package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	. "grpcgo/common"
	"grpcgo/gwpb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

type jsonItem struct {
	ID      string   `json:"id"`
	Name    string   `json:"name"`
	Count   int64    `json:"count,string"`
	Payload []byte   `json:"payload"`
	Tags    []string `json:"tags"`
}

type gwImpl struct{ gwpb.UnimplementedGwServer }

func (gwImpl) Echo(ctx context.Context, it *gwpb.Item) (*gwpb.Item, error) { return it, nil }

// countProxy 是只数字节的 TCP 代理(不解析协议,HTTP/1.1 和 HTTP/2 都能用)。
type countProxy struct {
	Addr   string
	cs, sc atomic.Int64
	conns  atomic.Int64
	ln     net.Listener
}

// cw 在每次写入时增量累加字节数。
type cw struct {
	w io.Writer
	n *atomic.Int64
}

func (c cw) Write(b []byte) (int, error) { c.n.Add(int64(len(b))); return c.w.Write(b) }

func newCountProxy(target string) *countProxy {
	ln, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	p := &countProxy{Addr: ln.Addr().String(), ln: ln}
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			p.conns.Add(1)
			s, err := net.Dial("tcp", target)
			if err != nil {
				c.Close()
				continue
			}
			go func() { io.Copy(cw{s, &p.cs}, c); s.Close() }()
			go func() { io.Copy(cw{c, &p.sc}, s); c.Close() }()
		}
	}()
	return p
}

func child() {
	// gRPC 服务
	gaddr, _ := Start0()
	// HTTP/1.1 JSON 服务
	hl, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	mux := http.NewServeMux()
	mux.HandleFunc("/echo", func(w http.ResponseWriter, r *http.Request) {
		var it jsonItem
		if err := json.NewDecoder(r.Body).Decode(&it); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(&it)
	})
	go http.Serve(hl, mux)
	fmt.Println(gaddr, hl.Addr().String())
	io.Copy(io.Discard, os.Stdin)
}

func Start0() (string, func()) {
	return StartGw()
}

func median(ds []time.Duration, p float64) time.Duration {
	sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
	return ds[int(float64(len(ds)-1)*p)]
}

func us(d time.Duration) string { return fmt.Sprintf("%d µs", d.Microseconds()) }

