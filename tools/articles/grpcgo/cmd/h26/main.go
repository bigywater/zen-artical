package main

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

// tokenCreds 是一个可配置的 PerRPCCredentials 实现。
type tokenCreds struct {
	secure bool
	get    func(ctx context.Context) (string, error)
	calls  atomic.Int64
}

func (t *tokenCreds) GetRequestMetadata(ctx context.Context, uri ...string) (map[string]string, error) {
	t.calls.Add(1)
	tok, err := t.get(ctx)
	if err != nil {
		return nil, err
	}
	return map[string]string{"authorization": "Bearer " + tok}, nil
}
func (t *tokenCreds) RequireTransportSecurity() bool { return t.secure }

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	m := st.Message()
	if len(m) > 160 {
		m = m[:160] + "…"
	}
	return fmt.Sprintf("code=%s message=%q", st.Code(), m)
}

func do(cl pb.DemoClient, timeout time.Duration, opts ...grpc.CallOption) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	_, err := cl.Unary(ctx, &pb.Req{}, opts...)
	return err
}

func authOf(tap *Tap, idx int) (string, int) {
	n := 0
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && e.Type == "HEADERS" {
			if n == idx {
				for _, kv := range strings.Split(e.Info, "; ") {
					if strings.HasPrefix(kv, "authorization:") {
						return strings.TrimSpace(strings.TrimPrefix(kv, "authorization:")), int(e.Len)
					}
				}
				return "(无)", int(e.Len)
			}
			n++
		}
	}
	return "(没有第这个请求)", 0
}

