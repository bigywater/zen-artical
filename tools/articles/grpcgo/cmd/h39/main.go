package main

import (
	"context"
	"fmt"
	"net"
	"strings"
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

type tl struct {
	mu   sync.Mutex
	t0   time.Time
	recs []string
	cur  connectivity.State
}

func watch(conn *grpc.ClientConn, t0 time.Time) (*tl, func()) {
	w := &tl{t0: t0}
	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		s := conn.GetState()
		w.add(s)
		for conn.WaitForStateChange(ctx, s) {
			s = conn.GetState()
			w.add(s)
		}
	}()
	return w, cancel
}
func (w *tl) add(s connectivity.State) {
	w.mu.Lock()
	w.cur = s
	w.recs = append(w.recs, fmt.Sprintf("%.2fs %s", time.Since(w.t0).Seconds(), s))
	w.mu.Unlock()
}
func (w *tl) String() string {
	w.mu.Lock()
	defer w.mu.Unlock()
	return strings.Join(w.recs, " → ")
}

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	m := st.Message()
	if len(m) > 90 {
		m = m[:90] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

func call(cl pb.DemoClient, wait time.Duration, opts ...grpc.CallOption) error {
	ctx, cancel := context.WithTimeout(context.Background(), wait)
	defer cancel()
	_, err := cl.Unary(ctx, &pb.Req{}, opts...)
	return err
}

func main() {
	Sec("一:状态时间线(退避设为基础 500 ms、倍数 1.6、不抖动):NewClient → Connect() → 服务端 Stop → 发一次调用(服务端已不在)→ 重新起服务端 → 再调用")
	{
		port := FreePort()
		startAt := func() func() {
			l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
			if err != nil {
				panic(err)
			}
			gs := grpc.NewServer()
			pb.RegisterDemoServer(gs, &DemoServer{})
			go gs.Serve(l)
			return gs.Stop
		}
		stop := startAt()
		t0 := time.Now()
		conn, _ := grpc.NewClient(fmt.Sprintf("127.0.0.1:%d", port), insec, grpc.WithConnectParams(grpc.ConnectParams{Backoff: backoff.Config{BaseDelay: 500 * time.Millisecond, Multiplier: 1.6, Jitter: 0, MaxDelay: 5 * time.Second}, MinConnectTimeout: 3 * time.Second}))
		w, cancel := watch(conn, t0)
		cl := pb.NewDemoClient(conn)
		time.Sleep(300 * time.Millisecond)
		conn.Connect()
		time.Sleep(300 * time.Millisecond)
		stop()
		time.Sleep(300 * time.Millisecond)
		P("调用(服务端不在)→ %s", em(call(cl, 200*time.Millisecond)))
		time.Sleep(1800 * time.Millisecond)
		stop = startAt()
		P("服务端重新启动的时刻:%.2fs", time.Since(t0).Seconds())
		time.Sleep(1500 * time.Millisecond)
		P("服务端回来后的调用(fail-fast)→ %s", em(call(cl, time.Second)))
		time.Sleep(200 * time.Millisecond)
		P("状态时间线(退避设为基础 500 ms、不抖动):%s", w)
		cancel()
		conn.Close()
		stop()
	}

	Sec("二:对端接受 TCP 但不做 HTTP/2 握手(假服务端只 Accept、不回应):MinConnectTimeout = 1 秒,状态多久变成 TRANSIENT_FAILURE")
	{
		l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
		go func() {
			var keep []net.Conn
			for {
				c, err := l.Accept()
				if err != nil {
					return
				}
				keep = append(keep, c)
			}
		}()
		t0 := time.Now()
		conn, _ := grpc.NewClient(l.Addr().String(), insec, grpc.WithConnectParams(grpc.ConnectParams{Backoff: backoff.Config{BaseDelay: 500 * time.Millisecond, Multiplier: 1.6, MaxDelay: 5 * time.Second}, MinConnectTimeout: 1 * time.Second}))
		w, cancel := watch(conn, t0)
		conn.Connect()
		time.Sleep(3500 * time.Millisecond)
		P("状态时间线:%s", w)
		P("这期间发一次 fail-fast 调用(deadline 5 秒):%s", func() string {
			s := time.Now()
			err := call(pb.NewDemoClient(conn), 5*time.Second)
			return fmt.Sprintf("%s(%s 后返回)", em(err), Ms(time.Since(s)))
		}())
		cancel()
		conn.Close()
		l.Close()
	}

	Sec("三:拒绝连接(端口没人监听):状态在 TRANSIENT_FAILURE 与 CONNECTING 之间的退避循环(基础 500 ms、倍数 2、不抖动),观察 4 秒;fail-fast 与 WaitForReady 的调用")
	{
		l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
		addr := l.Addr().String()
		l.Close()
		t0 := time.Now()
		conn, _ := grpc.NewClient(addr, insec, grpc.WithConnectParams(grpc.ConnectParams{Backoff: backoff.Config{BaseDelay: 500 * time.Millisecond, Multiplier: 2, Jitter: 0, MaxDelay: 5 * time.Second}, MinConnectTimeout: time.Second}))
		w, cancel := watch(conn, t0)
		conn.Connect()
		time.Sleep(4 * time.Second)
		P("状态时间线(4 秒内):%s", w)
		cl := pb.NewDemoClient(conn)
		s := time.Now()
		err := call(cl, 5*time.Second)
		P("fail-fast 调用:%s(%s 后返回)", em(err), Ms(time.Since(s)))
		s = time.Now()
		err = call(cl, 800*time.Millisecond, grpc.WaitForReady(true))
		P("WaitForReady(true),deadline 800 ms:%s(%s 后返回)", em(err), Ms(time.Since(s)))
		cancel()
		conn.Close()
	}

	Sec("四:Close 之后:状态 SHUTDOWN,再调用得到什么")
	{
		addr, stop := Start(&DemoServer{})
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		call(cl, time.Second)
		conn.Close()
		P("Close 之后状态:%s;调用:%s;WaitForReady 调用:%s", conn.GetState(), em(call(cl, time.Second)), em(call(cl, time.Second, grpc.WaitForReady(true))))
		P("再 Close 一次:%v", conn.Close())
		stop()
	}

	Sec("五:多个地址时通道的状态:round_robin 下 2 个后端,依次停掉一个、再停掉另一个(通道状态是各子连接状态的汇总);pick_first 对照")
	for _, lb := range []string{"round_robin", "pick_first"} {
		a1, s1 := Start(&DemoServer{})
		a2, s2 := Start(&DemoServer{})
		r := manual.NewBuilderWithScheme("demo")
		r.InitialState(resolver.State{Addresses: []resolver.Address{{Addr: a1}, {Addr: a2}}})
		conn, _ := grpc.NewClient("demo:///svc", insec, grpc.WithResolvers(r), grpc.WithDefaultServiceConfig(fmt.Sprintf(`{"loadBalancingConfig":[{"%s":{}}]}`, lb)))
		cl := pb.NewDemoClient(conn)
		t0 := time.Now()
		w, cancel := watch(conn, t0)
		call(cl, time.Second)
		time.Sleep(200 * time.Millisecond)
		s1()
		time.Sleep(300 * time.Millisecond)
		e1 := call(cl, time.Second)
		st1 := conn.GetState()
		s2()
		time.Sleep(300 * time.Millisecond)
		e2 := call(cl, time.Second)
		st2 := conn.GetState()
		time.Sleep(300 * time.Millisecond)
		P("%-11s 停掉后端 1 之后:调用 %s,通道状态 %s;再停掉后端 2:调用 %s,通道状态 %s", lb, em(e1), st1, em(e2), st2)
		P("    状态时间线:%s", w)
		cancel()
		conn.Close()
	}
}
