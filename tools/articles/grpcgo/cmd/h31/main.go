package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

// ---------- 子进程:纯服务端,可以查询自己的 goroutine 数和内存 ----------

func child() {
	release := make(chan struct{})
	srv := &DemoServer{
		OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			<-release
			return &pb.Resp{}, nil
		},
		OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			st.Send(&pb.Resp{})
			<-release
			return nil
		},
		OnBidi: func(st pb.Demo_BidiServer) error {
			st.Recv()
			<-release
			return nil
		},
	}
	addr, _ := Start(srv)
	fmt.Println(addr)
	sc := bufio.NewScanner(os.Stdin)
	for sc.Scan() {
		switch sc.Text() {
		case "stat":
			runtime.GC()
			runtime.GC()
			var m runtime.MemStats
			runtime.ReadMemStats(&m)
			fmt.Printf("%d %d %d %d\n", runtime.NumGoroutine(), m.HeapAlloc, m.StackInuse, m.Sys)
		case "release":
			close(release)
			release = make(chan struct{})
			fmt.Println("ok")
		}
	}
}

type stat struct{ g, heap, stack, sys int64 }

type proc struct {
	cmd  *exec.Cmd
	in   io.WriteCloser
	out  *bufio.Reader
	addr string
}

func spawn() *proc {
	cmd := exec.Command(os.Args[0], "child")
	in, _ := cmd.StdinPipe()
	o, _ := cmd.StdoutPipe()
	cmd.Start()
	rd := bufio.NewReader(o)
	a, _ := rd.ReadString('\n')
	return &proc{cmd, in, rd, strings.TrimSpace(a)}
}
func (p *proc) stat() stat {
	fmt.Fprintln(p.in, "stat")
	l, _ := p.out.ReadString('\n')
	var s stat
	fmt.Sscan(l, &s.g, &s.heap, &s.stack, &s.sys)
	return s
}
func (p *proc) release() { fmt.Fprintln(p.in, "release"); p.out.ReadString('\n') }
func (p *proc) close()   { p.in.Close(); p.cmd.Wait() }

