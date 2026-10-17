package main

import (
	"context"
	"fmt"
	"strings"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func remaining(ctx context.Context) string {
	d, ok := ctx.Deadline()
	if !ok {
		return "无截止时间"
	}
	return fmt.Sprintf("%dms", time.Until(d).Milliseconds())
}

func dial(addr string) pb.DemoClient {
	c, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	return pb.NewDemoClient(c)
}

func main() {
	Sec("一:不同的截止时间,线上 grpc-timeout 头的写法(数字最多 8 位,加一个单位字母:n 纳秒、u 微秒、m 毫秒、S 秒、M 分、H 时)")
	{
		addr, stop := Start(&DemoServer{})
		defer stop()
		tap := NewTap(addr)
		defer tap.Close()
		cl := dial(tap.Addr)
		cl.Unary(context.Background(), &pb.Req{})
		for _, d := range []time.Duration{50 * time.Millisecond, time.Second, 5 * time.Second, 90 * time.Second, 2 * time.Hour, 100 * time.Hour} {
			tap.Reset()
			ctx, cancel := context.WithTimeout(context.Background(), d)
			cl.Unary(ctx, &pb.Req{})
			cancel()
			time.Sleep(20 * time.Millisecond)
			hv := ""
			for _, e := range tap.Snapshot() {
				if e.Dir == "C→S" && e.Type == "HEADERS" {
					for _, kv := range strings.Split(e.Info, "; ") {
						if strings.HasPrefix(kv, "grpc-timeout") {
							hv = kv
						}
					}
				}
			}
			P("context 超时 %-10v → %s", d, hv)
		}
		tap.Reset()
		cl.Unary(context.Background(), &pb.Req{})
		time.Sleep(20 * time.Millisecond)
		found := false
		for _, e := range tap.Snapshot() {
			if e.Dir == "C→S" && e.Type == "HEADERS" && strings.Contains(e.Info, "grpc-timeout") {
				found = true
			}
		}
		P("不设截止时间(context.Background())→ 请求头里有 grpc-timeout:%v", found)
	}

	Sec("二:A → B → C 三层调用,客户端设 1 秒;A、B 各自先处理 100 ms 再用收到的 ctx 调下一层。每一层看到的剩余时间")
	var addrs [3]string
	var stops [3]func()
	cls := make([]pb.DemoClient, 3)
	trace := &atomic.Value{}
	_ = trace
	mk := func(i int, pass bool) *DemoServer {
		return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			me := fmt.Sprintf("%c 看到剩余 %s", 'A'+i, remaining(ctx))
			time.Sleep(100 * time.Millisecond)
			if i < 2 {
				cctx := ctx
				if !pass {
					cctx = context.Background()
				}
				resp, err := cls[i+1].Unary(cctx, &pb.Req{Msg: r.Msg})
				if err != nil {
					return nil, err
				}
				return &pb.Resp{Msg: me + " | " + resp.Msg}, nil
			}
			return &pb.Resp{Msg: me}, nil
		}}
	}
	for i := 2; i >= 0; i-- {
		addrs[i], stops[i] = Start(mk(i, true))
		defer stops[i]()
		if i < 2 {
		}
		cls[i] = dial(addrs[i])
	}
	// 每层要用下一层的客户端,上面循环顺序保证 cls[i+1] 已建立
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	resp, err := cls[0].Unary(ctx, &pb.Req{})
	cancel()
	P("%v  (err=%v)", resp.GetMsg(), err)

	Sec("三:如果 A 调 B 时没有传 ctx(用了 context.Background()),下游就没有截止时间;客户端超时后 B、C 还在白白干活")
	var bDone, cDone atomic.Int32
	slow := func(done *atomic.Int32, d time.Duration, next func(context.Context) error) *DemoServer {
		return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			time.Sleep(d)
			if next != nil {
				if err := next(ctx); err != nil {
					return nil, err
				}
			}
			done.Add(1)
			return &pb.Resp{Msg: "done"}, nil
		}}
	}
	cAddr, cStop := Start(slow(&cDone, 400*time.Millisecond, nil))
	defer cStop()
	cCl := dial(cAddr)
	for _, pass := range []bool{true, false} {
		bDone.Store(0)
		cDone.Store(0)
		bAddr, bStop := Start(slow(&bDone, 300*time.Millisecond, func(ctx context.Context) error {
			if !pass {
				ctx = context.Background()
			}
			_, err := cCl.Unary(ctx, &pb.Req{})
			return err
		}))
		bCl := dial(bAddr)
		ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
		t0 := time.Now()
		_, err := bCl.Unary(ctx, &pb.Req{})
		cancel()
		el := time.Since(t0)
		s, _ := status.FromError(err)
		time.Sleep(1200 * time.Millisecond)
		P("A→B 传递 ctx=%-5v:客户端 %s 用时 %s;1.2 秒后 B 完成了 %d 次、C 完成了 %d 次", pass, s.Code(), Ms(el), bDone.Load(), cDone.Load())
		bStop()
	}

	Sec("四:截止时间已经过了再发起调用:有没有帧发到线上")
	{
		addr, stop := Start(&DemoServer{})
		defer stop()
		tap := NewTap(addr)
		defer tap.Close()
		cl := dial(tap.Addr)
		cl.Unary(context.Background(), &pb.Req{})
		time.Sleep(30 * time.Millisecond)
		tap.Reset()
		ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
		t0 := time.Now()
		_, err := cl.Unary(ctx, &pb.Req{})
		el := time.Since(t0)
		cancel()
		time.Sleep(50 * time.Millisecond)
		s, _ := status.FromError(err)
		n := 0
		for _, e := range tap.Snapshot() {
			if e.Type == "HEADERS" || e.Type == "DATA" {
				n++
			}
		}
		P("已过期 1 秒的 deadline → code=%s message=%q 用时 %s;线上的 HEADERS/DATA 帧 %d 个", s.Code(), s.Message(), Ms(el), n)
	}

	Sec("五:服务端能不能看到客户端已经超时:handler 里监听 ctx.Done() 和不监听的区别")
	{
		var watched, ignored atomic.Int32
		var sawCancelAfter atomic.Int64
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			if r.Msg == "watch" {
				select {
				case <-time.After(time.Second):
					watched.Add(1)
				case <-ctx.Done():
					sawCancelAfter.Store(time.Now().UnixNano())
				}
				return nil, ctx.Err()
			}
			time.Sleep(time.Second)
			ignored.Add(1)
			return &pb.Resp{}, nil
		}}
		addr, stop := Start(srv)
		defer stop()
		cl := dial(addr)
		for _, m := range []string{"watch", "ignore"} {
			ctx, cancel := context.WithTimeout(context.Background(), 150*time.Millisecond)
			t0 := time.Now()
			_, err := cl.Unary(ctx, &pb.Req{Msg: m})
			cancel()
			s, _ := status.FromError(err)
			el := time.Since(t0)
			if m == "watch" {
				P("监听 ctx.Done():客户端 %s,%s 返回;服务端在 %s 时发现 ctx 已取消", s.Code(), Ms(el), Ms(time.Duration(sawCancelAfter.Load()-t0.UnixNano())))
			} else {
				time.Sleep(1100 * time.Millisecond)
				P("不监听 ctx:客户端 %s,%s 返回;1.1 秒后服务端仍把 1 秒的活干完了(完成次数 %d)", s.Code(), Ms(el), ignored.Load())
			}
		}
	}

	Sec("六:截止时间在线上是相对时长(grpc-timeout),服务端从收到请求头那一刻起重新计时,所以传输延迟不会被扣掉(代理给客户端→服务端方向加延迟)")
	{
		var rem atomic.Int64
		var clientDeadline atomic.Int64
		var clientLeft atomic.Int64
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			d, _ := ctx.Deadline()
			rem.Store(time.Until(d).Milliseconds())
			clientLeft.Store(time.Until(time.Unix(0, clientDeadline.Load())).Milliseconds())
			return &pb.Resp{}, nil
		}}
		addr, stop := Start(srv)
		defer stop()
		tap := NewTap(addr)
		defer tap.Close()
		cl := dial(tap.Addr)
		cl.Unary(context.Background(), &pb.Req{})
		P("%-14s %-22s %s", "线上额外延迟", "服务端 handler 看到的剩余", "此刻客户端真正还剩")
		for _, lat := range []time.Duration{0, 100 * time.Millisecond, 300 * time.Millisecond} {
			tap.Latency = lat
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			dl, _ := ctx.Deadline()
			clientDeadline.Store(dl.UnixNano())
			cl.Unary(ctx, &pb.Req{})
			cancel()
			P("%-14v %-22s %d ms", lat, fmt.Sprintf("%d ms", rem.Load()), clientLeft.Load())
		}
	}
}
