package main

import (
	"context"
	"fmt"
	"strings"
	"sync"
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

func sc(retry string) grpc.DialOption {
	return grpc.WithDefaultServiceConfig(fmt.Sprintf(`{"methodConfig":[{"name":[{"service":"demo.Demo"}],%s}]}`, retry))
}

func retryPol(max int, initial, maxB string, mult float64, codes string) string {
	return fmt.Sprintf(`"retryPolicy":{"maxAttempts":%d,"initialBackoff":"%s","maxBackoff":"%s","backoffMultiplier":%g,"retryableStatusCodes":[%s]}`, max, initial, maxB, mult, codes)
}

// srv 记录每次到达的时刻;前 failN 次返回 code(可选:先 SetHeader / 带 pushback trailer)。
type srv struct {
	mu      sync.Mutex
	arrive  []time.Time
	failN   int
	code    codes.Code
	setHdr  bool
	pushMs  string
	slowFst time.Duration
}

func (s *srv) impl() *DemoServer {
	return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		s.mu.Lock()
		s.arrive = append(s.arrive, time.Now())
		n := len(s.arrive)
		s.mu.Unlock()
		if n == 1 && s.slowFst > 0 {
			select {
			case <-time.After(s.slowFst):
			case <-ctx.Done():
			}
		}
		if n <= s.failN {
			if s.setHdr {
				grpc.SetHeader(ctx, metadata.Pairs("x-h", "1"))
			}
			if s.pushMs != "" {
				grpc.SetTrailer(ctx, metadata.Pairs("grpc-retry-pushback-ms", s.pushMs))
			}
			return nil, status.Error(s.code, "第 "+fmt.Sprint(n)+" 次失败")
		}
		return &pb.Resp{Msg: "ok"}, nil
	}}
}
func (s *srv) attempts() int { s.mu.Lock(); defer s.mu.Unlock(); return len(s.arrive) }
func (s *srv) gaps() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	var o []string
	for i := 1; i < len(s.arrive); i++ {
		o = append(o, fmt.Sprintf("%.0f", float64(s.arrive[i].Sub(s.arrive[i-1]).Microseconds())/1000))
	}
	return "[" + strings.Join(o, " ") + "] ms"
}

func prevAttempts(tap *Tap) string {
	var o []string
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && e.Type == "HEADERS" {
			v := "(无)"
			for _, kv := range strings.Split(e.Info, "; ") {
				if strings.HasPrefix(kv, "grpc-previous-rpc-attempts:") {
					v = strings.TrimSpace(strings.TrimPrefix(kv, "grpc-previous-rpc-attempts:"))
				}
			}
			o = append(o, v)
		}
	}
	return "[" + strings.Join(o, " ") + "]"
}

// run 起一个服务端和客户端,调用一次 Unary,返回结果。
func run(s *srv, dopt grpc.DialOption, timeout time.Duration, req *pb.Req) (*Tap, *grpc.ClientConn, time.Duration, error) {
	addr, _ := Start(s.impl())
	tap := NewTap(addr)
	conn, _ := grpc.NewClient(tap.Addr, insec, dopt)
	cl := pb.NewDemoClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	t0 := time.Now()
	_, err := cl.Unary(ctx, req)
	el := time.Since(t0)
	time.Sleep(100 * time.Millisecond)
	return tap, conn, el, err
}

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

