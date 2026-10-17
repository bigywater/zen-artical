package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/net/dns/dnsmessage"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	dnsres "google.golang.org/grpc/resolver/dns"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

// ---------- 本机的小 DNS 服务器(只在 127.0.0.1 的 UDP 端口上,记录查询) ----------

type zone struct {
	ips []string // A 记录
	ttl uint32
	nx  bool   // 对 A 查询返回 NXDOMAIN
	txt string // _grpc_config.<host> 的 TXT 内容,空则无
}

type query struct {
	t     time.Duration
	name  string
	qtype string
}

type dnsServer struct {
	addr  string
	conn  *net.UDPConn
	mu    sync.Mutex
	z     zone
	log   []query
	start time.Time
}

func newDNS(z zone) *dnsServer {
	port := FreePort()
	c, err := net.ListenUDP("udp", &net.UDPAddr{IP: net.ParseIP("127.0.0.1"), Port: port})
	if err != nil {
		panic(err)
	}
	d := &dnsServer{addr: c.LocalAddr().String(), conn: c, z: z, start: time.Now()}
	go d.serve()
	return d
}

func (d *dnsServer) set(f func(z *zone)) { d.mu.Lock(); f(&d.z); d.mu.Unlock() }
func (d *dnsServer) reset()              { d.mu.Lock(); d.log = nil; d.start = time.Now(); d.mu.Unlock() }
func (d *dnsServer) close()              { d.conn.Close() }

func (d *dnsServer) queries(typ string) []query {
	d.mu.Lock()
	defer d.mu.Unlock()
	var o []query
	for _, q := range d.log {
		if typ == "" || q.qtype == typ {
			o = append(o, q)
		}
	}
	return o
}

func times(qs []query) string {
	var o []string
	for _, q := range qs {
		o = append(o, fmt.Sprintf("%.1f", q.t.Seconds()))
	}
	return "[" + strings.Join(o, " ") + "]"
}

func (d *dnsServer) serve() {
	buf := make([]byte, 1500)
	for {
		n, from, err := d.conn.ReadFromUDP(buf)
		if err != nil {
			return
		}
		var p dnsmessage.Parser
		h, err := p.Start(buf[:n])
		if err != nil {
			continue
		}
		q, err := p.Question()
		if err != nil {
			continue
		}
		d.mu.Lock()
		z := d.z
		d.log = append(d.log, query{time.Since(d.start), q.Name.String(), q.Type.String()})
		d.mu.Unlock()
		rcode := dnsmessage.RCodeSuccess
		if z.nx && q.Type == dnsmessage.TypeA {
			rcode = dnsmessage.RCodeNameError
		}
		b := dnsmessage.NewBuilder(nil, dnsmessage.Header{ID: h.ID, Response: true, Authoritative: true, RecursionAvailable: true, RCode: rcode})
		b.EnableCompression()
		b.StartQuestions()
		b.Question(q)
		b.StartAnswers()
		hdr := dnsmessage.ResourceHeader{Name: q.Name, Class: dnsmessage.ClassINET, TTL: z.ttl}
		switch {
		case q.Type == dnsmessage.TypeA && !z.nx:
			for _, ip := range z.ips {
				hdr.Type = dnsmessage.TypeA
				var a [4]byte
				copy(a[:], net.ParseIP(ip).To4())
				b.AResource(hdr, dnsmessage.AResource{A: a})
			}
		case q.Type == dnsmessage.TypeTXT && z.txt != "" && strings.HasPrefix(q.Name.String(), "_grpc_config."):
			hdr.Type = dnsmessage.TypeTXT
			b.TXTResource(hdr, dnsmessage.TXTResource{TXT: []string{z.txt}})
		}
		out, err := b.Finish()
		if err == nil {
			d.conn.WriteToUDP(out, from)
		}
	}
}

// ---------- 后端:假 IP 10.9.0.N:7000 通过自定义 dialer 映射到本机真实后端 ----------

type backend struct {
	idx  int
	addr string
	hits atomic.Int64
	stop func()
}

func newBackend(idx int) *backend {
	b := &backend{idx: idx}
	b.addr, b.stop = Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		b.hits.Add(1)
		return &pb.Resp{N: int32(idx)}, nil
	}})
	return b
}

