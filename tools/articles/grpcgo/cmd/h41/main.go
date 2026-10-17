package main

import (
	"context"
	"fmt"
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

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

// B:按请求里的 N 返回对应的 gRPC code(0 表示成功);记录收到次数;Msg=="slow" 时睡 1 秒。
type bsrv struct {
	calls atomic.Int64
	arr   []time.Duration
	t0    time.Time
}

func (b *bsrv) start() (string, func()) {
	return Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		b.calls.Add(1)
		b.arr = append(b.arr, time.Since(b.t0))
		if r.Msg == "slow" {
			select {
			case <-time.After(1 * time.Second):
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}
		if r.N != 0 {
			return nil, status.Error(codes.Code(r.N), "B 内部错误:库表 orders_v2 找不到,连接 10.0.0.5:5432 失败")
		}
		return &pb.Resp{}, nil
	}})
}

// translate 是 A 的翻译策略(这是我的示例做法):不是客户端的错,也不是客户端能修的错,都不原样往外传。
func translate(err error) error {
	st := status.Convert(err)
	switch st.Code() {
	case codes.OK:
		return nil
	case codes.NotFound, codes.AlreadyExists, codes.ResourceExhausted, codes.Unavailable, codes.Canceled:
		return status.Error(st.Code(), "下游服务:"+st.Code().String())
	case codes.DeadlineExceeded:
		return status.Error(codes.Unavailable, "下游服务超时")
	default: // InvalidArgument、FailedPrecondition、Unauthenticated、PermissionDenied、Internal、Unknown……
		return status.Error(codes.Internal, "下游服务出错")
	}
}

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	return st.Code().String()
}

func newA(bAddr string, mode string, timeout time.Duration, attempts int, retryCfg string) (string, func(), *grpc.ClientConn) {
	opts := []grpc.DialOption{insec}
	if retryCfg != "" {
		opts = append(opts, grpc.WithDefaultServiceConfig(retryCfg))
	}
	connB, _ := grpc.NewClient(bAddr, opts...)
	clB := pb.NewDemoClient(connB)
	addr, stop := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		var err error
		for i := 0; i < attempts; i++ {
			cctx := ctx
			cancel := context.CancelFunc(func() {})
			if timeout > 0 {
				cctx, cancel = context.WithTimeout(ctx, timeout)
			}
			_, err = clB.Unary(cctx, r)
			cancel()
			if err == nil || status.Code(err) != codes.Unavailable {
				break
			}
		}
		if err == nil {
			return &pb.Resp{}, nil
		}
		if mode == "translate" {
			return nil, translate(err)
		}
		return nil, err
	}})
	return addr, func() { stop(); connB.Close() }, connB
}

func retryJSON(max int) string {
	return fmt.Sprintf(`{"methodConfig":[{"name":[{"service":"demo.Demo"}],"retryPolicy":{"maxAttempts":%d,"initialBackoff":"0.01s","maxBackoff":"0.05s","backoffMultiplier":2,"retryableStatusCodes":["UNAVAILABLE"]}}]}`, max)
}

