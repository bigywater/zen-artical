package main

import (
	"context"
	"fmt"
	"io"
	"strings"
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
	var srvLog atomic.Value
	srvLog.Store("(无记录)")
	var mode atomic.Value
	mode.Store("echo")
	srv := &DemoServer{}
	srv.OnClientStream = func(st pb.Demo_ClientStreamServer) error {
		n := 0
		for {
			_, err := st.Recv()
			if err == io.EOF {
				srvLog.Store(fmt.Sprintf("服务端 Recv 收到 io.EOF(共 %d 条),SendAndClose", n))
				return st.SendAndClose(&pb.Resp{N: int32(n)})
			}
			if err != nil {
				srvLog.Store(fmt.Sprintf("服务端 Recv 返回错误(已收 %d 条):%v", n, err))
				return err
			}
			n++
		}
	}
	srv.OnBidi = func(st pb.Demo_BidiServer) error {
		switch mode.Load().(string) {
		case "echo":
			for {
				m, err := st.Recv()
				if err == io.EOF {
					srvLog.Store("服务端 Recv 收到 io.EOF(客户端已 CloseSend)")
					return nil
				}
				if err != nil {
					srvLog.Store("服务端 Recv 错误:" + err.Error())
					return err
				}
				if err := st.Send(&pb.Resp{Msg: m.Msg, Payload: m.Payload}); err != nil {
					srvLog.Store("服务端 Send 错误:" + err.Error())
					return err
				}
			}
		case "after-eof":
			for {
				if _, err := st.Recv(); err == io.EOF {
					break
				}
			}
			for i := 0; i < 3; i++ {
				st.Send(&pb.Resp{Msg: fmt.Sprint("late-", i)})
			}
			srvLog.Store("服务端收到 EOF 之后又发了 3 条")
			return nil
		case "early-ok":
			st.Recv()
			srvLog.Store("服务端读了 1 条就 return nil")
			return nil
		case "early-err":
			st.Recv()
			srvLog.Store("服务端读了 1 条就 return PermissionDenied")
			return status.Error(codes.PermissionDenied, "不让你继续")
		case "never-recv":
			time.Sleep(300 * time.Millisecond)
			return nil
		}
		return nil
	}
	addr, stop := Start(srv)
	defer stop()
	tap := NewTap(addr)
	defer tap.Close()
	conn, _ := grpc.NewClient(tap.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	defer conn.Close()
	cl := pb.NewDemoClient(conn)
	cl.Unary(context.Background(), &pb.Req{})
	time.Sleep(30 * time.Millisecond)

	Sec("一:客户端流:发 3 条消息再 CloseAndRecv,线上 END_STREAM 标在哪一帧,服务端的 Recv 在什么时候返回 io.EOF")
	tap.Reset()
	st, _ := cl.ClientStream(context.Background())
	for i := 0; i < 3; i++ {
		st.Send(&pb.Req{Msg: fmt.Sprint("c", i)})
	}
	time.Sleep(50 * time.Millisecond)
	P("客户端发了 3 条、还没 CloseAndRecv:服务端 %v(没有 EOF,在等更多消息)", srvLog.Load())
	resp, err := st.CloseAndRecv()
	time.Sleep(50 * time.Millisecond)
	P("CloseAndRecv 后:resp.N=%d err=%v;%v", resp.GetN(), err, srvLog.Load())
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && (e.Type == "DATA" || e.Type == "HEADERS") && e.Stream == 3 {
			P("   C→S %-8s 长 %-3d 标志 %s", e.Type, e.Len, e.Flags)
		}
	}

	Sec("二:双向流的半关闭:客户端 CloseSend 之后,服务端 Recv 得到 EOF,但服务端还可以继续发;客户端 Recv 要等到服务端 return 才得到 EOF")
	mode.Store("after-eof")
	srvLog.Store("(无记录)")
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	b, _ := cl.Bidi(ctx)
	b.Send(&pb.Req{Msg: "x"})
	b.CloseSend()
	var got []string
	for {
		m, err := b.Recv()
		if err != nil {
			P("客户端依次收到 %v,最后 Recv 返回 %v;%v", got, err, srvLog.Load())
			break
		}
		got = append(got, m.Msg)
	}
	cancel()

	Sec("三:服务端提前结束:客户端继续 Send 会怎样。Send 返回 io.EOF 表示“流已经结束”,真正的状态要靠 Recv 取")
	for _, m := range []string{"early-ok", "early-err"} {
		mode.Store(m)
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		b, _ := cl.Bidi(ctx)
		b.Send(&pb.Req{Msg: "first"})
		time.Sleep(100 * time.Millisecond)
		var sendErrs []string
		for i := 0; i < 3; i++ {
			err := b.Send(&pb.Req{Msg: "more"})
			sendErrs = append(sendErrs, fmt.Sprint(err))
		}
		_, rerr := b.Recv()
		s, _ := status.FromError(rerr)
		rs := fmt.Sprintf("code=%s message=%q", s.Code(), s.Message())
		if rerr == io.EOF {
			rs = "io.EOF(状态为 OK)"
		}
		P("%-9s %v:后续 3 次 Send 返回 %v;Recv 返回 %s", m, srvLog.Load(), sendErrs, rs)
		cancel()
	}

	Sec("四:经典死锁:服务端收一条回一条(同一个 goroutine),客户端只管 Send 不 Recv,消息每条 256 KiB;数一数客户端 Send 成功了几条")
	{
		mode.Store("echo")
		srvLog.Store("(服务端 handler 还没返回,阻塞在 Send 上,没有日志)")
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		b, _ := cl.Bidi(ctx)
		payload := make([]byte, 256*1024)
		sent := 0
		done := make(chan struct{})
		go func() {
			for i := 0; i < 100; i++ {
				if err := b.Send(&pb.Req{Payload: payload}); err != nil {
					break
				}
				sent++
			}
			close(done)
		}()
		select {
		case <-done:
			P("100 条全部 Send 完成")
		case <-time.After(1 * time.Second):
			P("1 秒后客户端只 Send 成功了 %d 条(共 %d KiB),之后卡住;服务端状态:%v", sent, sent*256, srvLog.Load())
		}
		cancel()
		<-done
		time.Sleep(50 * time.Millisecond)
		P("deadline 到后:客户端 Send 退出;服务端:%v", srvLog.Load())
		// 对照:客户端另开 goroutine 并发读
		ctx, cancel = context.WithTimeout(context.Background(), 5*time.Second)
		b, _ = cl.Bidi(ctx)
		go func() {
			for {
				if _, err := b.Recv(); err != nil {
					return
				}
			}
		}()
		t0 := time.Now()
		for i := 0; i < 100; i++ {
			b.Send(&pb.Req{Payload: payload})
		}
		b.CloseSend()
		time.Sleep(200 * time.Millisecond)
		P("对照:客户端用另一个 goroutine 同时 Recv:100 条(25 MiB)Send 完,用时 %s;服务端:%v", Ms(time.Since(t0)), srvLog.Load())
		cancel()
	}

	Sec("五:忘记 CloseSend:客户端不 CloseSend,服务端的 Recv 会一直等")
	{
		mode.Store("echo")
		srvLog.Store("(服务端还没返回)")
		ctx, cancel := context.WithTimeout(context.Background(), 800*time.Millisecond)
		b, _ := cl.Bidi(ctx)
		b.Send(&pb.Req{Msg: "only"})
		b.Recv()
		srvLog.Store("(服务端还没返回)")
		time.Sleep(500 * time.Millisecond)
		P("500 ms 后服务端:%v", srvLog.Load())
		time.Sleep(500 * time.Millisecond)
		_, err := b.Recv()
		s, _ := status.FromError(err)
		P("deadline 到了之后客户端 Recv 返回 code=%s;服务端:%v", s.Code(), srvLog.Load())
		cancel()
	}

	Sec("六:各种结束方式下两端 Recv/Send 的返回值")
	for _, sc := range []string{"服务端 return nil", "服务端 return 错误", "客户端 CloseSend", "客户端 cancel"} {
		var cRecv, sRecv string
		mode.Store("echo")
		srvLog.Store("(服务端还没返回)")
		switch sc {
		case "服务端 return nil":
			mode.Store("early-ok")
		case "服务端 return 错误":
			mode.Store("early-err")
		}
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		b, _ := cl.Bidi(ctx)
		b.Send(&pb.Req{Msg: "m"})
		switch sc {
		case "客户端 CloseSend":
			b.CloseSend()
		case "客户端 cancel":
			time.Sleep(50 * time.Millisecond)
			cancel()
		}
		var err error
		for {
			_, err = b.Recv()
			if err != nil {
				break
			}
		}
		s, _ := status.FromError(err)
		cRecv = fmt.Sprintf("code=%s", s.Code())
		if err == io.EOF {
			cRecv = "io.EOF(状态为 OK)"
		}
		time.Sleep(50 * time.Millisecond)
		sRecv = fmt.Sprint(srvLog.Load())
		if len(sRecv) > 60 {
			sRecv = sRecv[:60]
		}
		P("%-14s 客户端 Recv 最终:%-24s 服务端记录:%s", sc, cRecv, strings.TrimSpace(sRecv))
		cancel()
	}
}