func main() {
	Sec("一:没有重试配置 vs 配置 retryPolicy(maxAttempts 4,initialBackoff 50 ms,multiplier 2,UNAVAILABLE);服务端前 2 次返回 Unavailable")
	{
		s := &srv{failN: 2, code: codes.Unavailable}
		tap, conn, el, err := run(s, grpc.WithDefaultServiceConfig(`{}`), 5*time.Second, &pb.Req{})
		P("没有配置:服务端收到 %d 次;结果 %s", s.attempts(), em(err))
		conn.Close()
		tap.Close()
		s = &srv{failN: 2, code: codes.Unavailable}
		tap, conn, el, err = run(s, sc(retryPol(4, "0.05s", "1s", 2, `"UNAVAILABLE"`)), 5*time.Second, &pb.Req{})
		P("有配置:服务端收到 %d 次;结果 %s;总耗时 %s;每次到达的间隔 %s", s.attempts(), em(err), Ms(el), s.gaps())
		P("线上每个请求的 grpc-previous-rpc-attempts 头:%s", prevAttempts(tap))
		conn.Close()
		tap.Close()
		P("退避的取值范围(源码:initialBackoff × multiplier^n,再乘以 0.8~1.2 的随机数):第 1 次重试前 40–60 ms,第 2 次重试前 80–120 ms")
		var rows []string
		for i := 0; i < 8; i++ {
			s := &srv{failN: 2, code: codes.Unavailable}
			tap, conn, _, _ := run(s, sc(retryPol(4, "0.05s", "1s", 2, `"UNAVAILABLE"`)), 5*time.Second, &pb.Req{})
			rows = append(rows, s.gaps())
			conn.Close()
			tap.Close()
		}
		P("再重复 8 次的间隔:%s", strings.Join(rows, " "))
	}

	Sec("二:哪些错误码会重试、次数上限:Internal 不在 retryableStatusCodes 里;一直返回 Unavailable 时 maxAttempts = 4 与 maxAttempts = 10 各试几次")
	{
		s := &srv{failN: 100, code: codes.Internal}
		tap, conn, _, err := run(s, sc(retryPol(4, "0.01s", "0.1s", 2, `"UNAVAILABLE"`)), 5*time.Second, &pb.Req{})
		P("服务端返回 Internal,只允许 UNAVAILABLE 重试:服务端收到 %d 次;%s", s.attempts(), em(err))
		conn.Close()
		tap.Close()
		for _, m := range []int{4, 10} {
			s := &srv{failN: 100, code: codes.Unavailable}
			tap, conn, _, err := run(s, sc(retryPol(m, "0.01s", "0.1s", 2, `"UNAVAILABLE"`)), 10*time.Second, &pb.Req{})
			P("一直 Unavailable,配置 maxAttempts = %d:服务端收到 %d 次;%s", m, s.attempts(), em(err))
			conn.Close()
			tap.Close()
		}
	}

	Sec("三:响应头已经发出就不再重试:服务端返回 Unavailable,但在 handler 里先 grpc.SetHeader(x-h)")
	{
		for _, h := range []bool{false, true} {
			s := &srv{failN: 2, code: codes.Unavailable, setHdr: h}
			tap, conn, _, err := run(s, sc(retryPol(4, "0.01s", "0.1s", 2, `"UNAVAILABLE"`)), 5*time.Second, &pb.Req{})
			P("handler 里 SetHeader=%-5v:服务端收到 %d 次;%s", h, s.attempts(), em(err))
			conn.Close()
			tap.Close()
		}
	}

	Sec("四:retry 与 deadline:退避 initialBackoff 100 ms、multiplier 2,调用带 deadline 250 ms,服务端一直返回 Unavailable")
	{
		s := &srv{failN: 100, code: codes.Unavailable}
		tap, conn, el, err := run(s, sc(retryPol(5, "0.1s", "10s", 2, `"UNAVAILABLE"`)), 250*time.Millisecond, &pb.Req{})
		P("服务端收到 %d 次,每次到达的间隔 %s;调用 %s 后返回:%s", s.attempts(), s.gaps(), Ms(el), em(err))
		conn.Close()
		tap.Close()
	}

	Sec("五:服务端用 trailer grpc-retry-pushback-ms 指定重试等待:300 → 客户端按 300 ms 等(忽略本地退避 50 ms);-1 → 客户端不再重试")
	{
		for _, pm := range []string{"300", "-1"} {
			s := &srv{failN: 1, code: codes.Unavailable, pushMs: pm}
			tap, conn, el, err := run(s, sc(retryPol(4, "0.05s", "1s", 2, `"UNAVAILABLE"`)), 5*time.Second, &pb.Req{})
			P("pushback = %-3s:服务端收到 %d 次;到达间隔 %s;总耗时 %s;%s", pm, s.attempts(), s.gaps(), Ms(el), em(err))
			conn.Close()
			tap.Close()
		}
	}

	Sec("六:重试需要缓存请求:默认缓冲 256 KiB(读源码 rpc_util.go),请求 100 KiB 与 300 KiB 的 Unary 调用,服务端前 2 次返回 Unavailable")
	{
		for _, kb := range []int{100, 300} {
			s := &srv{failN: 2, code: codes.Unavailable}
			tap, conn, _, err := run(s, sc(retryPol(4, "0.01s", "0.1s", 2, `"UNAVAILABLE"`)), 5*time.Second, &pb.Req{Payload: make([]byte, kb*1024)})
			P("请求 %3d KiB:服务端收到 %d 次;%s", kb, s.attempts(), em(err))
			conn.Close()
			tap.Close()
		}
	}

	Sec("七:hedging(对冲):服务端第一次请求要 600 ms,之后的很快;服务配置里只写 hedgingPolicy(maxAttempts 3,hedgingDelay 100 ms)")
	{
		hed := `"hedgingPolicy":{"maxAttempts":3,"hedgingDelay":"0.1s","nonFatalStatusCodes":["UNAVAILABLE"]}`
		s := &srv{slowFst: 600 * time.Millisecond}
		tap, conn, el, err := run(s, sc(hed), 5*time.Second, &pb.Req{})
		P("hedgingPolicy:服务端收到 %d 次;总耗时 %s;%s", s.attempts(), Ms(el), em(err))
		conn.Close()
		tap.Close()
	}
}
