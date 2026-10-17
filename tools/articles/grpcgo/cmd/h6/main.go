package main

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func dial(addr string) pb.DemoClient {
	c, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	return pb.NewDemoClient(c)
}

func main() {
	var active atomic.Int32
	var sendErr atomic.Value
	var streamCtxErr atomic.Value
	srv := &DemoServer{}
	srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		active.Add(1)
		defer active.Add(-1)
		switch r.Msg {
		case "watch":
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(2 * time.Second):
			}
		case "ignore":
			time.Sleep(500 * time.Millisecond)
		case "fast":
			time.Sleep(time.Duration(r.N) * time.Microsecond)
		}
		return &pb.Resp{Msg: "ok"}, nil
	}
	srv.OnServerStream = func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		active.Add(1)
		defer active.Add(-1)
		for i := 0; i < 1000; i++ {
			if err := st.Send(&pb.Resp{N: int32(i), Payload: make([]byte, 100)}); err != nil {
				sendErr.Store(fmt.Sprintf("第 %d 次 Send 失败:%v", i, err))
				streamCtxErr.Store(fmt.Sprint(st.Context().Err()))
				return err
			}
			time.Sleep(20 * time.Millisecond)
		}
		return nil
	}
	addr, stop := Start(srv)
	defer stop()
	tap := NewTap(addr)
	defer tap.Close()
	cl := dial(tap.Addr)
	cl.Unary(context.Background(), &pb.Req{})
	time.Sleep(30 * time.Millisecond)

	Sec("一:客户端取消在线上是什么:一个 RST_STREAM 帧;超时(deadline 到期)的客户端也发 RST_STREAM")
	for _, mode := range []string{"cancel", "deadline"} {
		tap.Reset()
		var ctx context.Context
		var cancel context.CancelFunc
		if mode == "cancel" {
			ctx, cancel = context.WithCancel(context.Background())
			go func() { time.Sleep(100 * time.Millisecond); cancel() }()
		} else {
			ctx, cancel = context.WithTimeout(context.Background(), 100*time.Millisecond)
		}
		_, err := cl.Unary(ctx, &pb.Req{Msg: "watch"})
		cancel()
		time.Sleep(50 * time.Millisecond)
		s, _ := status.FromError(err)
		P("%s:客户端得到 %s;线上帧:", mode, s.Code())
		for _, e := range tap.Snapshot() {
			if e.Type == "RST_STREAM" || e.Type == "HEADERS" || (e.Type == "DATA" && e.Dir == "C→S") {
				P("    %s %-10s 流 %d %s", e.Dir, e.Type, e.Stream, e.Info)
			}
		}
	}

	Sec("二:取消 50 个调用之后,服务端还有多少个 handler 在运行(watch = handler 监听 ctx.Done();ignore = 不监听,要睡 500 ms)")
	for _, m := range []string{"watch", "ignore"} {
		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
				defer cancel()
				cl.Unary(ctx, &pb.Req{Msg: m})
			}()
		}
		wg.Wait()
		P("%-7s 客户端 50 个调用全部超时返回时:服务端还在运行的 handler %d 个", m, active.Load())
		for _, w := range []time.Duration{100, 300, 600} {
			time.Sleep(w * time.Millisecond)
			P("          再过 %-3d ms:%d 个", w, active.Load())
		}
	}

	Sec("三:流式 RPC 取消:客户端收到 5 条消息后取消;服务端 Send 什么时候开始失败、ctx 是什么状态")
	{
		ctx, cancel := context.WithCancel(context.Background())
		st, _ := cl.ServerStream(ctx, &pb.Req{})
		for i := 0; i < 5; i++ {
			st.Recv()
		}
		t0 := time.Now()
		cancel()
		_, err := st.Recv()
		s, _ := status.FromError(err)
		P("客户端取消后下一次 Recv 立刻返回:code=%s (%s)", s.Code(), Ms(time.Since(t0)))
		time.Sleep(200 * time.Millisecond)
		P("服务端:%v;st.Context().Err() = %v;仍在运行的 handler %d 个", sendErr.Load(), streamCtxErr.Load(), active.Load())
	}

	Sec("四:取消和响应赛跑:handler 固定耗时约 1 ms,客户端在不同的延迟后取消,各跑 400 次,结果是成功还是 Canceled")
	for _, d := range []int{500, 1000, 1500, 2000, 4000} {
		var ok, canceled, other atomic.Int32
		var wg sync.WaitGroup
		sem := make(chan struct{}, 8)
		for i := 0; i < 400; i++ {
			wg.Add(1)
			sem <- struct{}{}
			go func() {
				defer wg.Done()
				defer func() { <-sem }()
				ctx, cancel := context.WithCancel(context.Background())
				go func() { time.Sleep(time.Duration(d) * time.Microsecond); cancel() }()
				_, err := cl.Unary(ctx, &pb.Req{Msg: "fast", N: 1000})
				cancel()
				switch status.Code(err) {
				case 0:
					ok.Add(1)
				case 1:
					canceled.Add(1)
				default:
					other.Add(1)
				}
			}()
		}
		wg.Wait()
		P("handler 约 1000 µs,客户端 %4d µs 后取消:成功 %3d、Canceled %3d、其它 %d", d, ok.Load(), canceled.Load(), other.Load())
	}

	Sec("五:调用已经完成之后再 cancel():线上有没有 RST_STREAM(典型写法 defer cancel() 会不会多发帧)")
	{
		time.Sleep(500 * time.Millisecond)
		tap.Reset()
		ctx, cancel := context.WithCancel(context.Background())
		cl.Unary(ctx, &pb.Req{})
		time.Sleep(30 * time.Millisecond)
		before := 0
		for _, e := range tap.Snapshot() {
			if e.Type == "RST_STREAM" {
				before++
			}
		}
		cancel()
		time.Sleep(50 * time.Millisecond)
		after := 0
		for _, e := range tap.Snapshot() {
			if e.Type == "RST_STREAM" {
				after++
			}
		}
		P("调用完成后线上 RST_STREAM %d 个;再调用 cancel() 之后 %d 个", before, after)
	}

	Sec("六:取消沿调用链传到下游要多久:A → B → C(每层都把 ctx 传下去并监听 ctx.Done()),客户端 100 ms 后取消")
	{
		var t0 atomic.Int64
		var seen [3]atomic.Int64
		var cls [3]pb.DemoClient
		mk := func(i int) *DemoServer {
			return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				if i < 2 {
					_, err := cls[i+1].Unary(ctx, r)
					seen[i].Store(time.Now().UnixNano() - t0.Load())
					return nil, err
				}
				<-ctx.Done()
				seen[i].Store(time.Now().UnixNano() - t0.Load())
				return nil, ctx.Err()
			}}
		}
		var stops [3]func()
		var addrs [3]string
		for i := 2; i >= 0; i-- {
			addrs[i], stops[i] = Start(mk(i))
			defer stops[i]()
			cls[i] = dial(addrs[i])
		}
		ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
		cls[0].Unary(ctx, &pb.Req{})
		cancel()
		time.Sleep(100 * time.Millisecond)
		ctx, cancel = context.WithCancel(context.Background())
		t0.Store(time.Now().UnixNano())
		done := make(chan struct{})
		go func() { cls[0].Unary(ctx, &pb.Req{}); close(done) }()
		time.Sleep(100 * time.Millisecond)
		tc := time.Now().UnixNano() - t0.Load()
		cancel()
		<-done
		time.Sleep(100 * time.Millisecond)
		P("客户端在 %.1f ms 时取消;A 在 %.1f ms、B 在 %.1f ms、C 在 %.1f ms 发现自己的 ctx 被取消(距取消分别 %.1f / %.1f / %.1f ms)", float64(tc)/1e6, float64(seen[0].Load())/1e6, float64(seen[1].Load())/1e6, float64(seen[2].Load())/1e6, float64(seen[0].Load()-tc)/1e6, float64(seen[1].Load()-tc)/1e6, float64(seen[2].Load()-tc)/1e6)
	}
}
