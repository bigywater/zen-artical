package main

import (
	"context"
	"fmt"
	"math/rand"
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

func cfg(throttle string) grpc.DialOption {
	t := ""
	if throttle != "" {
		t = `,"retryThrottling":` + throttle
	}
	return grpc.WithDefaultServiceConfig(`{"methodConfig":[{"name":[{"service":"demo.Demo"}],"retryPolicy":{"maxAttempts":3,"initialBackoff":"0.005s","maxBackoff":"0.01s","backoffMultiplier":1.5,"retryableStatusCodes":["UNAVAILABLE"]}}]` + t + `}`)
}

// flaky 的服务端:failMode 由测试修改(原子)。
type flaky struct {
	attempts atomic.Int64
	failP    atomic.Int64 // 失败概率,单位 1/1000
	rng      *rand.Rand
}

func (f *flaky) start() (string, func()) {
	return Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		f.attempts.Add(1)
		if int64(f.rng.Intn(1000)) < f.failP.Load() {
			return nil, status.Error(codes.Unavailable, "过载")
		}
		return &pb.Resp{}, nil
	}})
}

func newFlaky(p int64) *flaky {
	f := &flaky{rng: rand.New(rand.NewSource(1))}
	f.failP.Store(p)
	return f
}

func one(cl pb.DemoClient) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := cl.Unary(ctx, &pb.Req{})
	return err
}

func main() {
	const th = `{"maxTokens":10,"tokenRatio":0.1}`

	Sec("一:服务端一直 Unavailable(maxAttempts = 3):不节流与 retryThrottling {maxTokens 10, tokenRatio 0.1} 下,前 12 个调用各让服务端收到几次、40 个调用共几次")
	for _, c := range []struct{ name, th string }{{"不节流", ""}, {"节流", th}} {
		f := newFlaky(1000)
		addr, stop := f.start()
		conn, _ := grpc.NewClient(addr, insec, cfg(c.th))
		cl := pb.NewDemoClient(conn)
		var per []string
		for i := 0; i < 40; i++ {
			before := f.attempts.Load()
			one(cl)
			if i < 12 {
				per = append(per, fmt.Sprint(f.attempts.Load()-before))
			}
		}
		P("%-4s 前 12 个调用服务端各收到 [%s] 次;40 个调用服务端共收到 %d 次", c.name, strings.Join(per, " "), f.attempts.Load())
		conn.Close()
		stop()
	}

	Sec("二:恢复:把令牌用光之后,服务端变好,需要先成功多少次,失败的调用才重新被重试(每一行都是新的客户端:先让令牌用光,再成功 N 次,再来一个失败的调用)")
	for _, n := range []int{0, 20, 50, 60, 70, 80, 100} {
		f := newFlaky(1000)
		addr, stop := f.start()
		conn, _ := grpc.NewClient(addr, insec, cfg(th))
		cl := pb.NewDemoClient(conn)
		for i := 0; i < 20; i++ {
			one(cl)
		}
		f.failP.Store(0)
		for i := 0; i < n; i++ {
			one(cl)
		}
		f.failP.Store(1000)
		before := f.attempts.Load()
		one(cl)
		P("令牌用光后成功 %3d 次 → 再来一个必然失败的调用:服务端收到 %d 次", n, f.attempts.Load()-before)
		conn.Close()
		stop()
	}

	Sec("三:不同的失败概率下,2000 个调用:每个调用平均让服务端处理几次,以及最终失败的调用占比(不节流 vs 节流)")
	for _, p := range []int64{50, 200, 500, 1000} {
		for _, c := range []struct{ name, th string }{{"不节流", ""}, {"节流", th}} {
			f := newFlaky(p)
			addr, stop := f.start()
			conn, _ := grpc.NewClient(addr, insec, cfg(c.th))
			cl := pb.NewDemoClient(conn)
			fail := 0
			for i := 0; i < 2000; i++ {
				if one(cl) != nil {
					fail++
				}
			}
			P("每次尝试失败概率 %4.0f%% %-4s:每个调用平均让服务端处理 %.2f 次;最终失败 %.1f%%", float64(p)/10, c.name, float64(f.attempts.Load())/2000, 100*float64(fail)/2000)
			conn.Close()
			stop()
		}
	}

	{
		ratio := 0.1
		P("按令牌的进出估算的平衡点(每次尝试失败扣 1,每次成功加 %.1f):失败概率 p 满足 p = %.1f × (1 − p) 时令牌既不涨也不跌,p ≈ %.1f%%(忽略了重试本身的失败,只是粗算)", ratio, ratio, 100*ratio/(1+ratio))
	}

	Sec("四:retryThrottling 配置不合法时:maxTokens = 0、maxTokens = 1001、tokenRatio = 0")
	for _, t := range []string{`{"maxTokens":0,"tokenRatio":0.1}`, `{"maxTokens":1001,"tokenRatio":0.1}`, `{"maxTokens":10,"tokenRatio":0}`, `{"maxTokens":1000,"tokenRatio":0.1}`} {
		_, err := grpc.NewClient("127.0.0.1:1", insec, cfg(t))
		m := "NewClient 成功"
		if err != nil {
			m = fmt.Sprintf("NewClient 失败:%v", err)
			if len(m) > 150 {
				m = m[:150] + "…"
			}
		}
		P("%-42s → %s", t, m)
	}
}