func fakeIP(i int) string { return fmt.Sprintf("10.9.0.%d", i+1) }

type dialLog struct {
	mu    sync.Mutex
	addrs []string
}

func (l *dialLog) add(a string) {
	l.mu.Lock()
	l.addrs = append(l.addrs, a)
	l.mu.Unlock()
}
func (l *dialLog) uniq() string {
	l.mu.Lock()
	defer l.mu.Unlock()
	m := map[string]bool{}
	var o []string
	for _, a := range l.addrs {
		if !m[a] {
			m[a] = true
			o = append(o, a)
		}
	}
	return strings.Join(o, " ")
}

func dialer(bs []*backend, lg *dialLog) grpc.DialOption {
	return grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
		lg.add(addr)
		host, _, _ := net.SplitHostPort(addr)
		for _, b := range bs {
			if host == fakeIP(b.idx) {
				return (&net.Dialer{}).DialContext(ctx, "tcp", b.addr)
			}
		}
		return nil, fmt.Errorf("没有这个假地址的后端:%s", addr)
	})
}

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func callN(ctx context.Context, cl pb.DemoClient, opts ...grpc.CallOption) (int, error) {
	c, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	r, err := cl.Unary(c, &pb.Req{}, opts...)
	if err != nil {
		return -1, err
	}
	return int(r.N), nil
}

func hitsOf(bs []*backend) []int64 {
	var o []int64
	for _, b := range bs {
		o = append(o, b.hits.Load())
	}
	return o
}

const RR = `{"loadBalancingConfig":[{"round_robin":{}}]}`

