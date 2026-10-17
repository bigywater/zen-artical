package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

type logger struct {
	mu sync.Mutex
	l  []string
}

func (g *logger) add(s string) { g.mu.Lock(); g.l = append(g.l, s); g.mu.Unlock() }
func (g *logger) take() string {
	g.mu.Lock()
	defer g.mu.Unlock()
	s := strings.Join(g.l, " → ")
	g.l = nil
	return s
}

func sUnary(g *logger, name string) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
		g.add("服务端" + name + "前")
		r, err := h(ctx, req)
		g.add("服务端" + name + "后")
		return r, err
	}
}
func cUnary(g *logger, name string) grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply any, cc *grpc.ClientConn, inv grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		g.add("客户端" + name + "前")
		err := inv(ctx, method, req, reply, cc, opts...)
		g.add("客户端" + name + "后")
		return err
	}
}

func logSrv(g *logger) *DemoServer {
	return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		g.add("handler")
		return &pb.Resp{}, nil
	}}
}

type wrapSS struct {
	grpc.ServerStream
	recv, sent *atomic.Int64
}

func (w *wrapSS) RecvMsg(m any) error {
	err := w.ServerStream.RecvMsg(m)
	if err == nil {
		w.recv.Add(1)
	}
	return err
}
func (w *wrapSS) SendMsg(m any) error {
	err := w.ServerStream.SendMsg(m)
	if err == nil {
		w.sent.Add(1)
	}
	return err
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "panic-child" {
		panicChild()
		return
	}
	g := &logger{}

	Sec("一:链式拦截器的执行顺序:服务端 ChainUnaryInterceptor(A, B, C),客户端 WithChainUnaryInterceptor(a, b, c)")
	{
		addr, stop := Start(logSrv(g), grpc.ChainUnaryInterceptor(sUnary(g, "A"), sUnary(g, "B"), sUnary(g, "C")))
		conn, _ := grpc.NewClient(addr, insec, grpc.WithChainUnaryInterceptor(cUnary(g, "a"), cUnary(g, "b"), cUnary(g, "c")))
		pb.NewDemoClient(conn).Unary(context.Background(), &pb.Req{})
		P("%s", g.take())
		conn.Close()
		stop()
	}

	Sec("二:同时用 UnaryInterceptor(X) 和 ChainUnaryInterceptor(Y, Z)(服务端),WithUnaryInterceptor(x) 和 WithChainUnaryInterceptor(y, z)(客户端),谁在外层")
	for _, first := range []string{"先写 Chain 后写单个", "先写单个后写 Chain"} {
		var so []grpc.ServerOption
		var co []grpc.DialOption
		chainS := grpc.ChainUnaryInterceptor(sUnary(g, "Y"), sUnary(g, "Z"))
		oneS := grpc.UnaryInterceptor(sUnary(g, "X"))
		chainC := grpc.WithChainUnaryInterceptor(cUnary(g, "y"), cUnary(g, "z"))
		oneC := grpc.WithUnaryInterceptor(cUnary(g, "x"))
		if first == "先写 Chain 后写单个" {
			so, co = []grpc.ServerOption{chainS, oneS}, []grpc.DialOption{chainC, oneC}
		} else {
			so, co = []grpc.ServerOption{oneS, chainS}, []grpc.DialOption{oneC, chainC}
		}
		addr, stop := Start(logSrv(g), so...)
		conn, _ := grpc.NewClient(addr, append(co, insec)...)
		pb.NewDemoClient(conn).Unary(context.Background(), &pb.Req{})
		P("(%s)%s", first, g.take())
		conn.Close()
		stop()
	}

	Sec("三:拦截器能改什么:客户端拦截器往 metadata 里加 x-trace;服务端拦截器读到后放进 ctx、并改写返回值;服务端 SetHeader 在响应头里回传")
	{
		type key struct{}
		var seenInHandler string
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			seenInHandler, _ = ctx.Value(key{}).(string)
			return &pb.Resp{Msg: "handler 的返回值"}, nil
		}}
		srvIc := func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
			md, _ := metadata.FromIncomingContext(ctx)
			ctx = context.WithValue(ctx, key{}, strings.Join(md.Get("x-trace"), ","))
			grpc.SetHeader(ctx, metadata.Pairs("x-served-by", "interceptor"))
			r, err := h(ctx, req)
			if err == nil {
				r.(*pb.Resp).Msg += "(被服务端拦截器改写)"
			}
			return r, err
		}
		cliIc := func(ctx context.Context, method string, req, reply any, cc *grpc.ClientConn, inv grpc.UnaryInvoker, opts ...grpc.CallOption) error {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-trace", "t-123")
			return inv(ctx, method, req, reply, cc, opts...)
		}
		addr, stop := Start(srv, grpc.UnaryInterceptor(srvIc))
		conn, _ := grpc.NewClient(addr, insec, grpc.WithUnaryInterceptor(cliIc))
		var hdr metadata.MD
		r, err := pb.NewDemoClient(conn).Unary(context.Background(), &pb.Req{}, grpc.Header(&hdr))
		P("err=%v;客户端收到 Msg=%q;handler 里从 ctx 取到 x-trace=%q;客户端读到响应头 x-served-by=%q", err, r.GetMsg(), seenInHandler, hdr.Get("x-served-by"))
		conn.Close()
		stop()
	}

	Sec("四:拦截器可以不调用下一层(短路):服务端“鉴权”拦截器拒绝没有 token 的请求;客户端拦截器在本地直接返回,请求根本不发出")
	{
		var handlerCalls atomic.Int64
		srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			handlerCalls.Add(1)
			return &pb.Resp{}, nil
		}}
		auth := func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
			md, _ := metadata.FromIncomingContext(ctx)
			if len(md.Get("authorization")) == 0 {
				return nil, status.Error(codes.Unauthenticated, "缺少 authorization")
			}
			return h(ctx, req)
		}
		addr, stop := Start(srv, grpc.UnaryInterceptor(auth))
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		_, err := cl.Unary(context.Background(), &pb.Req{})
		st, _ := status.FromError(err)
		P("没带 token:code=%s message=%q;handler 被调用 %d 次", st.Code(), st.Message(), handlerCalls.Load())
		ctx := metadata.AppendToOutgoingContext(context.Background(), "authorization", "Bearer x")
		_, err = cl.Unary(ctx, &pb.Req{})
		P("带 token:err=%v;handler 被调用 %d 次", err, handlerCalls.Load())
		conn.Close()
		conn2, _ := grpc.NewClient(tap.Addr, insec, grpc.WithUnaryInterceptor(func(ctx context.Context, method string, req, reply any, cc *grpc.ClientConn, inv grpc.UnaryInvoker, opts ...grpc.CallOption) error {
			return status.Error(codes.ResourceExhausted, "本地限流,没有发出请求")
		}))
		tap.Reset()
		_, err = pb.NewDemoClient(conn2).Unary(context.Background(), &pb.Req{})
		time.Sleep(50 * time.Millisecond)
		nh := 0
		for _, e := range tap.Snapshot() {
			if e.Dir == "C→S" && e.Type == "HEADERS" {
				nh++
			}
		}
		st, _ = status.FromError(err)
		P("客户端拦截器短路:code=%s;代理看到客户端发出的 HEADERS %d 个", st.Code(), nh)
		conn2.Close()
		tap.Close()
		stop()
	}

	Sec("五:流式 RPC:StreamInterceptor 每个流只调用一次(不是每条消息一次);一元拦截器对流不起作用;要数消息,得包装 ServerStream 的 RecvMsg/SendMsg")
	{
		var unaryCalls, streamCalls atomic.Int64
		recv, sent := &atomic.Int64{}, &atomic.Int64{}
		srv := &DemoServer{
			OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
				for i := 0; i < 5; i++ {
					st.Send(&pb.Resp{})
				}
				return nil
			},
			OnBidi: func(st pb.Demo_BidiServer) error {
				for {
					m, err := st.Recv()
					if err != nil {
						return nil
					}
					st.Send(&pb.Resp{Msg: m.Msg})
				}
			},
		}
		addr, stop := Start(srv,
			grpc.UnaryInterceptor(func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
				unaryCalls.Add(1)
				return h(ctx, req)
			}),
			grpc.StreamInterceptor(func(srv any, ss grpc.ServerStream, info *grpc.StreamServerInfo, h grpc.StreamHandler) error {
				streamCalls.Add(1)
				return h(srv, &wrapSS{ss, recv, sent})
			}))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		st, _ := cl.ServerStream(context.Background(), &pb.Req{})
		for {
			if _, err := st.Recv(); err != nil {
				break
			}
		}
		P("一次服务端流(服务端发 5 条):StreamInterceptor 调用 %d 次,一元拦截器 %d 次;包装后统计 SendMsg 成功 %d、RecvMsg 成功 %d", streamCalls.Load(), unaryCalls.Load(), sent.Load(), recv.Load())
		recv.Store(0)
		sent.Store(0)
		b, _ := cl.Bidi(context.Background())
		for i := 0; i < 7; i++ {
			b.Send(&pb.Req{Msg: "x"})
			b.Recv()
		}
		b.CloseSend()
		b.Recv()
		P("一次双向流(来回 7 条):StreamInterceptor 累计调用 %d 次;SendMsg 成功 %d、RecvMsg 成功 %d", streamCalls.Load(), sent.Load(), recv.Load())
		cl.Unary(context.Background(), &pb.Req{})
		P("再来一次 Unary:一元拦截器累计 %d 次,StreamInterceptor 仍是 %d 次", unaryCalls.Load(), streamCalls.Load())
		conn.Close()
		stop()
	}

	Sec("六:handler 里 panic:没有恢复拦截器时整个服务进程退出;加一个 recover 拦截器后只让这一次调用失败(子进程里跑,看退出码)")
	for _, mode := range []string{"norecover", "recover"} {
		cmd := exec.Command(os.Args[0], "panic-child", mode)
		out, err := cmd.CombinedOutput()
		code := 0
		if ee, ok := err.(*exec.ExitError); ok {
			code = ee.ExitCode()
		}
		lines := strings.Split(strings.TrimSpace(string(out)), "\n")
		first := lines[0]
		P("%-9s 子进程退出码 %d;第一行输出:%s", mode, code, first)
		if mode == "recover" {
			for _, l := range lines[1:] {
				P("    %s", l)
			}
		}
	}

	Sec("七:拦截器的开销:一元调用,服务端和客户端各加 0、1、10 个什么都不做的拦截器,各 20000 次顺序调用的每次平均耗时(同一台机器、同一个进程,只作量级参考)")
	{
		noopS := func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
			return h(ctx, req)
		}
		noopC := func(ctx context.Context, method string, req, reply any, cc *grpc.ClientConn, inv grpc.UnaryInvoker, opts ...grpc.CallOption) error {
			return inv(ctx, method, req, reply, cc, opts...)
		}
		var res []string
		for _, n := range []int{0, 1, 10} {
			var so []grpc.ServerOption
			var co []grpc.DialOption
			for i := 0; i < n; i++ {
				so = append(so, grpc.ChainUnaryInterceptor(noopS))
				co = append(co, grpc.WithChainUnaryInterceptor(noopC))
			}
			addr, stop := Start(&DemoServer{}, so...)
			conn, _ := grpc.NewClient(addr, append(co, insec)...)
			cl := pb.NewDemoClient(conn)
			for i := 0; i < 2000; i++ {
				cl.Unary(context.Background(), &pb.Req{})
			}
			var ds []time.Duration
			for r := 0; r < 5; r++ {
				t0 := time.Now()
				for i := 0; i < 20000; i++ {
					cl.Unary(context.Background(), &pb.Req{})
				}
				ds = append(ds, time.Since(t0))
			}
			sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
			per := float64(ds[2].Nanoseconds()) / 20000 / 1000
			res = append(res, fmt.Sprintf("每端 %2d 个拦截器:每次调用 %.1f µs(5 轮取中位数)", n, per))
			conn.Close()
			stop()
		}
		for _, r := range res {
			P("%s", r)
		}
	}
}

func panicChild() {
	mode := os.Args[2]
	srv := &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		if r.Msg == "boom" {
			panic("handler 里出错了")
		}
		return &pb.Resp{Msg: "ok"}, nil
	}}
	var opts []grpc.ServerOption
	if mode == "recover" {
		opts = append(opts, grpc.UnaryInterceptor(func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (resp any, err error) {
			defer func() {
				if r := recover(); r != nil {
					err = status.Errorf(codes.Internal, "panic: %v", r)
				}
			}()
			return h(ctx, req)
		}))
	}
	addr, _ := Start(srv, opts...)
	conn, _ := grpc.NewClient(addr, insec)
	cl := pb.NewDemoClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	_, err := cl.Unary(ctx, &pb.Req{Msg: "boom"})
	if mode == "recover" {
		st, _ := status.FromError(err)
		fmt.Printf("出错的调用:code=%s message=%q\n", st.Code(), st.Message())
		r, err := cl.Unary(ctx, &pb.Req{Msg: "next"})
		fmt.Printf("之后的调用:err=%v msg=%q(服务进程还活着)\n", err, r.GetMsg())
		return
	}
	fmt.Println("(客户端走到了这里,说明服务进程没有退出)", err)
}