func main() {
	if len(os.Args) > 1 && os.Args[1] == "child" {
		child()
		return
	}
	cmd := exec.Command(os.Args[0], "child")
	in, _ := cmd.StdinPipe()
	o, _ := cmd.StdoutPipe()
	cmd.Start()
	line, _ := bufio.NewReader(o).ReadString('\n')
	fs := strings.Fields(line)
	gAddr, hAddr := fs[0], fs[1]
	defer func() { in.Close(); cmd.Wait() }()

	mk := func(payload, tags int) (*gwpb.Item, []byte) {
		it := &gwpb.Item{Id: "item-1", Name: "alice", Count: 123456789, Payload: bytes.Repeat([]byte{0xAB}, payload)}
		for i := 0; i < tags; i++ {
			it.Tags = append(it.Tags, fmt.Sprintf("tag-%d", i))
		}
		j := jsonItem{ID: it.Id, Name: it.Name, Count: it.Count, Payload: it.Payload, Tags: it.Tags}
		b, _ := json.Marshal(&j)
		return it, b
	}
	httpCall := func(c *http.Client, url string, body []byte) error {
		resp, err := c.Post(url, "application/json", bytes.NewReader(body))
		if err != nil {
			return err
		}
		io.Copy(io.Discard, resp.Body)
		return resp.Body.Close()
	}

	Sec("一:同一个 Item 在线上的字节数(稳态:连接已建立,连续 200 次请求取平均,含 HTTP 头/帧头,两个方向合计)")
	{
		for _, c := range []struct {
			name         string
			payload, tag int
		}{{"小(id、name、count)", 0, 0}, {"中(+10 个 tag、1 KiB payload)", 1024, 10}, {"大(+64 KiB payload)", 64 << 10, 10}} {
			it, jb := mk(c.payload, c.tag)
			gp := newCountProxy(gAddr)
			gconn, _ := grpc.NewClient(gp.Addr, insec, grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(64<<20)))
			gcl := gwpb.NewGwClient(gconn)
			for i := 0; i < 20; i++ {
				gcl.Echo(context.Background(), it)
			}
			time.Sleep(50 * time.Millisecond)
			cs0, sc0 := gp.cs.Load(), gp.sc.Load()
			for i := 0; i < 200; i++ {
				gcl.Echo(context.Background(), it)
			}
			time.Sleep(50 * time.Millisecond)
			gcs, gsc := float64(gp.cs.Load()-cs0)/200, float64(gp.sc.Load()-sc0)/200

			hp := newCountProxy(hAddr)
			tr := &http.Transport{MaxIdleConnsPerHost: 4}
			hc := &http.Client{Transport: tr}
			for i := 0; i < 20; i++ {
				httpCall(hc, "http://"+hp.Addr+"/echo", jb)
			}
			time.Sleep(50 * time.Millisecond)
			cs0, sc0 = hp.cs.Load(), hp.sc.Load()
			for i := 0; i < 200; i++ {
				httpCall(hc, "http://"+hp.Addr+"/echo", jb)
			}
			time.Sleep(50 * time.Millisecond)
			hcs, hsc := float64(hp.cs.Load()-cs0)/200, float64(hp.sc.Load()-sc0)/200
			P("%-28s gRPC:请求 %.0f + 响应 %.0f = %.0f 字节;HTTP/1.1 JSON:请求 %.0f + 响应 %.0f = %.0f 字节(JSON 是 gRPC 的 %.2f 倍)", c.name, gcs, gsc, gcs+gsc, hcs, hsc, hcs+hsc, (hcs+hsc)/(gcs+gsc))
			gconn.Close()
			tr.CloseIdleConnections()
			gp.ln.Close()
			hp.ln.Close()
		}
	}

	Sec("二:单个调用者顺序请求的延迟(1 条连接,每种 3000 次):小 Item 与 64 KiB payload 的 Item")
	{
		for _, c := range []struct {
			name         string
			payload, tag int
		}{{"小 Item", 0, 0}, {"64 KiB payload", 64 << 10, 10}} {
			it, jb := mk(c.payload, c.tag)
			gconn, _ := grpc.NewClient(gAddr, insec, grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(64<<20)))
			gcl := gwpb.NewGwClient(gconn)
			hc := &http.Client{Transport: &http.Transport{MaxIdleConnsPerHost: 1}}
			for i := 0; i < 200; i++ {
				gcl.Echo(context.Background(), it)
				httpCall(hc, "http://"+hAddr+"/echo", jb)
			}
			var gd, hd []time.Duration
			for i := 0; i < 3000; i++ {
				t0 := time.Now()
				gcl.Echo(context.Background(), it)
				gd = append(gd, time.Since(t0))
				t0 = time.Now()
				httpCall(hc, "http://"+hAddr+"/echo", jb)
				hd = append(hd, time.Since(t0))
			}
			P("%-16s gRPC p50 %s、p99 %s;HTTP/1.1 JSON p50 %s、p99 %s(p50 之比 %.2f)", c.name, us(median(gd, 0.5)), us(median(gd, 0.99)), us(median(hd, 0.5)), us(median(hd, 0.99)), float64(median(hd, 0.5))/float64(median(gd, 0.5)))
			gconn.Close()
		}
	}

	Sec("三:64 个并发调用者(小 Item,每种跑 2 秒):gRPC 1 条连接;HTTP/1.1 限制 1 条连接(请求排队);HTTP/1.1 放开到 64 条连接")
	{
		it, jb := mk(0, 0)
		run := func(f func()) (float64, time.Duration) {
			var stop atomic.Bool
			var wg sync.WaitGroup
			var mu sync.Mutex
			var all []time.Duration
			t0 := time.Now()
			for w := 0; w < 64; w++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					var mine []time.Duration
					for !stop.Load() {
						s := time.Now()
						f()
						mine = append(mine, time.Since(s))
					}
					mu.Lock()
					all = append(all, mine...)
					mu.Unlock()
				}()
			}
			time.Sleep(2 * time.Second)
			stop.Store(true)
			wg.Wait()
			return float64(len(all)) / time.Since(t0).Seconds(), median(all, 0.5)
		}
		gconn, _ := grpc.NewClient(gAddr, insec)
		gcl := gwpb.NewGwClient(gconn)
		gcl.Echo(context.Background(), it)
		q, p50 := run(func() { gcl.Echo(context.Background(), it) })
		P("gRPC,1 条连接:      %8.0f 请求/秒,p50 %s", q, us(p50))
		for _, n := range []int{1, 64} {
			tr := &http.Transport{MaxConnsPerHost: n, MaxIdleConnsPerHost: n}
			hc := &http.Client{Transport: tr}
			httpCall(hc, "http://"+hAddr+"/echo", jb)
			q, p50 = run(func() { httpCall(hc, "http://"+hAddr+"/echo", jb) })
			P("HTTP/1.1 JSON,%2d 条连接:%8.0f 请求/秒,p50 %s", n, q, us(p50))
			tr.CloseIdleConnections()
		}
		gconn.Close()
	}

	Sec("四:新连接上第一次请求的耗时(建连 + 第一次请求,各 100 次的中位数)")
	{
		it, jb := mk(0, 0)
		var gd, hd []time.Duration
		for i := 0; i < 100; i++ {
			t0 := time.Now()
			gconn, _ := grpc.NewClient(gAddr, insec)
			gwpb.NewGwClient(gconn).Echo(context.Background(), it)
			gd = append(gd, time.Since(t0))
			gconn.Close()
			t0 = time.Now()
			tr := &http.Transport{DisableKeepAlives: false}
			httpCall(&http.Client{Transport: tr}, "http://"+hAddr+"/echo", jb)
			hd = append(hd, time.Since(t0))
			tr.CloseIdleConnections()
		}
		P("gRPC:新连接 + 第一次请求 p50 %s;HTTP/1.1 JSON:p50 %s", us(median(gd, 0.5)), us(median(hd, 0.5)))
	}
}

// StartGw 在 127.0.0.1 上启动实现了 Gw.Echo 的 gRPC 服务。
func StartGw() (string, func()) {
	l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	gs := grpc.NewServer(grpc.MaxRecvMsgSize(64<<20), grpc.MaxSendMsgSize(64<<20))
	gwpb.RegisterGwServer(gs, gwImpl{})
	go gs.Serve(l)
	return l.Addr().String(), gs.Stop
}