func main() {
	Sec("一:客户端 → A → B:B 返回各种错误码,A 原样往外传 vs 按我的策略翻译,客户端看到的 code(翻译策略:NotFound、AlreadyExists、ResourceExhausted、Unavailable、Canceled 保持;DeadlineExceeded → Unavailable;其余 → Internal)")
	{
		b := &bsrv{}
		bAddr, stopB := b.start()
		aPass, stopP, _ := newA(bAddr, "pass", 0, 1, "")
		aTr, stopT, _ := newA(bAddr, "translate", 0, 1, "")
		cp, _ := grpc.NewClient(aPass, insec)
		ct, _ := grpc.NewClient(aTr, insec)
		P("%-20s %-20s %s", "B 返回", "A 原样透传 → 客户端", "A 翻译 → 客户端")
		for _, c := range []codes.Code{codes.NotFound, codes.InvalidArgument, codes.Unauthenticated, codes.PermissionDenied, codes.FailedPrecondition, codes.ResourceExhausted, codes.Unavailable, codes.DeadlineExceeded, codes.Internal} {
			_, e1 := pb.NewDemoClient(cp).Unary(context.Background(), &pb.Req{N: int32(c)})
			_, e2 := pb.NewDemoClient(ct).Unary(context.Background(), &pb.Req{N: int32(c)})
			P("%-20s %-20s %s", c, em(e1), em(e2))
		}
		cp.Close()
		ct.Close()
		stopP()
		stopT()
		stopB()
	}

	Sec("二:错误信息会泄漏内部细节:B 的错误 message 里有库表名和内网地址;客户端看到的 message(透传 vs 翻译)")
	{
		b := &bsrv{}
		bAddr, stopB := b.start()
		aPass, stopP, _ := newA(bAddr, "pass", 0, 1, "")
		aTr, stopT, _ := newA(bAddr, "translate", 0, 1, "")
		for _, c := range []struct {
			name, addr string
		}{{"透传", aPass}, {"翻译", aTr}} {
			cn, _ := grpc.NewClient(c.addr, insec)
			_, err := pb.NewDemoClient(cn).Unary(context.Background(), &pb.Req{N: int32(codes.Internal)})
			st, _ := status.FromError(err)
			P("%s:客户端看到 code=%s message=%q", c.name, st.Code(), st.Message())
			cn.Close()
		}
		// B 整个不可达
		stopB()
		time.Sleep(100 * time.Millisecond)
		for _, c := range []struct {
			name, addr string
		}{{"透传", aPass}, {"翻译", aTr}} {
			cn, _ := grpc.NewClient(c.addr, insec)
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			_, err := pb.NewDemoClient(cn).Unary(ctx, &pb.Req{})
			cancel()
			st, _ := status.FromError(err)
			m := st.Message()
			if len(m) > 110 {
				m = m[:110] + "…"
			}
			P("B 已经停掉,%s:客户端看到 code=%s message=%q", c.name, st.Code(), m)
			cn.Close()
		}
		stopP()
		stopT()
	}

	Sec("三:重试放大:B 一直返回 Unavailable。客户端有重试策略(最多 3 次 UNAVAILABLE),A 调 B 也有重试(最多 3 次)——一次客户端调用让 B 收到几次")
	{
		for _, c := range []struct {
			name      string
			aAttempts int
			aRetryCfg string
			cliCfg    string
		}{
			{"只有客户端重试 3 次", 1, "", retryJSON(3)},
			{"客户端 3 次 × A 应用层重试 3 次", 3, "", retryJSON(3)},
			{"客户端 3 次 × A 的 gRPC 重试策略 3 次", 1, retryJSON(3), retryJSON(3)},
			{"只有 A 重试 3 次(客户端不重试)", 3, "", ""},
		} {
			b := &bsrv{}
			bAddr, stopB := b.start()
			aAddr, stopA, _ := newA(bAddr, "pass", 0, c.aAttempts, c.aRetryCfg)
			opts := []grpc.DialOption{insec}
			if c.cliCfg != "" {
				opts = append(opts, grpc.WithDefaultServiceConfig(c.cliCfg))
			}
			cn, _ := grpc.NewClient(aAddr, opts...)
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			_, err := pb.NewDemoClient(cn).Unary(ctx, &pb.Req{N: int32(codes.Unavailable)})
			cancel()
			time.Sleep(100 * time.Millisecond)
			P("%-34s B 收到 %d 次;客户端最终:%s", c.name, b.calls.Load(), em(err))
			cn.Close()
			stopA()
			stopB()
		}
	}

	Sec("四:下游超时该翻译成什么:A 调 B 带 300 ms 超时(B 要 1 秒),客户端有 2 秒 deadline 与“UNAVAILABLE 重试 3 次”的策略。A 把 B 的超时 透传(DeadlineExceeded)vs 翻译成 Unavailable——客户端看到的 code、B 收到的次数、总耗时")
	{
		for _, mode := range []string{"pass", "translate"} {
			b := &bsrv{}
			bAddr, stopB := b.start()
			aAddr, stopA, _ := newA(bAddr, mode, 300*time.Millisecond, 1, "")
			cn, _ := grpc.NewClient(aAddr, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithDefaultServiceConfig(retryJSON(3)))
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			t0 := time.Now()
			b.t0 = t0
			_, err := pb.NewDemoClient(cn).Unary(ctx, &pb.Req{Msg: "slow"})
			el := time.Since(t0)
			cancel()
			time.Sleep(100 * time.Millisecond)
			name := "透传(DeadlineExceeded)"
			if mode == "translate" {
				name = "翻译(Unavailable)"
			}
			P("%-24s 客户端最终 %s,用了 %s;B 收到 %d 次,到达时刻 %v", name, em(err), Ms(el), b.calls.Load(), b.arr)
			cn.Close()
			stopA()
			stopB()
		}
	}
	_ = strings.Join
}
