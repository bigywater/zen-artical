package main

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	hpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/resolver"
	"google.golang.org/grpc/resolver/manual"
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
	if len(m) > 70 {
		m = m[:70] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

type srv struct {
	gs   *grpc.Server
	hs   *health.Server
	addr string
}

func start(impl *DemoServer, opts ...grpc.ServerOption) *srv {
	s := &srv{hs: health.NewServer()}
	s.addr, _ = StartReg(impl, func(g *grpc.Server) {
		s.gs = g
		hpb.RegisterHealthServer(g, s.hs)
	}, opts...)
	return s
}

func main() {
	Sec("一:服务端关闭时,一个正在处理的调用(handler 要 500 ms):Stop vs GracefulStop,客户端看到什么、Stop 调用本身用了多久")
	for _, graceful := range []bool{false, true} {
		s := start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			time.Sleep(500 * time.Millisecond)
			return &pb.Resp{}, nil
		}})
		conn, _ := grpc.NewClient(s.addr, insec)
		cl := pb.NewDemoClient(conn)
		res := make(chan string, 1)
		t0 := time.Now()
		go func() {
			_, err := cl.Unary(context.Background(), &pb.Req{})
			res <- fmt.Sprintf("%s,%s 后返回", em(err), Ms(time.Since(t0)))
		}()
		time.Sleep(100 * time.Millisecond)
		ts := time.Now()
		name := "Stop()"
		if graceful {
			name = "GracefulStop()"
			s.gs.GracefulStop()
		} else {
			s.gs.Stop()
		}
		P("%-15s 调用本身用了 %s;客户端的在途调用:%s", name, Ms(time.Since(ts)), <-res)
		conn.Close()
	}

	Sec("二:GracefulStop 会一直等到所有在途的流结束:有一个永不结束的服务端流时,GracefulStop 等 2 秒仍没有返回;之后改成“先 GracefulStop,等不到就 Stop”")
	{
		s := start(&DemoServer{OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			st.Send(&pb.Resp{})
			<-st.Context().Done() // 永不结束,直到被取消
			return st.Context().Err()
		}})
		conn, _ := grpc.NewClient(s.addr, insec)
		cl := pb.NewDemoClient(conn)
		stream, _ := cl.ServerStream(context.Background(), &pb.Req{})
		stream.Recv()
		done := make(chan struct{})
		t0 := time.Now()
		go func() { s.gs.GracefulStop(); close(done) }()
		select {
		case <-done:
			P("GracefulStop 在 %s 后返回", Ms(time.Since(t0)))
		case <-time.After(2 * time.Second):
			P("GracefulStop 等了 %s,仍然没有返回", Ms(time.Since(t0)))
		}
		t1 := time.Now()
		s.gs.Stop()
		<-done
		_, err := stream.Recv()
		P("再调用 Stop():GracefulStop 在 %s 后才返回;长流的客户端:%s", Ms(time.Since(t0)), em(err))
		_ = t1
		conn.Close()
	}

	Sec("三:滚动重启的失败数:2 个后端 + round_robin,16 个客户端 goroutine 连续调用(handler 20 ms),1 秒时关掉后端 0,共 3 秒;三种关闭方式各自的失败调用数")
	for _, mode := range []string{"Stop()", "GracefulStop()", "先 health.Shutdown,等 300 ms,再 GracefulStop()"} {
		var hits [2]atomic.Int64
		var ss []*srv
		var addrs []resolver.Address
		for i := 0; i < 2; i++ {
			i := i
			s := start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				hits[i].Add(1)
				time.Sleep(20 * time.Millisecond)
				return &pb.Resp{}, nil
			}})
			ss = append(ss, s)
			addrs = append(addrs, resolver.Address{Addr: s.addr})
		}
		r := manual.NewBuilderWithScheme("demo")
		r.InitialState(resolver.State{Addresses: addrs})
		conn, _ := grpc.NewClient("demo:///svc", insec, grpc.WithResolvers(r), grpc.WithDefaultServiceConfig(`{"loadBalancingConfig":[{"round_robin":{}}],"healthCheckConfig":{"serviceName":""}}`))
		cl := pb.NewDemoClient(conn)
		var total, failed atomic.Int64
		var firstErr atomic.Value
		var stopAll atomic.Bool
		var wg sync.WaitGroup
		for w := 0; w < 16; w++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for !stopAll.Load() {
					ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
					_, err := cl.Unary(ctx, &pb.Req{})
					cancel()
					total.Add(1)
					if err != nil {
						failed.Add(1)
						firstErr.CompareAndSwap(nil, em(err))
					}
				}
			}()
		}
		time.Sleep(1 * time.Second)
		before := hits[0].Load()
		ts := time.Now()
		switch mode {
		case "Stop()":
			ss[0].gs.Stop()
		case "GracefulStop()":
			ss[0].gs.GracefulStop()
		default:
			ss[0].hs.Shutdown()
			time.Sleep(300 * time.Millisecond)
			ss[0].gs.GracefulStop()
		}
		took := time.Since(ts)
		time.Sleep(2 * time.Second)
		stopAll.Store(true)
		wg.Wait()
		fe, _ := firstErr.Load().(string)
		if fe == "" {
			fe = "(没有失败)"
		}
		P("%-34s 总调用 %5d,失败 %2d;关闭动作用了 %s;关闭之后后端 0 又收到 %d 次、后端 1 共 %d 次;第一个失败:%s", mode, total.Load(), failed.Load(), Ms(took), hits[0].Load()-before, hits[1].Load(), fe)
		conn.Close()
		ss[1].gs.Stop()
	}

	Sec("四:Stop() 不等 handler 返回:handler 里 time.Sleep(1 秒) 且不看 ctx,Stop() 要多久返回;加上 grpc.WaitForHandlers(true) 之后呢")
	for _, wait := range []bool{false, true} {
		var running atomic.Int64
		var opts []grpc.ServerOption
		if wait {
			opts = append(opts, grpc.WaitForHandlers(true))
		}
		s := start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			running.Add(1)
			defer running.Add(-1)
			time.Sleep(1 * time.Second)
			return &pb.Resp{}, nil
		}}, opts...)
		conn, _ := grpc.NewClient(s.addr, insec)
		go pb.NewDemoClient(conn).Unary(context.Background(), &pb.Req{})
		time.Sleep(200 * time.Millisecond)
		t0 := time.Now()
		s.gs.Stop()
		el := time.Since(t0)
		P("WaitForHandlers(%-5v) Stop() 用了 %s;Stop 返回时仍在运行的 handler %d 个", wait, Ms(el), running.Load())
		conn.Close()
		time.Sleep(1 * time.Second)
	}
}
