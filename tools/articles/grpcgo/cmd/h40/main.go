package main

import (
	"context"
	"fmt"
	"io"
	"sort"
	"strings"
	"sync"
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
	if len(m) > 80 {
		m = m[:80] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

func ka(age, grace, idle time.Duration) grpc.ServerOption {
	return grpc.KeepaliveParams(keepalive.ServerParameters{MaxConnectionAge: age, MaxConnectionAgeGrace: grace, MaxConnectionIdle: idle})
}

func goaways(tap *Tap) []Event {
	var o []Event
	for _, e := range tap.Snapshot() {
		if e.Dir == "S→C" && e.Type == "GOAWAY" {
			o = append(o, e)
		}
	}
	return o
}

func main() {
	Sec("一:到期时线上发生什么:MaxConnectionAge = 1 秒(宽限默认=无限),连接上有一个已完成的调用;GOAWAY 帧的时刻和内容")
	{
		addr, stop := Start(&DemoServer{}, ka(1*time.Second, 0, 0))
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		pb.NewDemoClient(conn).Unary(context.Background(), &pb.Req{})
		time.Sleep(2 * time.Second)
		for _, e := range goaways(tap) {
			P("%.3f 秒:S→C GOAWAY %s", e.T.Seconds(), e.Info)
		}
		P("TCP 连接数 %d;客户端状态 %s", tap.Conns, conn.GetState())
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("二:抖动:MaxConnectionAge = 2 秒,新建 30 条连接(各发一次调用),第一个 GOAWAY 到达的时刻(源码:±10% 的随机抖动)")
	{
		addr, stop := Start(&DemoServer{}, ka(2*time.Second, 0, 0))
		tap := NewTap(addr)
		var conns []*grpc.ClientConn
		t0 := time.Now()
		for i := 0; i < 30; i++ {
			c, _ := grpc.NewClient(tap.Addr, insec)
			c.Connect()
			conns = append(conns, c)
		}
		time.Sleep(2800 * time.Millisecond)
		var ts []float64
		for _, e := range goaways(tap) {
			if strings.Contains(e.Info, "2147483647") {
				ts = append(ts, e.T.Seconds())
			}
		}
		sort.Float64s(ts)
		sum := 0.0
		for _, v := range ts {
			sum += v
		}
		_ = t0
		if len(ts) == 0 {
			P("没有观察到 GOAWAY")
		} else {
			P("观察到 %d 个连接的第一个 GOAWAY:最早 %.2f 秒、最晚 %.2f 秒、平均 %.2f 秒(MaxConnectionAge = 2 秒)", len(ts), ts[0], ts[len(ts)-1], sum/float64(len(ts)))
		}
		for _, c := range conns {
			c.Close()
		}
		tap.Close()
		stop()
	}

	Sec("三:到期时还有长调用:服务端流(一共 4 秒,每 500 ms 发一条)。MaxConnectionAge = 1 秒,宽限 = 默认(无限)vs 宽限 1 秒:服务端第一次发送失败的时刻、客户端 Recv 出错的时刻与错误")
	for _, grace := range []time.Duration{0, 1 * time.Second} {
		var sendFail atomic.Int64
		var t0 atomic.Value
		addr, stop := Start(&DemoServer{OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			for i := 0; i < 8; i++ {
				if err := st.Send(&pb.Resp{N: int32(i)}); err != nil {
					sendFail.Store(time.Since(t0.Load().(time.Time)).Milliseconds())
					return err
				}
				time.Sleep(500 * time.Millisecond)
			}
			return nil
		}}, ka(1*time.Second, grace, 0))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		t0.Store(time.Now())
		st, _ := cl.ServerStream(context.Background(), &pb.Req{})
		n := 0
		var err error
		for {
			if _, err = st.Recv(); err != nil {
				break
			}
			n++
		}
		name := "宽限默认(无限)"
		if grace > 0 {
			name = "宽限 1 秒"
		}
		res := em(err)
		if err == io.EOF {
			res = "io.EOF(流正常结束,状态为 OK)"
		}
		sf := "服务端发送一直成功"
		if sendFail.Load() > 0 {
			sf = fmt.Sprintf("服务端第一次发送失败在 %.2f 秒", float64(sendFail.Load())/1000)
		}
		P("%-14s 客户端 %.2f 秒时结束、收到 %d 条消息(服务端共发 8 条),结束时:%s;%s", name, time.Since(t0.Load().(time.Time)).Seconds(), n, res, sf)
		conn.Close()
		stop()
	}

	Sec("四:持续负载下的连接更替:8 个 goroutine 连续调用 4 秒;服务端 MaxConnectionAge = 500 ms(宽限 1 秒) vs 没有设置——建立的连接数、失败调用数、p99 延迟")
	for _, withAge := range []bool{false, true} {
		var so []grpc.ServerOption
		if withAge {
			so = append(so, ka(500*time.Millisecond, 1*time.Second, 0))
		}
		addr, stop := Start(&DemoServer{}, so...)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		var failed, total atomic.Int64
		var mu sync.Mutex
		var ds []time.Duration
		var stopAll atomic.Bool
		var wg sync.WaitGroup
		for w := 0; w < 8; w++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				var mine []time.Duration
				for !stopAll.Load() {
					s := time.Now()
					ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
					_, err := cl.Unary(ctx, &pb.Req{})
					cancel()
					mine = append(mine, time.Since(s))
					total.Add(1)
					if err != nil {
						failed.Add(1)
					}
				}
				mu.Lock()
				ds = append(ds, mine...)
				mu.Unlock()
			}()
		}
		time.Sleep(4 * time.Second)
		stopAll.Store(true)
		wg.Wait()
		sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
		name := "没有设置"
		if withAge {
			name = "MaxConnectionAge 500 ms"
		}
		P("%-24s 总调用 %6d;失败 %d;TCP 连接共 %d 条;p50 %d µs、p99 %d µs、最慢 %d µs", name, total.Load(), failed.Load(), tap.Conns, ds[len(ds)/2].Microseconds(), ds[len(ds)*99/100].Microseconds(), ds[len(ds)-1].Microseconds())
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("五:MaxConnectionIdle(只回收空闲连接)与 MaxConnectionAge 的区别:每秒调用一次,持续 4 秒;MaxConnectionIdle = 300 ms vs MaxConnectionAge = 1.5 秒——TCP 连接数")
	for _, mode := range []string{"MaxConnectionIdle = 300 ms", "MaxConnectionAge = 1.5 秒"} {
		var so grpc.ServerOption
		if strings.HasPrefix(mode, "MaxConnectionIdle") {
			so = ka(0, 0, 300*time.Millisecond)
		} else {
			so = ka(1500*time.Millisecond, 0, 0)
		}
		addr, stop := Start(&DemoServer{}, so)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		var fails int
		for i := 0; i < 4; i++ {
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			if _, err := cl.Unary(ctx, &pb.Req{}); err != nil {
				fails++
			}
			cancel()
			time.Sleep(1 * time.Second)
		}
		P("%-26s 4 次调用(间隔 1 秒):失败 %d;TCP 连接共 %d 条;最后的客户端状态 %s", mode, fails, tap.Conns, conn.GetState())
		conn.Close()
		tap.Close()
		stop()
	}
}
