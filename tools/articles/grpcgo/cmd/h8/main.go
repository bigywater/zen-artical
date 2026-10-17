package main

import (
	"context"
	"fmt"
	"io"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func main() {
	var sendDur []time.Duration
	var sent atomic.Int64
	var finalErr atomic.Value
	srv := &DemoServer{}
	srv.OnServerStream = func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		sendDur = nil
		sent.Store(0)
		payload := make([]byte, r.N)
		limit := 400
		if r.Msg == "until-block" {
			limit = 40000
		}
		for i := 0; i < limit; i++ {
			t0 := time.Now()
			err := st.Send(&pb.Resp{N: int32(i), Payload: payload})
			sendDur = append(sendDur, time.Since(t0))
			if err != nil {
				finalErr.Store(fmt.Sprintf("第 %d 次 Send 失败:%v", i, err))
				return err
			}
			sent.Add(int64(len(payload)))
		}
		return nil
	}
	addr, stop := Start(srv)
	defer stop()
	cl := func(opts ...grpc.DialOption) pb.DemoClient {
		c, _ := grpc.NewClient(addr, append([]grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}, opts...)...)
		return pb.NewDemoClient(c)
	}

	Sec("一:快的生产者(服务端连续 Send 64 KiB 的消息)+ 慢的消费者(客户端每收一条睡 30 ms):服务端每次 Send 花多久")
	{
		c := cl()
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		st, _ := c.ServerStream(ctx, &pb.Req{N: 64 * 1024})
		t0 := time.Now()
		got := 0
		for got < 40 {
			if _, err := st.Recv(); err != nil {
				break
			}
			got++
			time.Sleep(30 * time.Millisecond)
		}
		cancel()
		time.Sleep(50 * time.Millisecond)
		P("客户端 %.0f ms 内收了 %d 条;服务端此时已 Send 完成(返回)%d 条", float64(time.Since(t0).Milliseconds()), got, sent.Load()/(64*1024))
		var o []string
		for i := 0; i < 20 && i < len(sendDur); i++ {
			o = append(o, fmt.Sprintf("%.1f", float64(sendDur[i].Microseconds())/1000))
		}
		P("服务端前 20 次 Send 耗时(ms):%v", o)
	}

	Sec("二:客户端完全不 Recv 时,服务端能 Send 多少字节才阻塞(1 KiB 的消息逐条发,600 ms 后读已经成功返回的字节数)")
	{
		c := cl()
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		st, _ := c.ServerStream(ctx, &pb.Req{N: 1024, Msg: "until-block"})
		_ = st
		time.Sleep(600 * time.Millisecond)
		got := sent.Load()
		time.Sleep(300 * time.Millisecond)
		got2 := sent.Load()
		cancel()
		time.Sleep(50 * time.Millisecond)
		P("默认窗口:600 ms 时已成功 Send %d 字节(%d 条 × 1 KiB),再过 300 ms 还是 %d 字节(%s);取消后服务端:%v", got, got/1024, got2, map[bool]string{true: "已经阻塞", false: "还在增长"}[got == got2], finalErr.Load())
	}

	Sec("三:把客户端接收窗口调大(WithInitialWindowSize / WithInitialConnWindowSize),阻塞前能多发多少(同样 1 KiB 的消息,最多发 40000 条)")
	for _, w := range []int32{64 * 1024, 256 * 1024, 1 << 20, 4 << 20} {
		c := cl(grpc.WithInitialWindowSize(w), grpc.WithInitialConnWindowSize(w))
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		st, _ := c.ServerStream(ctx, &pb.Req{N: 1024, Msg: "until-block"})
		_ = st
		time.Sleep(600 * time.Millisecond)
		got := sent.Load()
		cancel()
		time.Sleep(50 * time.Millisecond)
		P("窗口 %-8d 字节:阻塞前 Send 了 %d 字节(%.1f 倍窗口)", w, got, float64(got)/float64(w))
	}

	Sec("四:Send 阻塞时流的 deadline 到了:服务端被阻塞的 Send 会怎样")
	{
		c := cl()
		ctx, cancel := context.WithTimeout(context.Background(), 400*time.Millisecond)
		st, _ := c.ServerStream(ctx, &pb.Req{N: 64 * 1024})
		_ = st
		time.Sleep(900 * time.Millisecond)
		cancel()
		time.Sleep(100 * time.Millisecond)
		P("服务端:%v;客户端的 deadline 是 400 ms,被阻塞的 Send 在 deadline 到了之后才返回", finalErr.Load())
	}

	Sec("五:服务端发完 100 条小消息立刻返回错误(Send 都已经返回了),客户端能不能收全这 100 条,再看到错误")
	{
		srv2 := &DemoServer{OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			for i := 0; i < 100; i++ {
				st.Send(&pb.Resp{N: int32(i), Payload: make([]byte, 20000)})
			}
			return status.Error(codes.Aborted, "发完就报错")
		}}
		a2, s2 := Start(srv2)
		defer s2()
		c2, _ := grpc.NewClient(a2, grpc.WithTransportCredentials(insecure.NewCredentials()))
		st, _ := pb.NewDemoClient(c2).ServerStream(context.Background(), &pb.Req{})
		time.Sleep(300 * time.Millisecond) // 让服务端 handler 早早返回,消息还积在传输层里
		n := 0
		var last int32 = -1
		inOrder := true
		var err error
		for {
			var m *pb.Resp
			m, err = st.Recv()
			if err != nil {
				break
			}
			if m.N != last+1 {
				inOrder = false
			}
			last = m.N
			n++
		}
		s, _ := status.FromError(err)
		if err == io.EOF {
			s = status.New(codes.OK, "EOF")
		}
		P("客户端收到 %d 条(每条 20000 字节),顺序正确:%v,最后得到 code=%s message=%q", n, inOrder, s.Code(), s.Message())
	}
	Sec("六:一个 handler 同时在两个 goroutine 里调用 Send 是不允许的(grpc 文档:不能并发调用同一个流的 SendMsg);用 -race 看会怎样——这里只数一下并发 Send 时消息是否交错损坏")
	{
		srv3 := &DemoServer{OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
			done := make(chan struct{}, 2)
			for g := 0; g < 2; g++ {
				go func(g int) {
					for i := 0; i < 200; i++ {
						st.Send(&pb.Resp{N: int32(g*1000 + i), Msg: fmt.Sprintf("g%d-%d", g, i)})
					}
					done <- struct{}{}
				}(g)
			}
			<-done
			<-done
			return nil
		}}
		a3, s3 := Start(srv3)
		defer s3()
		c3, _ := grpc.NewClient(a3, grpc.WithTransportCredentials(insecure.NewCredentials()))
		st, _ := pb.NewDemoClient(c3).ServerStream(context.Background(), &pb.Req{})
		n, bad := 0, 0
		for {
			m, err := st.Recv()
			if err != nil {
				break
			}
			n++
			if m.Msg != fmt.Sprintf("g%d-%d", int(m.N)/1000, int(m.N)%1000) {
				bad++
			}
		}
		P("两个 goroutine 各 Send 200 条:客户端收到 %d 条,内容与编号对不上的 %d 条", n, bad)
	}
}
