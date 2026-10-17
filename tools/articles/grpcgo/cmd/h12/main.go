package main

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func pingsAt(tap *Tap, dir string, ack bool) []float64 {
	var out []float64
	for _, e := range tap.Snapshot() {
		if e.Type == "PING" && e.Dir == dir && strings.Contains(e.Flags, "ACK") == ack && e.Info != "02041010090e0707" {
			out = append(out, float64(e.T.Milliseconds())/1000)
		}
	}
	return out
}

func fmtT(v []float64) string {
	var o []string
	for _, x := range v {
		o = append(o, fmt.Sprintf("%.1f", x))
	}
	return "[" + strings.Join(o, " ") + "] 秒"
}

func goaways(tap *Tap) []string {
	var o []string
	for _, e := range tap.Snapshot() {
		if e.Type == "GOAWAY" {
			o = append(o, fmt.Sprintf("%.1f 秒 %s GOAWAY:%s", float64(e.T.Milliseconds())/1000, e.Dir, e.Info))
		}
	}
	return o
}

func newSrv() *DemoServer {
	return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		if r.Msg == "hang" {
			<-ctx.Done()
		}
		return &pb.Resp{}, nil
	}, OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		<-st.Context().Done()
		return nil
	}}
}

type scen struct {
	name string
	out  []string
}