func main() {
	ca := NewCA("demo-ca")
	cert := ca.IssueServer("server", "svc.demo.test")
	srvTLS := grpc.Creds(credentials.NewTLS(&tls.Config{Certificates: []tls.Certificate{cert}}))
	cliTLS := grpc.WithTransportCredentials(credentials.NewClientTLSFromCert(ca.Pool, "svc.demo.test"))

	Sec("一:RequireTransportSecurity:PerRPCCredentials 声明需要加密传输时,配合明文连接会怎样;声明不需要时,令牌在线上是明文")
	{
		_, err := grpc.NewClient("127.0.0.1:1", insec, grpc.WithPerRPCCredentials(&tokenCreds{secure: true, get: func(context.Context) (string, error) { return "t", nil }}))
		P("RequireTransportSecurity()=true + 明文连接:NewClient 的结果:%v", err)
		addr, stop := Start(&DemoServer{})
		tap := NewTap(addr)
		tc := &tokenCreds{secure: false, get: func(context.Context) (string, error) { return "SECRET-TOKEN-123", nil }}
		conn, _ := grpc.NewClient(tap.Addr, insec, grpc.WithPerRPCCredentials(tc))
		do(pb.NewDemoClient(conn), 3*time.Second)
		time.Sleep(50 * time.Millisecond)
		a, _ := authOf(tap, 0)
		P("RequireTransportSecurity()=false + 明文连接:代理(窃听者)在线上看到 authorization: %s", a)
		conn.Close()
		tap.Close()
		stop()
		addr2, stop2 := Start(&DemoServer{}, srvTLS)
		tc2 := &tokenCreds{secure: true, get: func(context.Context) (string, error) { return "t", nil }}
		conn2, err := grpc.NewClient(addr2, cliTLS, grpc.WithPerRPCCredentials(tc2))
		P("RequireTransportSecurity()=true + TLS 连接:NewClient 结果 %v;调用 %s", err, em(do(pb.NewDemoClient(conn2), 3*time.Second)))
		conn2.Close()
		stop2()
	}

	Sec("二:每个 RPC 都调用一次 GetRequestMetadata,令牌每次都在线上;带一个 1000 字节的令牌时第 1、2、100 个请求的 HEADERS 帧大小(HPACK 动态表)")
	{
		addr, stop := Start(&DemoServer{})
		tap := NewTap(addr)
		big := strings.Repeat("a", 1000)
		tc := &tokenCreds{secure: false, get: func(context.Context) (string, error) { return big, nil }}
		conn, _ := grpc.NewClient(tap.Addr, insec, grpc.WithPerRPCCredentials(tc))
		cl := pb.NewDemoClient(conn)
		for i := 0; i < 100; i++ {
			do(cl, 3*time.Second)
		}
		time.Sleep(50 * time.Millisecond)
		_, l1 := authOf(tap, 0)
		_, l2 := authOf(tap, 1)
		_, l100 := authOf(tap, 99)
		P("100 个调用:GetRequestMetadata 被调用 %d 次;请求 HEADERS 帧载荷大小 第 1 个 %d 字节、第 2 个 %d 字节、第 100 个 %d 字节", tc.calls.Load(), l1, l2, l100)
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("三:令牌 1 秒过期,服务端的时钟比客户端快 100 ms(模拟时钟偏差/传输延迟);3 秒内每 20 ms 调用一次:不缓存、缓存但用到过期才刷新、缓存并提前 300 ms 刷新,各自的取令牌次数和被服务端拒绝的次数")
	{
		type tok struct {
			v   string
			exp time.Time
		}
		for _, mode := range []string{"每次都取新令牌", "缓存,过期才刷新", "缓存,提前 300 ms 刷新"} {
			var fetches atomic.Int64
			var mu sync.Mutex
			var cur tok
			fetch := func() tok {
				fetches.Add(1)
				return tok{fmt.Sprint(time.Now().UnixNano()), time.Now().Add(1 * time.Second)}
			}
			exps := sync.Map{}
			get := func(ctx context.Context) (string, error) {
				switch mode {
				case "每次都取新令牌":
					t := fetch()
					exps.Store(t.v, t.exp)
					return t.v, nil
				}
				margin := time.Duration(0)
				if mode == "缓存,提前 300 ms 刷新" {
					margin = 300 * time.Millisecond
				}
				mu.Lock()
				defer mu.Unlock()
				if cur.v == "" || time.Now().Add(margin).After(cur.exp) {
					cur = fetch()
					exps.Store(cur.v, cur.exp)
				}
				return cur.v, nil
			}
			var rejected atomic.Int64
			skew := 100 * time.Millisecond
			srv := &DemoServer{}
			addr, stop := Start(srv, grpc.UnaryInterceptor(func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
				md, _ := metadata.FromIncomingContext(ctx)
				a := md.Get("authorization")
				if len(a) == 0 {
					return nil, status.Error(codes.Unauthenticated, "没有令牌")
				}
				t := strings.TrimPrefix(a[0], "Bearer ")
				e, ok := exps.Load(t)
				if !ok || time.Now().Add(skew).After(e.(time.Time)) {
					rejected.Add(1)
					return nil, status.Error(codes.Unauthenticated, "令牌无效或已过期")
				}
				return h(ctx, req)
			}))
			conn, _ := grpc.NewClient(addr, insec, grpc.WithPerRPCCredentials(&tokenCreds{get: get}))
			cl := pb.NewDemoClient(conn)
			n := 0
			t0 := time.Now()
			for time.Since(t0) < 3*time.Second {
				do(cl, 3*time.Second)
				n++
				time.Sleep(20 * time.Millisecond)
			}
			P("%-22s 共 %3d 次调用;取令牌 %3d 次;被服务端拒绝 %3d 次(%.1f%%)", mode, n, fetches.Load(), rejected.Load(), 100*float64(rejected.Load())/float64(n))
			conn.Close()
			stop()
		}
	}

	Sec("四:令牌刚过期时 50 个并发调用:取令牌要 100 ms;不加锁 vs 加锁,各取了几次")
	for _, locked := range []bool{false, true} {
		var fetches atomic.Int64
		var mu sync.Mutex
		cur := ""
		get := func(ctx context.Context) (string, error) {
			if locked {
				mu.Lock()
				defer mu.Unlock()
			}
			if cur != "" {
				return cur, nil
			}
			fetches.Add(1)
			time.Sleep(100 * time.Millisecond)
			cur = "t"
			return cur, nil
		}
		addr, stop := Start(&DemoServer{})
		conn, _ := grpc.NewClient(addr, insec, grpc.WithPerRPCCredentials(&tokenCreds{get: get}))
		cl := pb.NewDemoClient(conn)
		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); do(cl, 5*time.Second) }()
		}
		wg.Wait()
		name := "不加锁"
		if locked {
			name = "加锁(只有一个去取,其余等待)"
		}
		P("%-26s 50 个并发调用,取令牌 %d 次", name, fetches.Load())
		conn.Close()
		stop()
	}

	Sec("五:GetRequestMetadata 返回错误时调用的结果;取令牌很慢时算在调用的 deadline 里")
	{
		addr, stop := Start(&DemoServer{})
		for _, c := range []struct {
			name string
			err  error
		}{{"普通 error", errors.New("取令牌失败")}, {"status.Error(Unavailable)", status.Error(codes.Unavailable, "令牌服务不可用")}, {"status.Error(PermissionDenied)", status.Error(codes.PermissionDenied, "无权")}} {
			c := c
			conn, _ := grpc.NewClient(addr, insec, grpc.WithPerRPCCredentials(&tokenCreds{get: func(context.Context) (string, error) { return "", c.err }}))
			P("GetRequestMetadata 返回 %-30s → 调用 %s", c.name, em(do(pb.NewDemoClient(conn), 3*time.Second)))
			conn.Close()
		}
		conn, _ := grpc.NewClient(addr, insec, grpc.WithPerRPCCredentials(&tokenCreds{get: func(ctx context.Context) (string, error) {
			select {
			case <-time.After(500 * time.Millisecond):
				return "t", nil
			case <-ctx.Done():
				return "", ctx.Err()
			}
		}}))
		t0 := time.Now()
		err := do(pb.NewDemoClient(conn), 200*time.Millisecond)
		P("取令牌要 500 ms、调用 deadline 200 ms:%s;%s 后返回", em(err), Ms(time.Since(t0)))
		conn.Close()
		stop()
	}

	Sec("六:连接级的凭证和单次调用的凭证同时存在:两个都设置 authorization,服务端看到什么")
	{
		var seen []string
		addr, stop := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
			md, _ := metadata.FromIncomingContext(ctx)
			seen = md.Get("authorization")
			return &pb.Resp{}, nil
		}})
		conn, _ := grpc.NewClient(addr, insec, grpc.WithPerRPCCredentials(&tokenCreds{get: func(context.Context) (string, error) { return "CONN-LEVEL", nil }}))
		cl := pb.NewDemoClient(conn)
		do(cl, 3*time.Second)
		P("只有连接级凭证:服务端看到 authorization = %q", seen)
		do(cl, 3*time.Second, grpc.PerRPCCredentials(&tokenCreds{get: func(context.Context) (string, error) { return "CALL-LEVEL", nil }}))
		P("再加单次调用的凭证:服务端看到 authorization = %q", seen)
		conn.Close()
		stop()
	}
}
