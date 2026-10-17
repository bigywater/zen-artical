package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"time"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

func main() {
	srv := &DemoServer{}
	var tapRef *Tap
	srv.OnServerStream = func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
		switch r.Msg {
		case "fail-after-2":
			st.Send(&pb.Resp{Msg: "one"})
			st.Send(&pb.Resp{Msg: "two"})
			return status.Error(codes.Internal, "第三条出错了")
		case "fail-at-once":
			return status.Error(codes.PermissionDenied, "一条都没发就失败")
		case "ok-3":
			for i := 0; i < 3; i++ {
				st.Send(&pb.Resp{Msg: fmt.Sprint("m", i)})
			}
			return nil
		case "cut-after-1":
			st.Send(&pb.Resp{Msg: "first"})
			time.Sleep(50 * time.Millisecond)
			tapRef.CutAll()
			time.Sleep(300 * time.Millisecond)
			return nil
		case "trailer":
			st.SetTrailer(metadata.Pairs("x-served-by", "node-7", "x-cost-ms", "12", "x-blob-bin", "\x00\x01\xfe\xff"))
			st.Send(&pb.Resp{Msg: "with-trailer"})
			return nil
		}
		return nil
	}
	srv.OnUnary = func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		return nil, status.Error(codes.InvalidArgument, r.Msg)
	}
	addr, stop := Start(srv)
	defer stop()
	tap := NewTap(addr)
	tapRef = tap
	defer tap.Close()
	conn, _ := grpc.NewClient(tap.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	defer conn.Close()
	cl := pb.NewDemoClient(conn)
	drain := func(msg string, opts ...grpc.CallOption) (n int, err error) {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		st, e := cl.ServerStream(ctx, &pb.Req{Msg: msg}, opts...)
		if e != nil {
			return 0, e
		}
		for {
			_, e := st.Recv()
			if e == io.EOF {
				return n, nil
			}
			if e != nil {
				return n, e
			}
			n++
		}
	}
	cl.Unary(context.Background(), &pb.Req{})
	time.Sleep(30 * time.Millisecond)
	short := func(ev []Event, stream uint32) {
		for _, e := range ev {
			if e.Stream == stream && e.Dir == "S→C" && (e.Type == "HEADERS" || e.Type == "DATA") {
				fl := e.Flags
				if fl == "" {
					fl = "-"
				}
				info := e.Info
				if e.Type == "DATA" {
					info = fmt.Sprintf("消息 %d 字节", len(e.Data)-5)
				}
				P("  S→C %-8s 标志 %-24s %s", e.Type, fl, info)
			}
		}
	}

	Sec("一:服务端流发了 2 条消息之后才出错:HTTP 状态早在第一个 HEADERS 里就发出去了(200),错误只能放在最后")
	tap.Reset()
	n, err := drain("fail-after-2")
	time.Sleep(30 * time.Millisecond)
	s, _ := status.FromError(err)
	P("客户端:收到 %d 条消息之后 Recv 返回 code=%s message=%q", n, s.Code(), s.Message())
	short(tap.Snapshot(), 3)

	Sec("二:一条消息都没发就失败 —— 只有一个 HEADERS 帧(trailers-only):同时带 :status、content-type、grpc-status,并且带 END_STREAM")
	tap.Reset()
	n, err = drain("fail-at-once")
	time.Sleep(30 * time.Millisecond)
	s, _ = status.FromError(err)
	P("客户端:收到 %d 条消息,code=%s message=%q", n, s.Code(), s.Message())
	short(tap.Snapshot(), 5)
	tap.Reset()
	n, err = drain("ok-3")
	time.Sleep(30 * time.Millisecond)
	P("对照:正常返回 3 条消息的流,服务端的帧是:")
	short(tap.Snapshot(), 7)

	Sec("三:grpc-message 在线上要做百分号编码(中文、换行、百分号):线上看到的与客户端看到的")
	tap.Reset()
	msg := "参数错误:id=100%\n第二行"
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	_, err = cl.Unary(ctx, &pb.Req{Msg: msg})
	cancel()
	time.Sleep(30 * time.Millisecond)
	s, _ = status.FromError(err)
	for _, e := range tap.Snapshot() {
		if e.Dir == "S→C" && e.Type == "HEADERS" && strings.Contains(e.Info, "grpc-message") {
			for _, kv := range strings.Split(e.Info, "; ") {
				if strings.HasPrefix(kv, "grpc-message") {
					P("线上 %s", kv)
				}
			}
		}
	}
	P("客户端解码后 message=%q;与服务端原文相同:%v", s.Message(), s.Message() == msg)

	Sec("四:应用自己的 trailers:服务端 SetTrailer 三个键(其中一个是 -bin 结尾的二进制值),客户端用 grpc.Trailer 取;线上的样子")
	tap.Reset()
	var tr metadata.MD
	n, err = drain("trailer", grpc.Trailer(&tr))
	time.Sleep(30 * time.Millisecond)
	for _, k := range []string{"x-served-by", "x-cost-ms", "x-blob-bin"} {
		P("客户端 trailer %-12s = %q", k, tr.Get(k))
	}
	for _, e := range tap.Snapshot() {
		if e.Dir == "S→C" && e.Type == "HEADERS" && strings.Contains(e.Info, "x-served-by") {
			P("线上 trailers 帧:%s", e.Info)
		}
	}

	Sec("五:流到一半连接断了(trailers 没来得及发):客户端拿到的错误")
	n, err = drain("cut-after-1")
	s, _ = status.FromError(err)
	P("客户端先收到 %d 条消息,然后 code=%s message=%q", n, s.Code(), s.Message())

	Sec("六:一个只会发 HEADERS + DATA 而不发 trailers 的服务器(比如不支持 trailers 的代理):客户端的反应")
	hp := FreePort()
	mux := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.Copy(io.Discard, r.Body)
		w.Header().Set("Content-Type", "application/grpc")
		w.WriteHeader(200)
		w.Write([]byte{0, 0, 0, 0, 4, 0x0a, 0x02, 'o', 'k'})
	})
	l, _ := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", hp))
	go (&http.Server{Handler: h2c.NewHandler(mux, &http2.Server{})}).Serve(l)
	c2, _ := grpc.NewClient(l.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	defer c2.Close()
	ctx, cancel = context.WithTimeout(context.Background(), 2*time.Second)
	resp, err := pb.NewDemoClient(c2).Unary(ctx, &pb.Req{})
	cancel()
	s, _ = status.FromError(err)
	P("服务器回了合法的消息,但没有 grpc-status:resp=%v code=%s message=%q", resp, s.Code(), s.Message())
	_ = errors.New
}