func main() {
	var wg sync.WaitGroup
	var mu sync.Mutex
	res := map[string][]string{}
	add := func(k string, f func() []string) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := f()
			mu.Lock()
			res[k] = r
			mu.Unlock()
		}()
	}
	setup := func(sopts []grpc.ServerOption, dopts ...grpc.DialOption) (*Tap, pb.DemoClient, func()) {
		addr, stop := StartWith(newSrv(), sopts...)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, append([]grpc.DialOption{insec}, dopts...)...)
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		time.Sleep(50 * time.Millisecond)
		tap.Reset()
		return tap, cl, func() { conn.Close(); tap.Close(); stop() }
	}
	ka := func(t, to time.Duration, pws bool) grpc.DialOption {
		return grpc.WithKeepaliveParams(keepalive.ClientParameters{Time: t, Timeout: to, PermitWithoutStream: pws})
	}

	// 场景 1:客户端 Time 设 200 ms(会被抬到 10 s),服务端默认策略
	add("1", func() []string {
		tap, _, done := setup(nil, ka(200*time.Millisecond, 100*time.Millisecond, true))
		defer done()
		time.Sleep(42 * time.Second)
		return []string{fmt.Sprintf("客户端 PING 的时刻 %s;服务端 ACK 的时刻 %s", fmtT(pingsAt(tap, "C→S", false)), fmtT(pingsAt(tap, "S→C", true))), strings.Join(goaways(tap), " | ")}
	})
	// 场景 2:客户端 Time=10 s,服务端放宽到 MinTime=5 s,PermitWithoutStream
	add("2", func() []string {
		tap, _, done := setup([]grpc.ServerOption{grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{MinTime: 5 * time.Second, PermitWithoutStream: true})}, ka(10*time.Second, 2*time.Second, true))
		defer done()
		time.Sleep(42 * time.Second)
		return []string{fmt.Sprintf("客户端 PING 的时刻 %s;服务端 ACK 的时刻 %s;GOAWAY %d 个;TCP 连接 %d 条", fmtT(pingsAt(tap, "C→S", false)), fmtT(pingsAt(tap, "S→C", true)), len(goaways(tap)), tap.Conns)}
	})
	// 场景 3 / 4:黑洞,有 keepalive 与没有
	for _, withKA := range []bool{true, false} {
		withKA := withKA
		add(fmt.Sprint("blackhole-", withKA), func() []string {
			var opts []grpc.DialOption
			if withKA {
				opts = append(opts, ka(10*time.Second, 2*time.Second, true))
			}
			tap, cl, done := setup([]grpc.ServerOption{grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{MinTime: 5 * time.Second, PermitWithoutStream: true})}, opts...)
			defer done()
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			out := make(chan string, 1)
			t0 := time.Now()
			go func() {
				_, err := cl.Unary(ctx, &pb.Req{Msg: "hang"})
				s, _ := status.FromError(err)
				out <- fmt.Sprintf("code=%s message=%q", s.Code(), s.Message())
			}()
			time.Sleep(time.Second)
			tap.DropSC.Store(true)
			tap.DropCS.Store(true)
			tb := time.Since(t0)
			r := <-out
			return []string{fmt.Sprintf("黑洞在调用开始 %.1f 秒后出现;调用在 %.1f 秒时返回(黑洞之后 %.1f 秒):%s", tb.Seconds(), time.Since(t0).Seconds(), (time.Since(t0) - tb).Seconds(), r)}
		})
	}
	// 场景 5:服务端 keepalive
	add("5", func() []string {
		tap, cl, done := setup([]grpc.ServerOption{grpc.KeepaliveParams(keepalive.ServerParameters{Time: 200 * time.Millisecond, Timeout: 1 * time.Second})})
		defer done()
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		var tb time.Time
		var mu2 sync.Mutex
		out := make(chan string, 1)
		go func() {
			st, _ := cl.ServerStream(ctx, &pb.Req{})
			_, err := st.Recv()
			s, _ := status.FromError(err)
			mu2.Lock()
			out <- fmt.Sprintf("在途的流在黑洞开始后 %.1f 秒收到 code=%s message=%q", time.Since(tb).Seconds(), s.Code(), s.Message())
			mu2.Unlock()
		}()
		time.Sleep(4500 * time.Millisecond)
		normal := fmt.Sprintf("正常运行 4.5 秒:服务端发出的 PING %s;客户端回的 ACK %s", fmtT(pingsAt(tap, "S→C", false)), fmtT(pingsAt(tap, "C→S", true)))
		mu2.Lock()
		tb = time.Now()
		mu2.Unlock()
		tap.DropCS.Store(true)
		r := <-out
		return []string{normal, r}
	})
	// 场景 6:PermitWithoutStream=false
	add("6", func() []string {
		tap, cl, done := setup([]grpc.ServerOption{grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{MinTime: 5 * time.Second, PermitWithoutStream: true})}, ka(10*time.Second, 2*time.Second, false))
		defer done()
		time.Sleep(25 * time.Second)
		idle := pingsAt(tap, "C→S", false)
		ctx, cancel := context.WithCancel(context.Background())
		go cl.ServerStream(ctx, &pb.Req{})
		time.Sleep(100 * time.Millisecond)
		tap.Reset()
		time.Sleep(25 * time.Second)
		active := pingsAt(tap, "C→S", false)
		cancel()
		return []string{fmt.Sprintf("PermitWithoutStream=false:空闲 25 秒客户端 PING %d 个 %s;有在途的流 25 秒 %d 个 %s", len(idle), fmtT(idle), len(active), fmtT(active))}
	})
	wg.Wait()

	Sec("一:客户端 keepalive.Time 设成 200 ms,服务端用默认的 EnforcementPolicy(MinTime 5 分钟,不允许没有流时的 PING):42 秒内的 PING 与 GOAWAY(客户端的 Time 被抬到 10 秒)")
	for _, l := range res["1"] {
		P("%s", l)
	}
	Sec("二:服务端放宽 EnforcementPolicy(MinTime = 5 s,PermitWithoutStream = true),客户端 Time = 10 s、Timeout = 2 s:42 秒内")
	for _, l := range res["2"] {
		P("%s", l)
	}
	Sec("三:对端变成黑洞(连接还在,但两个方向的数据都被丢弃),有一个挂住的调用(deadline 30 秒):客户端 keepalive(Time 10 s、Timeout 2 s)与没有 keepalive 的对照")
	P("有 keepalive:%s", res["blackhole-true"][0])
	P("没有 keepalive:%s", res["blackhole-false"][0])
	Sec("四:服务端 keepalive(Time = 200 ms 会被抬到 1 秒,Timeout = 1 秒):正常时服务端发 PING;客户端到服务端的方向变成黑洞后,服务端多久关闭连接")
	for _, l := range res["5"] {
		P("%s", l)
	}
	Sec("五:PermitWithoutStream = false(默认):连接空闲时不发 keepalive PING,有在途的流时才发(客户端 Time = 10 s)")
	for _, l := range res["6"] {
		P("%s", l)
	}
}
