package main

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func main() {
	var want codes.Code
	srv := &DemoServer{}
	srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		switch r.Msg {
		case "code":
			return nil, status.Error(want, "服务端主动返回 "+want.String())
		case "plain":
			return nil, errors.New("普通 error,不是 status")
		case "ctxcancel":
			return nil, context.Canceled
		case "ctxdeadline":
			return nil, context.DeadlineExceeded
		case "wrapped":
			return nil, fmt.Errorf("包了一层: %w", status.Error(codes.NotFound, "内层 NotFound"))
		case "slow":
			select {
			case <-time.After(2 * time.Second):
			case <-ctx.Done():
			}
			return &pb.Resp{}, nil
		}
		return &pb.Resp{Msg: "ok"}, nil
	}
	addr, stop := Start(srv)
	defer stop()
	tap := NewTap(addr)
	defer tap.Close()
	conn, _ := grpc.NewClient(tap.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	defer conn.Close()
	cl := pb.NewDemoClient(conn)
	call := func(msg string, d time.Duration, opts ...grpc.CallOption) (*pb.Resp, error) {
		ctx, cancel := context.WithTimeout(context.Background(), d)
		defer cancel()
		return cl.Unary(ctx, &pb.Req{Msg: msg}, opts...)
	}
	call("warm", time.Second)

	Sec("一:服务端主动返回 17 个状态码,客户端收到的 code 与线上 trailers 里的 grpc-status 数字(代理抓到的)")
	P("%-4s %-20s %-20s %s", "数字", "名字", "客户端看到", "线上 grpc-status")
	for c := codes.Code(0); c <= 16; c++ {
		want = c
		tap.Reset()
		_, err := call("code", 2*time.Second)
		time.Sleep(15 * time.Millisecond)
		s, _ := status.FromError(err)
		wire := ""
		for _, e := range tap.Snapshot() {
			if e.Dir == "S→C" && e.Type == "HEADERS" {
				for _, kv := range strings.Split(e.Info, "; ") {
					if strings.HasPrefix(kv, "grpc-status:") {
						wire = strings.TrimSpace(strings.TrimPrefix(kv, "grpc-status:"))
					}
				}
			}
		}
		P("%-4d %-20s %-20s %s", uint32(c), c.String(), s.Code().String(), wire)
	}

	Sec("二:服务端返回的不是 status 的错误,或者是 context 错误,客户端看到的 code")
	for _, m := range []string{"plain", "ctxcancel", "ctxdeadline", "wrapped"} {
		_, err := call(m, 2*time.Second)
		s, _ := status.FromError(err)
		P("服务端返回 %-12s → 客户端 code=%-17s message=%q", m, s.Code(), s.Message())
	}

	Sec("三:框架自己产生的状态码:调用没注册的方法、客户端超时、客户端取消、服务端不存在")
	{
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		err := conn.Invoke(ctx, "/demo.Demo/NoSuchMethod", &pb.Req{}, &pb.Resp{})
		cancel()
		s, _ := status.FromError(err)
		P("调用不存在的方法 → code=%s message=%q", s.Code(), s.Message())
		t0 := time.Now()
		_, err = call("slow", 200*time.Millisecond)
		s, _ = status.FromError(err)
		P("服务端要 2 秒、客户端 200 ms 超时 → code=%s message=%q 用时 %s", s.Code(), s.Message(), Ms(time.Since(t0)))
		ctx, cancel = context.WithCancel(context.Background())
		go func() { time.Sleep(100 * time.Millisecond); cancel() }()
		t0 = time.Now()
		_, err = cl.Unary(ctx, &pb.Req{Msg: "slow"})
		s, _ = status.FromError(err)
		P("客户端 100 ms 后取消 → code=%s message=%q 用时 %s", s.Code(), s.Message(), Ms(time.Since(t0)))
	}
	{
		dead := FreePort()
		c2, _ := grpc.NewClient(fmt.Sprintf("127.0.0.1:%d", dead), grpc.WithTransportCredentials(insecure.NewCredentials()))
		defer c2.Close()
		cl2 := pb.NewDemoClient(c2)
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		t0 := time.Now()
		_, err := cl2.Unary(ctx, &pb.Req{})
		cancel()
		s, _ := status.FromError(err)
		P("服务端不存在(端口没人监听),默认 fail-fast → code=%s 用时 %s", s.Code(), Ms(time.Since(t0)))
		P("   message=%q", s.Message())
		ctx, cancel = context.WithTimeout(context.Background(), 800*time.Millisecond)
		t0 = time.Now()
		_, err = cl2.Unary(ctx, &pb.Req{}, grpc.WaitForReady(true))
		cancel()
		s, _ = status.FromError(err)
		P("同样但加 WaitForReady(true) → code=%s 用时 %s", s.Code(), Ms(time.Since(t0)))
		P("   message=%q", s.Message())
	}

	Sec("四:一个不说 gRPC 的 HTTP/2 服务器(比如网关或代理)返回各种 HTTP 状态时,客户端把它映射成什么 code")
	hp := FreePort()
	var hs int
	mux := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(hs)
		w.Write([]byte("<html>" + strconv.Itoa(hs) + "</html>"))
	})
	hsrv := &http.Server{Handler: h2c.NewHandler(mux, &http2.Server{})}
	l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", hp))
	go hsrv.Serve(l)
	c3, _ := grpc.NewClient(l.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	defer c3.Close()
	cl3 := pb.NewDemoClient(c3)
	P("%-10s %-20s %s", "HTTP 状态", "客户端 code", "message")
	for _, h := range []int{200, 400, 401, 403, 404, 429, 500, 502, 503, 504} {
		hs = h
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		_, err := cl3.Unary(ctx, &pb.Req{})
		cancel()
		s, _ := status.FromError(err)
		P("%-10d %-20s %q", h, s.Code(), s.Message())
	}
}
