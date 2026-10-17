package main

import (
	"context"
	"fmt"
	"io"
	"runtime"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	m := st.Message()
	if len(m) > 60 {
		m = m[:60] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

type counters struct{ active, started atomic.Int64 }

// 服务端:ServerStream 发一条后一直等到 ctx 结束;ClientStream 一直收到 EOF 或 ctx 结束;Unary 立即返回。
func srv(c *counters) *DemoServer {
	return &DemoServer{
		OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			c.started.Add(1)
			c.active.Add(1)
			defer c.active.Add(-1)
			st.Send(&pb.Resp{})
			if r.Msg == "finite" {
				return nil
			}
			<-st.Context().Done()
			return st.Context().Err()
		},
		OnClientStream: func(st pb.Demo_ClientStreamServer) error {
			c.started.Add(1)
			c.active.Add(1)
			defer c.active.Add(-1)
			n := 0
			for {
				if _, err := st.Recv(); err != nil {
					if err == io.EOF {
						return st.SendAndClose(&pb.Resp{N: int32(n)})
					}
					return err
				}
				n++
			}
		},
	}
}

func settle() { time.Sleep(300 * time.Millisecond) }

func main() {
	Sec("一:客户端开了服务端流,收了第一条就不管了(没取消 ctx、没读到结束、也没保留引用):服务端 handler 还在不在,GC 能不能收走它")
	{
		var c counters
		addr, stop := Start(srv(&c))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		base := runtime.NumGoroutine()
		func() {
			for i := 0; i < 200; i++ {
				st, err := cl.ServerStream(context.Background(), &pb.Req{})
				if err == nil {
					st.Recv()
				}
			}
		}()
		settle()
		P("开了 200 个流、没处理:服务端在运行的 handler %d 个;进程 goroutine 比基线多 %d", c.active.Load(), runtime.NumGoroutine()-base)
		for i := 0; i < 3; i++ {
			runtime.GC()
			time.Sleep(100 * time.Millisecond)
		}
		P("丢掉所有引用并 runtime.GC() 3 次之后:服务端 handler %d 个;goroutine 比基线多 %d", c.active.Load(), runtime.NumGoroutine()-base)
		conn.Close()
		settle()
		P("conn.Close() 之后:服务端 handler %d 个", c.active.Load())
		stop()
	}

	Sec("二:泄漏的流占着名额,别的调用也被拖死:服务端 MaxConcurrentStreams(10);先泄漏 10 个流,再发一个 Unary(deadline 1 秒);然后释放(cancel)泄漏的流,再发一次 Unary")
	{
		var c counters
		addr, stop := Start(srv(&c), grpc.MaxConcurrentStreams(10))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		var cancels []context.CancelFunc
		for i := 0; i < 10; i++ {
			ctx, cancel := context.WithCancel(context.Background())
			cancels = append(cancels, cancel)
			st, err := cl.ServerStream(ctx, &pb.Req{})
			if err == nil {
				st.Recv()
			}
		}
		call := func() (time.Duration, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
			defer cancel()
			t0 := time.Now()
			_, err := cl.Unary(ctx, &pb.Req{})
			return time.Since(t0), err
		}
		el, err := call()
		P("10 个流被泄漏占满名额:Unary 调用 %s 后返回 %s", Ms(el), em(err))
		for _, cn := range cancels {
			cn()
		}
		settle()
		el, err = call()
		P("cancel 掉泄漏的流之后:Unary 调用 %s 后返回 %s;服务端在运行的 handler %d 个", Ms(el), em(err), c.active.Load())
		conn.Close()
		stop()
	}

	Sec("三:怎样才算“释放”了一个服务端流:只 CloseSend、cancel ctx、读到服务端自己结束(EOF)——服务端 handler 分别还在不在")
	{
		var c counters
		addr, stop := Start(srv(&c))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		// A: 只 CloseSend
		st, _ := cl.ServerStream(context.Background(), &pb.Req{})
		st.Recv()
		st.CloseSend()
		settle()
		P("只调用 CloseSend():服务端 handler %d 个(还在)", c.active.Load())
		// B: cancel
		ctx, cancel := context.WithCancel(context.Background())
		st2, _ := cl.ServerStream(ctx, &pb.Req{})
		st2.Recv()
		cancel()
		settle()
		P("再开一个并 cancel ctx:服务端 handler 共 %d 个(A 那个还在,B 已经释放)", c.active.Load())
		// C: 服务端自己结束,客户端读到 EOF
		st3, _ := cl.ServerStream(context.Background(), &pb.Req{Msg: "finite"})
		var err error
		for {
			if _, err = st3.Recv(); err != nil {
				break
			}
		}
		settle()
		P("再开一个会自己结束的流并读到 %v:服务端 handler 共 %d 个(仍只有 A)", err, c.active.Load())
		conn.Close()
		settle()
		P("conn.Close() 之后:服务端 handler %d 个", c.active.Load())
		stop()
	}

	Sec("四:客户端流忘记 CloseSend / CloseAndRecv:发了 3 条消息就没了下文,服务端 handler 还在 Recv 里等;调用 CloseAndRecv 之后")
	{
		var c counters
		addr, stop := Start(srv(&c))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		ctx, cancel := context.WithCancel(context.Background())
		st, _ := cl.ClientStream(ctx)
		for i := 0; i < 3; i++ {
			st.Send(&pb.Req{})
		}
		settle()
		P("发了 3 条之后没有 CloseAndRecv:服务端 handler %d 个", c.active.Load())
		r, err := st.CloseAndRecv()
		settle()
		P("调用 CloseAndRecv():%s,服务端数到 %d 条;服务端 handler %d 个", em(err), r.GetN(), c.active.Load())
		cancel()
		conn.Close()
		stop()
	}

	Sec("五:泄漏的流让连接永远“不空闲”:服务端 MaxConnectionIdle = 300 ms;有一个泄漏的流 vs 没有任何流,1.5 秒内服务端有没有发 GOAWAY 关闭连接")
	{
		for _, leak := range []bool{true, false} {
			var c counters
			addr, stop := Start(srv(&c), grpc.KeepaliveParams(keepalive.ServerParameters{MaxConnectionIdle: 300 * time.Millisecond}))
			tap := NewTap(addr)
			conn, _ := grpc.NewClient(tap.Addr, insec)
			cl := pb.NewDemoClient(conn)
			var cancel context.CancelFunc = func() {}
			if leak {
				var ctx context.Context
				ctx, cancel = context.WithCancel(context.Background())
				st, _ := cl.ServerStream(ctx, &pb.Req{})
				st.Recv()
			} else {
				cl.Unary(context.Background(), &pb.Req{})
			}
			time.Sleep(1500 * time.Millisecond)
			g := 0
			for _, e := range tap.Snapshot() {
				if e.Dir == "S→C" && e.Type == "GOAWAY" {
					g++
				}
			}
			name := "有一个泄漏的流"
			if !leak {
				name = "没有任何在途的流"
			}
			P("%-16s 1.5 秒内服务端发出的 GOAWAY %d 个;TCP 连接数 %d", name, g, tap.Conns)
			if leak {
				cancel()
				time.Sleep(800 * time.Millisecond)
				g2 := 0
				for _, e := range tap.Snapshot() {
					if e.Dir == "S→C" && e.Type == "GOAWAY" {
						g2++
					}
				}
				P("%-16s cancel 之后再过 0.8 秒:GOAWAY 共 %d 个", "", g2)
			}
			conn.Close()
			tap.Close()
			stop()
		}
	}
}