// openBlocked 在 addr 上建 conns 条连接,共发起 n 个会阻塞在服务端的调用,返回清理函数。
func openBlocked(addr, kind string, n, conns int) func() {
	var cs []*grpc.ClientConn
	var wg sync.WaitGroup
	ctx, cancel := context.WithCancel(context.Background())
	for i := 0; i < conns; i++ {
		c, _ := grpc.NewClient(addr, insec)
		cs = append(cs, c)
	}
	started := make(chan struct{}, n)
	for i := 0; i < n; i++ {
		cl := pb.NewDemoClient(cs[i%conns])
		wg.Add(1)
		go func() {
			defer wg.Done()
			switch kind {
			case "unary":
				started <- struct{}{}
				cl.Unary(ctx, &pb.Req{})
			case "server-stream":
				st, err := cl.ServerStream(ctx, &pb.Req{})
				if err == nil {
					st.Recv()
					started <- struct{}{}
					st.Recv()
				}
			case "bidi":
				st, err := cl.Bidi(ctx)
				if err == nil {
					st.Send(&pb.Req{})
					started <- struct{}{}
					st.Recv()
				}
			}
		}()
	}
	for i := 0; i < n; i++ {
		<-started
	}
	time.Sleep(500 * time.Millisecond)
	return func() {
		cancel()
		wg.Wait()
		for _, c := range cs {
			c.Close()
		}
	}
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "child" {
		child()
		return
	}

	Sec("一:每个正在处理中的调用,服务端多出几个 goroutine(子进程里的纯服务端,调用都阻塞在 handler 里,1000 个调用分在 10 条连接上)")
	{
		for _, kind := range []string{"unary", "server-stream", "bidi"} {
			p := spawn()
			base := p.stat()
			done := openBlocked(p.addr, kind, 1000, 10)
			mid := p.stat()
			p.release()
			done()
			time.Sleep(300 * time.Millisecond)
			after := p.stat()
			P("%-14s 基线 %d 个 goroutine;1000 个调用在途时 %d 个(每个调用 +%.2f);全部结束后 %d 个", kind, base.g, mid.g, float64(mid.g-base.g)/1000, after.g)
			p.close()
		}
	}

	Sec("二:每个在途的 unary 调用占多少内存(服务端子进程,runtime.GC 之后读 HeapAlloc 与 StackInuse 的增量)")
	{
		for _, n := range []int{1000, 10000} {
			p := spawn()
			base := p.stat()
			done := openBlocked(p.addr, "unary", n, 10)
			mid := p.stat()
			dh, ds, dt := float64(mid.heap-base.heap)/float64(n), float64(mid.stack-base.stack)/float64(n), float64(mid.sys-base.sys)/float64(n)
			P("%5d 个在途调用:堆 +%.1f KiB/个;goroutine 栈 +%.1f KiB/个;合计 %.1f KiB/个;进程向系统申请的总量(Sys)+%.1f KiB/个;goroutine 数 %d → %d", n, dh/1024, ds/1024, (dh+ds)/1024, dt/1024, base.g, mid.g)
			p.release()
			done()
			p.close()
		}
	}

	Sec("三:限制处理中的调用数:5000 个调用同时到达、handler 各睡 20 ms:不限制、拦截器里的信号量(100)、grpc.NumStreamWorkers(8)——服务端同时在处理的调用峰值与总耗时")
	{
		for _, c := range []struct {
			name string
			opts func(sem chan struct{}) []grpc.ServerOption
		}{
			{"不限制", func(chan struct{}) []grpc.ServerOption { return nil }},
			{"信号量 100(拦截器)", func(sem chan struct{}) []grpc.ServerOption {
				return []grpc.ServerOption{grpc.UnaryInterceptor(func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
					sem <- struct{}{}
					defer func() { <-sem }()
					return h(ctx, req)
				})}
			}},
			{"NumStreamWorkers(8)", func(chan struct{}) []grpc.ServerOption { return []grpc.ServerOption{grpc.NumStreamWorkers(8)} }},
		} {
			var cur, peak atomic.Int64
			srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				n := cur.Add(1)
				for {
					p := peak.Load()
					if n <= p || peak.CompareAndSwap(p, n) {
						break
					}
				}
				time.Sleep(20 * time.Millisecond)
				cur.Add(-1)
				return &pb.Resp{}, nil
			}}
			addr, stop := Start(srv, c.opts(make(chan struct{}, 100))...)
			var cs []*grpc.ClientConn
			for i := 0; i < 10; i++ {
				cn, _ := grpc.NewClient(addr, insec)
				cs = append(cs, cn)
				pb.NewDemoClient(cn).Unary(context.Background(), &pb.Req{})
			}
			peak.Store(0)
			var wg sync.WaitGroup
			t0 := time.Now()
			for i := 0; i < 5000; i++ {
				wg.Add(1)
				cl := pb.NewDemoClient(cs[i%10])
				go func() { defer wg.Done(); cl.Unary(context.Background(), &pb.Req{}) }()
			}
			wg.Wait()
			P("%-22s 同时在处理的峰值 %4d;5000 个调用总耗时 %s", c.name, peak.Load(), Ms(time.Since(t0)))
			for _, cn := range cs {
				cn.Close()
			}
			stop()
		}
	}

	Sec("四:客户端取消之后,不看 ctx 的 handler 还在跑:500 个调用的 handler 睡 3 秒,客户端 100 ms 后取消;取消完成后 500 ms 与 3.5 秒时,仍在运行的 handler 数与服务端多出的 goroutine 数(与调用前基线比,同进程内有客户端 goroutine,看趋势)")
	{
		for _, aware := range []bool{false, true} {
			aware := aware
			var running atomic.Int64
			srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				if r.Msg == "warm" {
					return &pb.Resp{}, nil
				}
				running.Add(1)
				defer running.Add(-1)
				if aware {
					select {
					case <-time.After(3 * time.Second):
					case <-ctx.Done():
					}
				} else {
					time.Sleep(3 * time.Second)
				}
				return &pb.Resp{}, nil
			}}
			addr, stop := Start(srv)
			conn, _ := grpc.NewClient(addr, insec)
			cl := pb.NewDemoClient(conn)
			cl.Unary(context.Background(), &pb.Req{Msg: "warm"})
			time.Sleep(200 * time.Millisecond)
			base := runtime.NumGoroutine()
			ctx, cancel := context.WithCancel(context.Background())
			var wg sync.WaitGroup
			for i := 0; i < 500; i++ {
				wg.Add(1)
				go func() { defer wg.Done(); cl.Unary(ctx, &pb.Req{}) }()
			}
			time.Sleep(100 * time.Millisecond)
			inflight := running.Load()
			t0 := time.Now()
			cancel()
			wg.Wait()
			time.Sleep(500*time.Millisecond - time.Since(t0))
			r1, g1 := running.Load(), runtime.NumGoroutine()-base
			time.Sleep(3500*time.Millisecond - time.Since(t0))
			r2, g2 := running.Load(), runtime.NumGoroutine()-base
			name := "handler 不看 ctx(time.Sleep 3 秒)"
			if aware {
				name = "handler 用 select 监听 ctx"
			}
			P("%-30s 取消前在运行 %d;取消后 500 ms:仍在运行 %d、goroutine +%d;3.5 秒后:仍在运行 %d、goroutine +%d", name, inflight, r1, g1, r2, g2)
			conn.Close()
			stop()
		}
	}
}
