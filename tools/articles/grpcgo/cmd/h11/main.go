package main

import (
	"context"
	"fmt"
	"net"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/backoff"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/resolver"
	"google.golang.org/grpc/resolver/manual"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func main() {
	Sec("一:grpc.NewClient 是惰性的:创建时不连接,第一次调用(或 Connect())才建 TCP 连接")
	{
		addr, stop := Start(&DemoServer{})
		defer stop()
		tap := NewTap(addr)
		defer tap.Close()
		conn, _ := grpc.NewClient(tap.Addr, insec)
		time.Sleep(200 * time.Millisecond)
		P("NewClient 之后 200 ms:状态 %s;代理看到的 TCP 连接 %d 条", conn.GetState(), tap.Conns)
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		P("第一次调用之后:状态 %s;TCP 连接 %d 条", conn.GetState(), tap.Conns)
		for i := 0; i < 20; i++ {
			cl.Unary(context.Background(), &pb.Req{})
		}
		P("再调用 20 次之后:状态 %s;TCP 连接仍是 %d 条", conn.GetState(), tap.Conns)
		conn.Close()
		conn2, _ := grpc.NewClient(tap.Addr, insec)
		conn2.Connect()
		time.Sleep(200 * time.Millisecond)
		P("另一个 ClientConn 只调用 Connect(),不发请求:状态 %s;TCP 连接共 %d 条", conn2.GetState(), tap.Conns)
		conn2.Close()
	}

	Sec("二:多个后端地址:pick_first(默认)只连一个,round_robin 同时连所有地址")
	{
		var addrs []string
		var taps []*Tap
		var stops []func()
		for i := 0; i < 3; i++ {
			a, s := Start(&DemoServer{})
			stops = append(stops, s)
			t := NewTap(a)
			taps = append(taps, t)
			addrs = append(addrs, t.Addr)
		}
		for _, policy := range []string{"pick_first", "round_robin"} {
			for _, t := range taps {
				t.ResetConns()
			}
			r := manual.NewBuilderWithScheme("demo")
			var as []resolver.Address
			for _, a := range addrs {
				as = append(as, resolver.Address{Addr: a})
			}
			r.InitialState(resolver.State{Addresses: as})
			conn, _ := grpc.NewClient("demo:///svc", insec, grpc.WithResolvers(r), grpc.WithDefaultServiceConfig(fmt.Sprintf(`{"loadBalancingConfig":[{"%s":{}}]}`, policy)))
			cl := pb.NewDemoClient(conn)
			for i := 0; i < 30; i++ {
				cl.Unary(context.Background(), &pb.Req{})
			}
			time.Sleep(100 * time.Millisecond)
			var cs []int
			for _, t := range taps {
				cs = append(cs, t.Conns)
			}
			P("%-12s 30 次调用之后,三个后端各自收到的 TCP 连接数 %v", policy, cs)
			conn.Close()
			time.Sleep(100 * time.Millisecond)
		}
		for _, s := range stops {
			s()
		}
	}

	Sec("三:连接不上时的重连退避:一个“接受连接后立刻关闭”的假后端,记录客户端每次尝试连接的时刻(默认退避:基础 1 s、倍数 1.6、抖动 0.2)")
	attempt := func(name string, opts ...grpc.DialOption) {
		port := FreePort()
		l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
		var mu sync.Mutex
		var ts []time.Duration
		t0 := time.Now()
		go func() {
			for {
				c, err := l.Accept()
				if err != nil {
					return
				}
				mu.Lock()
				ts = append(ts, time.Since(t0))
				mu.Unlock()
				c.Close()
			}
		}()
		conn, _ := grpc.NewClient(l.Addr().String(), append([]grpc.DialOption{insec}, opts...)...)
		conn.Connect()
		time.Sleep(11 * time.Second)
		mu.Lock()
		var s string
		for i, d := range ts {
			if i > 0 {
				s += fmt.Sprintf("  (+%.2fs)", (d - ts[i-1]).Seconds())
			}
			s += fmt.Sprintf(" %.2fs", d.Seconds())
		}
		P("%s:11 秒内尝试 %d 次,时刻:%s", name, len(ts), s)
		P("   最后状态 %s", conn.GetState())
		mu.Unlock()
		conn.Close()
		l.Close()
	}
	attempt("默认退避")
	attempt("自定义退避(基础 100 ms、倍数 2、抖动 0、最大 1 s)", grpc.WithConnectParams(grpc.ConnectParams{Backoff: backoff.Config{BaseDelay: 100 * time.Millisecond, Multiplier: 2, Jitter: 0, MaxDelay: time.Second}, MinConnectTimeout: 20 * time.Second}))

	Sec("四:连接断开后,正在进行的调用、退避期间的新调用、恢复之后的新调用各是什么结果")
	{
		srv := &DemoServer{}
		srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if r.Msg == "slow" {
				time.Sleep(2 * time.Second)
			}
			return &pb.Resp{Msg: "ok"}, nil
		}
		port := FreePort()
		start := func() func() {
			l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
			if err != nil {
				panic(err)
			}
			s := grpc.NewServer()
			pb.RegisterDemoServer(s, srv)
			go s.Serve(l)
			return s.Stop
		}
		stop := start()
		conn, _ := grpc.NewClient(fmt.Sprintf("127.0.0.1:%d", port), insec, grpc.WithConnectParams(grpc.ConnectParams{Backoff: backoff.Config{BaseDelay: 300 * time.Millisecond, Multiplier: 1.6, MaxDelay: 2 * time.Second}, MinConnectTimeout: 5 * time.Second}))
		defer conn.Close()
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		res := make(chan string, 1)
		go func() {
			_, err := cl.Unary(context.Background(), &pb.Req{Msg: "slow"})
			s, _ := status.FromError(err)
			res <- fmt.Sprintf("code=%s message=%q", s.Code(), s.Message())
		}()
		time.Sleep(200 * time.Millisecond)
		t0 := time.Now()
		stop() // 服务端直接 Stop:关闭所有连接
		P("服务端 Stop 之后正在进行的调用:%s(%s 后返回)", <-res, Ms(time.Since(t0)))
		time.Sleep(100 * time.Millisecond)
		P("连接状态 %s", conn.GetState())
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		t1 := time.Now()
		_, err := cl.Unary(ctx, &pb.Req{})
		cancel()
		s, _ := status.FromError(err)
		P("退避期间的新调用(fail-fast):code=%s,%s 返回", s.Code(), Ms(time.Since(t1)))
		stop = start()
		defer stop()
		ctx, cancel = context.WithTimeout(context.Background(), 5*time.Second)
		t1 = time.Now()
		_, err = cl.Unary(ctx, &pb.Req{}, grpc.WaitForReady(true))
		cancel()
		P("服务端重启后用 WaitForReady(true) 调用:err=%v,等了 %s(退避结束后重连成功才发出)", err, Ms(time.Since(t1)))
		P("连接状态 %s", conn.GetState())
	}

	Sec("五:服务端 GracefulStop:发 GOAWAY,在途调用能完成,客户端对新调用的处理")
	{
		srv := &DemoServer{}
		srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if r.Msg == "slow" {
				time.Sleep(500 * time.Millisecond)
			}
			return &pb.Resp{Msg: "ok"}, nil
		}
		port := FreePort()
		l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
		s := grpc.NewServer()
		pb.RegisterDemoServer(s, srv)
		go s.Serve(l)
		tap := NewTap(l.Addr().String())
		defer tap.Close()
		conn, _ := grpc.NewClient(tap.Addr, insec)
		defer conn.Close()
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		res := make(chan string, 1)
		go func() {
			_, err := cl.Unary(context.Background(), &pb.Req{Msg: "slow"})
			res <- fmt.Sprint(err)
		}()
		time.Sleep(100 * time.Millisecond)
		tap.Reset()
		t0 := time.Now()
		go s.GracefulStop()
		time.Sleep(100 * time.Millisecond)
		_, err := cl.Unary(context.Background(), &pb.Req{})
		st, _ := status.FromError(err)
		P("GracefulStop 开始后发起的新调用:code=%s message=%q", st.Code(), st.Message())
		P("在途的慢调用:err=%s,%s 后完成", <-res, Ms(time.Since(t0)))
		for _, e := range tap.Snapshot() {
			if e.Type == "GOAWAY" {
				P("线上 %s GOAWAY:%s", e.Dir, e.Info)
			}
		}
		P("连接状态 %s", conn.GetState())
	}

	Sec("六:空闲超时:WithIdleTimeout(300 ms) —— 连接空闲这么久后客户端主动关闭 TCP 连接,下一次调用重新建立")
	{
		addr, stop := Start(&DemoServer{})
		defer stop()
		tap := NewTap(addr)
		defer tap.Close()
		conn, _ := grpc.NewClient(tap.Addr, insec, grpc.WithIdleTimeout(300*time.Millisecond))
		defer conn.Close()
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		P("第一次调用之后:状态 %s,TCP 连接 %d 条", conn.GetState(), tap.Conns)
		time.Sleep(700 * time.Millisecond)
		P("空闲 700 ms 后:状态 %s", conn.GetState())
		t0 := time.Now()
		cl.Unary(context.Background(), &pb.Req{})
		P("再调用一次:%s,状态 %s,TCP 连接累计 %d 条(重新建立了连接)", Ms(time.Since(t0)), conn.GetState(), tap.Conns)
		_ = connectivity.Idle
	}
}
