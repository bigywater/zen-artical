package main

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	. "grpcgo/common"
	"grpcgo/pb"
)

type cfg struct {
	name string
	opts []grpc.DialOption
	win  int
}

var cfgs = []cfg{
	{"默认(动态窗口,BDP 估计)", nil, 0},
	{"静态窗口 64 KiB", []grpc.DialOption{grpc.WithInitialWindowSize(64 << 10), grpc.WithInitialConnWindowSize(64 << 10)}, 64 << 10},
	{"静态窗口 256 KiB", []grpc.DialOption{grpc.WithInitialWindowSize(256 << 10), grpc.WithInitialConnWindowSize(256 << 10)}, 256 << 10},
	{"静态窗口 1 MiB", []grpc.DialOption{grpc.WithInitialWindowSize(1 << 20), grpc.WithInitialConnWindowSize(1 << 20)}, 1 << 20},
	{"静态窗口 4 MiB", []grpc.DialOption{grpc.WithInitialWindowSize(4 << 20), grpc.WithInitialConnWindowSize(4 << 20)}, 4 << 20},
}

func newClient(tap *Tap, c cfg) (pb.DemoClient, func()) {
	conn, _ := grpc.NewClient(tap.Addr, append([]grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}, c.opts...)...)
	return pb.NewDemoClient(conn), func() { conn.Close() }
}

// bulk 从服务端流式接收 n 条 256 KiB 的消息,返回吞吐(MiB/s)。
func bulk(cl pb.DemoClient, n int) float64 {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	t0 := time.Now()
	st, _ := cl.ServerStream(ctx, &pb.Req{N: int32(n)})
	got := 0
	for {
		if _, err := st.Recv(); err != nil {
			break
		}
		got++
	}
	return float64(got) * 0.25 / time.Since(t0).Seconds()
}

func main() {
	srv := &DemoServer{OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		payload := make([]byte, 256<<10)
		for i := 0; i < int(r.N); i++ {
			if err := st.Send(&pb.Resp{Payload: payload}); err != nil {
				return err
			}
		}
		return nil
	}}
	addr, stop := Start(srv)
	defer stop()
	tap := NewTap(addr)
	defer tap.Close()

	run := func(rtt time.Duration, total int, show bool) {
		tap.DelayCS, tap.DelaySC = rtt/2, rtt/2
		P("%-24s %-12s %-14s %s", "客户端设置", "吞吐 MiB/s", "窗口/RTT 的理论值", "")
		for _, c := range cfgs {
			cl, closeFn := newClient(tap, c)
			cl.Unary(context.Background(), &pb.Req{}) // 先建立连接并等 SETTINGS 往返
			th := bulk(cl, total)
			theory := "—"
			if c.win > 0 && rtt > 0 {
				theory = fmt.Sprintf("%.1f", float64(c.win)/1048576/rtt.Seconds())
			}
			P("%-24s %-12.1f %-14s", c.name, th, theory)
			closeFn()
		}
	}

	Sec("一:没有延迟(本机回环)传 16 MiB(64 条 × 256 KiB)的吞吐")
	run(0, 64, true)
	Sec("二:往返延迟 RTT = 5 ms(代理在两个方向各延迟 2.5 ms),传 16 MiB")
	run(5*time.Millisecond, 64, true)
	Sec("三:往返延迟 RTT = 20 ms(两个方向各 10 ms),传 8 MiB(32 条)")
	run(20*time.Millisecond, 32, true)

	Sec("四:默认(动态窗口)模式下,窗口怎么长大:RTT = 20 ms,传 8 MiB 时客户端发出的连接级 WINDOW_UPDATE 增量与 PING 的次数,以及静态模式下的 SETTINGS")
	{
		tap.DelayCS, tap.DelaySC = 10*time.Millisecond, 10*time.Millisecond
		cl, closeFn := newClient(tap, cfgs[0])
		cl.Unary(context.Background(), &pb.Req{})
		time.Sleep(100 * time.Millisecond)
		tap.Reset()
		th := bulk(cl, 32)
		time.Sleep(200 * time.Millisecond)
		var incs []string
		pings, wu := 0, 0
		for _, e := range tap.Snapshot() {
			if e.Dir == "C→S" && e.Type == "WINDOW_UPDATE" && e.Stream == 0 {
				wu++
				if len(incs) < 10 {
					incs = append(incs, strings.TrimPrefix(e.Info, "增量 "))
				}
			}
			if e.Type == "PING" && e.Dir == "C→S" && !strings.Contains(e.Flags, "ACK") {
				pings++
			}
		}
		P("吞吐 %.1f MiB/s;连接级 WINDOW_UPDATE 共 %d 个,前 10 个的增量(字节):%v;客户端发出的 PING %d 个", th, wu, incs, pings)
		closeFn()
		tap.DelayCS, tap.DelaySC = 0, 0
		for _, c := range []cfg{cfgs[0], cfgs[1], cfgs[3]} {
			tap.Reset()
			cl, closeFn := newClient(tap, c)
			cl.Unary(context.Background(), &pb.Req{})
			time.Sleep(100 * time.Millisecond)
			for _, e := range tap.Snapshot() {
				if e.Dir == "C→S" && e.Type == "SETTINGS" && e.Flags == "" {
					P("%-24s 客户端 SETTINGS:%q", c.name, e.Info)
					break
				}
			}
			closeFn()
		}
	}

	Sec("五:4 个并发的流共享一条连接(每个流 4 MiB,RTT = 5 ms):流窗口都是 1 MiB,连接窗口分别取 64 KiB 和 4 MiB 时的总吞吐")
	tap.DelayCS, tap.DelaySC = 2500*time.Microsecond, 2500*time.Microsecond
	for _, cw := range []int32{64 << 10, 4 << 20} {
		conn, _ := grpc.NewClient(tap.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithInitialWindowSize(1<<20), grpc.WithInitialConnWindowSize(cw))
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		var wg sync.WaitGroup
		t0 := time.Now()
		for i := 0; i < 4; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); bulk(cl, 16) }()
		}
		wg.Wait()
		el := time.Since(t0)
		P("连接窗口 %-8d 字节:4 × 4 MiB 共 16 MiB,用时 %s,总吞吐 %.1f MiB/s", cw, Ms(el), 16/el.Seconds())
		conn.Close()
	}

	Sec("六:小消息不受窗口影响:RTT = 5 ms,200 次串行的 Unary(小请求),默认窗口与静态 64 KiB 窗口的平均耗时")
	tap.DelayCS, tap.DelaySC = 2500*time.Microsecond, 2500*time.Microsecond
	for _, c := range cfgs[:2] {
		cl, closeFn := newClient(tap, c)
		cl.Unary(context.Background(), &pb.Req{})
		t0 := time.Now()
		for i := 0; i < 200; i++ {
			cl.Unary(context.Background(), &pb.Req{Msg: "x"})
		}
		P("%-24s 200 次 Unary 平均 %.2f ms/次", c.name, float64(time.Since(t0).Microseconds())/200/1000)
		closeFn()
	}
}