func typeCounts(d *dnsServer) string {
	m := map[string]int{}
	for _, q := range d.queries("") {
		m[q.qtype]++
	}
	var ks []string
	for k := range m {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	var o []string
	for _, k := range ks {
		o = append(o, fmt.Sprintf("%s %d", strings.TrimPrefix(k, "Type"), m[k]))
	}
	if len(o) == 0 {
		return "0 个查询"
	}
	return strings.Join(o, "、")
}

func mkBackends(n int) []*backend {
	var bs []*backend
	for i := 0; i < n; i++ {
		bs = append(bs, newBackend(i))
	}
	return bs
}

func ips(n ...int) []string {
	var o []string
	for _, i := range n {
		o = append(o, fakeIP(i))
	}
	return o
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "txt-child" {
		txtChild()
		return
	}

	Sec("一:不同写法的 target:解析器是谁、DNS 服务器收到什么查询、自定义 dialer 收到的地址是什么(svc.test 的 A 记录是 10.9.0.1 到 10.9.0.3,TTL 1 秒;端口 7000)")
	{
		bs := mkBackends(3)
		d := newDNS(zone{ips: ips(0, 1, 2), ttl: 1})
		for _, tg := range []string{
			"passthrough:///svc.test:7000",
			"dns://" + d.addr + "/svc.test:7000",
			"dns://" + d.addr + "/svc.test",
			"dns:///10.9.0.1:7000",
			"svc.test:7000",
		} {
			d.reset()
			lg := &dialLog{}
			conn, _ := grpc.NewClient(tg, insec, dialer(bs, lg))
			cl := pb.NewDemoClient(conn)
			n, err := callN(context.Background(), cl)
			res := fmt.Sprintf("成功,后端 %d", n)
			if err != nil {
				st, _ := status.FromError(err)
				m := st.Message()
				if len(m) > 110 {
					m = m[:110] + "…"
				}
				res = fmt.Sprintf("失败 code=%s message=%q", st.Code(), m)
			}
			time.Sleep(50 * time.Millisecond)
			tg2 := strings.ReplaceAll(tg, d.addr, "<本机DNS>")
			P("%-36s → DNS 查询:%s;dialer 收到的地址:%s;%s", tg2, typeCounts(d), lg.uniq(), res)
			conn.Close()
		}
		d.close()
		for _, b := range bs {
			b.stop()
		}
	}

	Sec("二:一个域名 3 条 A 记录 + round_robin:90 次调用的分布,以及启动时 DNS 服务器收到哪些类型的查询")
	{
		bs := mkBackends(3)
		d := newDNS(zone{ips: ips(0, 1, 2), ttl: 1})
		lg := &dialLog{}
		conn, _ := grpc.NewClient("dns://"+d.addr+"/svc.test:7000", insec, dialer(bs, lg), grpc.WithDefaultServiceConfig(RR))
		cl := pb.NewDemoClient(conn)
		for i := 0; i < 90; i++ {
			callN(context.Background(), cl)
		}
		P("90 次调用各后端收到 %v;dialer 收到的地址:%s", hitsOf(bs), lg.uniq())
		P("DNS 服务器收到的查询:%s", typeCounts(d))
		var names []string
		seen := map[string]bool{}
		for _, q := range d.queries("") {
			k := q.qtype + " " + q.name
			if !seen[k] {
				seen[k] = true
				names = append(names, k)
			}
		}
		P("查询的名字:%s", strings.Join(names, ";"))
		conn.Close()
		d.close()
		for _, b := range bs {
			b.stop()
		}
	}

	Sec("三:DNS 里的 TXT 记录(_grpc_config.<域名>)能带服务配置:TXT 里写 round_robin,客户端不设任何默认配置;默认环境 vs GRPC_ENABLE_TXT_SERVICE_CONFIG=false")
	for _, env := range []string{"", "GRPC_ENABLE_TXT_SERVICE_CONFIG=false"} {
		cmd := exec.Command(os.Args[0], "txt-child")
		cmd.Env = os.Environ()
		name := "默认环境"
		if env != "" {
			cmd.Env = append(cmd.Env, env)
			name = env
		}
		out, err := cmd.CombinedOutput()
		if err != nil {
			P("%s:子进程出错 %v %s", name, err, out)
			continue
		}
		P("%-38s %s", name, strings.TrimSpace(string(out)))
	}

	// 四:重新解析的时机
	for _, c := range []struct {
		name  string
		minIv time.Duration
		total time.Duration
	}{{"默认 MinResolutionInterval = 30 s", 0, 36 * time.Second}, {"SetMinResolutionInterval(1 s)", time.Second, 14 * time.Second}} {
		if c.minIv > 0 {
			dnsres.SetMinResolutionInterval(c.minIv)
		}
		Sec("四:什么时候重新解析 DNS——" + c.name + "。A 记录 TTL 1 秒;2 秒时把记录从 [1 2 3] 换成 [3 4 5];6 秒时停掉后端 1(当前在用),每 100 ms 调用一次共 " + fmt.Sprint(int(c.total.Seconds())) + " 秒")
		bs := mkBackends(5)
		d := newDNS(zone{ips: ips(0, 1, 2), ttl: 1})
		lg := &dialLog{}
		conn, _ := grpc.NewClient("dns://"+d.addr+"/svc.test:7000", insec, dialer(bs, lg), grpc.WithDefaultServiceConfig(RR))
		cl := pb.NewDemoClient(conn)
		callN(context.Background(), cl)
		d.reset()
		t0 := time.Now()
		type rec struct {
			t time.Duration
			n int
		}
		var recs []rec
		changed, killed := false, false
		for time.Since(t0) < c.total {
			el := time.Since(t0)
			if !changed && el >= 2*time.Second {
				d.set(func(z *zone) { z.ips = ips(2, 3, 4) })
				changed = true
			}
			if !killed && el >= 6*time.Second {
				bs[0].stop()
				killed = true
			}
			n, _ := callN(context.Background(), cl)
			recs = append(recs, rec{el, n})
			time.Sleep(100 * time.Millisecond)
		}
		set := func(a, b float64) string {
			m := map[int]bool{}
			fails := 0
			for _, r := range recs {
				if r.t.Seconds() >= a && r.t.Seconds() < b {
					if r.n < 0 {
						fails++
					} else {
						m[r.n+1] = true
					}
				}
			}
			var ks []int
			for k := range m {
				ks = append(ks, k)
			}
			sort.Ints(ks)
			return fmt.Sprintf("后端集合 %v,失败 %d 次", ks, fails)
		}
		P("DNS 的 A 查询时刻(秒,相对 t0):%s", times(d.queries("TypeA")))
		P("0–2 秒(记录 [1 2 3]):%s", set(0, 2))
		P("2–6 秒(记录已换成 [3 4 5],后端 1 还在):%s", set(2, 6))
		P("6 秒起(后端 1 已停掉),到最后一次 A 查询之前:%s", func() string {
			qs := d.queries("TypeA")
			end := c.total.Seconds()
			if len(qs) > 0 {
				end = qs[len(qs)-1].t.Seconds()
			}
			return fmt.Sprintf("[6, %.1f) %s", end, set(6, end))
		}())
		P("最后一次 A 查询之后:%s", func() string {
			qs := d.queries("TypeA")
			if len(qs) == 0 {
				return "(没有查询)"
			}
			return set(qs[len(qs)-1].t.Seconds()+0.5, c.total.Seconds())
		}())
		conn.Close()
		d.close()
		for _, b := range bs {
			b.stop()
		}
	}

	Sec("五:DNS 解析失败的表现:域名不存在(NXDOMAIN)时 fail-fast 调用和 WaitForReady 调用;3 秒后把记录加上去")
	{
		bs := mkBackends(1)
		d := newDNS(zone{nx: true, ttl: 1})
		lg := &dialLog{}
		conn, _ := grpc.NewClient("dns://"+d.addr+"/svc.test:7000", insec, dialer(bs, lg))
		cl := pb.NewDemoClient(conn)
		t0 := time.Now()
		_, err := callN(context.Background(), cl)
		st, _ := status.FromError(err)
		P("fail-fast 调用:%s 后返回 code=%s message=%q", Ms(time.Since(t0)), st.Code(), st.Message())
		wr := make(chan string, 1)
		t1 := time.Now()
		go func() {
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			_, err := cl.Unary(ctx, &pb.Req{}, grpc.WaitForReady(true))
			el := time.Since(t1)
			st, _ := status.FromError(err)
			wr <- fmt.Sprintf("WaitForReady 调用:%.1f 秒后返回 code=%s", el.Seconds(), st.Code())
		}()
		time.Sleep(3 * time.Second)
		d.set(func(z *zone) { z.nx = false; z.ips = ips(0) })
		P("3 秒时 DNS 加上记录;这时 A 查询时刻(相对 t0)%s", times(d.queries("TypeA")))
		P("%s", <-wr)
		P("整个过程 A 查询时刻(秒):%s", times(d.queries("TypeA")))
		var nm []string
		for _, q := range d.queries("TypeA") {
			nm = append(nm, q.name)
		}
		P("A 查询的名字依次是:%s", strings.Join(nm, " "))
		conn.Close()
		d.close()
		bs[0].stop()
	}

	Sec("六:域名存在但一条 A 记录都没有(NOERROR 空答案)时的调用")
	{
		bs := mkBackends(1)
		d := newDNS(zone{ips: nil, ttl: 1})
		conn, _ := grpc.NewClient("dns://"+d.addr+"/svc.test:7000", insec, dialer(bs, &dialLog{}))
		cl := pb.NewDemoClient(conn)
		t0 := time.Now()
		_, err := callN(context.Background(), cl)
		st, _ := status.FromError(err)
		P("fail-fast 调用:%s 后返回 code=%s message=%q", Ms(time.Since(t0)), st.Code(), st.Message())
		_ = codes.OK
		conn.Close()
		d.close()
		bs[0].stop()
	}
}

func txtChild() {
	bs := mkBackends(3)
	d := newDNS(zone{ips: ips(0, 1, 2), ttl: 1, txt: `grpc_config=[{"serviceConfig":{"loadBalancingConfig":[{"round_robin":{}}]}}]`})
	conn, _ := grpc.NewClient("dns://"+d.addr+"/svc.test:7000", insec, dialer(bs, &dialLog{}))
	cl := pb.NewDemoClient(conn)
	for i := 0; i < 30; i++ {
		callN(context.Background(), cl)
	}
	fmt.Printf("30 次调用各后端收到 %v;DNS 查询:%s\n", hitsOf(bs), typeCounts(d))
}
