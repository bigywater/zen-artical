package main

import (
	"context"
	"fmt"
	"strings"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func em(err error) string {
	if err == nil {
		return "成功"
	}
	st, _ := status.FromError(err)
	return "code=" + st.Code().String()
}

// 链路:客户端 → A → B。B 的工作时间由请求里的 N(毫秒)决定,会监听 ctx。
type chain struct {
	aPre                           time.Duration // A 在调用 B 之前先耗掉的时间
	bStarted, bFinished, bCanceled atomic.Int64
	bRemain                        atomic.Int64 // B 看到的剩余 deadline(毫秒),-1 表示没有 deadline
	aTimeout                       time.Duration
	aFresh                         bool // A 调 B 时用 context.Background() 代替传入的 ctx
	aAttempts                      int
	aAttemptTimeout                time.Duration
	aAttemptsDone                  atomic.Int64
	bAddr, aAddr                   string
	tapB, tapA                     *Tap
	stops                          []func()
}

func newChain() *chain {
	c := &chain{aAttempts: 1}
	c.bRemain.Store(-2)
	bAddr, stopB := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		c.bStarted.Add(1)
		if dl, ok := ctx.Deadline(); ok {
			c.bRemain.Store(time.Until(dl).Milliseconds())
		} else {
			c.bRemain.Store(-1)
		}
		select {
		case <-time.After(time.Duration(r.N) * time.Millisecond):
			c.bFinished.Add(1)
			return &pb.Resp{}, nil
		case <-ctx.Done():
			c.bCanceled.Add(1)
			return nil, ctx.Err()
		}
	}})
	c.tapB = NewTap(bAddr)
	connB, _ := grpc.NewClient(c.tapB.Addr, insec)
	clB := pb.NewDemoClient(connB)
	aAddr, stopA := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		var err error
		time.Sleep(c.aPre)
		for i := 0; i < c.aAttempts; i++ {
			c.aAttemptsDone.Add(1)
			base := ctx
			if c.aFresh {
				base = context.Background()
			}
			cctx, cancel := base, context.CancelFunc(func() {})
			to := c.aTimeout
			if c.aAttemptTimeout > 0 {
				to = c.aAttemptTimeout
			}
			if to > 0 {
				cctx, cancel = context.WithTimeout(base, to)
			}
			_, err = clB.Unary(cctx, r)
			cancel()
			if err == nil {
				return &pb.Resp{}, nil
			}
			if ctx.Err() != nil {
				break
			}
		}
		return nil, err
	}})
	c.tapA = NewTap(aAddr)
	c.aAddr, c.bAddr = c.tapA.Addr, c.tapB.Addr
	c.stops = []func(){stopB, stopA, func() { connB.Close() }}
	return c
}
func (c *chain) close() {
	c.tapA.Close()
	c.tapB.Close()
	for _, s := range c.stops {
		s()
	}
}
func (c *chain) reset() {
	c.bStarted.Store(0)
	c.bFinished.Store(0)
	c.bCanceled.Store(0)
	c.aAttemptsDone.Store(0)
	c.bRemain.Store(-2)
	c.tapA.Reset()
	c.tapB.Reset()
}

func (c *chain) call(clientTimeout time.Duration, work int) (time.Duration, error) {
	conn, _ := grpc.NewClient(c.aAddr, insec)
	defer conn.Close()
	ctx := context.Background()
	var cancel context.CancelFunc = func() {}
	if clientTimeout > 0 {
		ctx, cancel = context.WithTimeout(ctx, clientTimeout)
	}
	defer cancel()
	t0 := time.Now()
	_, err := pb.NewDemoClient(conn).Unary(ctx, &pb.Req{N: int32(work)})
	return time.Since(t0), err
}

func timeoutHdr(tap *Tap) string {
	for _, e := range tap.Snapshot() {
		if e.Dir == "C→S" && e.Type == "HEADERS" {
			for _, kv := range strings.Split(e.Info, "; ") {
				if strings.HasPrefix(kv, "grpc-timeout:") {
					return strings.TrimSpace(strings.TrimPrefix(kv, "grpc-timeout:"))
				}
			}
			return "(无)"
		}
	}
	return "(没有请求)"
}

func main() {
	Sec("一:各层的超时取最小的:客户端 → A → B,B 干活 500 ms。客户端超时 / A 调 B 的超时 各取不同值:谁先到期,客户端看到什么、用了多久")
	{
		c := newChain()
		for _, t := range []struct{ cli, a int }{{1000, 0}, {1000, 300}, {200, 1000}, {200, 0}, {0, 0}} {
			c.reset()
			c.aTimeout = time.Duration(t.a) * time.Millisecond
			// 预热连接
			c.call(2*time.Second, 0)
			c.reset()
			el, err := c.call(time.Duration(t.cli)*time.Millisecond, 500)
			time.Sleep(50 * time.Millisecond)
			cs, as := "无", "无"
			if t.cli > 0 {
				cs = fmt.Sprintf("%d ms", t.cli)
			}
			if t.a > 0 {
				as = fmt.Sprintf("%d ms", t.a)
			}
			P("客户端超时 %-7s A 调 B 的超时 %-7s → 客户端 %s,用时 %s;B 看到的 grpc-timeout 头 %s;B 收到 %d 次、做完 %d、被取消 %d", cs, as, em(err), Ms(el), timeoutHdr(c.tapB), c.bStarted.Load(), c.bFinished.Load(), c.bCanceled.Load())
		}
		c.close()
	}

	Sec("二:deadline 沿着调用链往下传,每一跳都在变小:客户端设 1000 ms,线上 grpc-timeout 头与 B 看到的剩余时间:A 在调用 B 之前先自己耗掉 0 ms、200 ms、600 ms")
	{
		c := newChain()
		c.call(2*time.Second, 0)
		for _, pre := range []int{0, 200, 600} {
			c.aPre = time.Duration(pre) * time.Millisecond
			c.reset()
			el, err := c.call(1000*time.Millisecond, 10)
			time.Sleep(50 * time.Millisecond)
			P("A 先耗 %3d ms:客户端→A 的 grpc-timeout %s;A→B 的 grpc-timeout %s;B 看到的剩余 deadline %d ms;%s,用时 %s", pre, timeoutHdr(c.tapA), timeoutHdr(c.tapB), c.bRemain.Load(), em(err), Ms(el))
		}
		c.aPre = 0
		c.reset()
		c.call(0, 10)
		time.Sleep(50 * time.Millisecond)
		P("客户端不设超时:客户端→A 的 grpc-timeout:%s;A→B 的 grpc-timeout:%s;B 看到的剩余 deadline %d(-1 表示没有 deadline)", timeoutHdr(c.tapA), timeoutHdr(c.tapB), c.bRemain.Load())
		c.close()
	}

	Sec("三:A 重试 B:每次尝试的超时 400 ms,最多 3 次,B 干活 1000 ms;客户端超时 1000 ms、2000 ms、不设置。A 实际试了几次,客户端等了多久")
	{
		c := newChain()
		c.aAttempts = 3
		c.aAttemptTimeout = 400 * time.Millisecond
		c.call(5*time.Second, 0)
		for _, cli := range []int{1000, 2000, 0} {
			c.reset()
			el, err := c.call(time.Duration(cli)*time.Millisecond, 1000)
			time.Sleep(100 * time.Millisecond)
			cs := "无"
			if cli > 0 {
				cs = fmt.Sprintf("%d ms", cli)
			}
			P("客户端超时 %-7s → A 实际尝试 %d 次(B 收到 %d 次、被取消 %d);客户端 %s,用时 %s", cs, c.aAttemptsDone.Load(), c.bStarted.Load(), c.bCanceled.Load(), em(err), Ms(el))
		}
		c.close()
	}

	Sec("四:A 调 B 时不传 ctx(用 context.Background() + 2 秒超时):客户端 200 ms 就放弃了,B 的活还要做 1500 ms")
	{
		for _, fresh := range []bool{false, true} {
			c := newChain()
			c.aFresh = fresh
			c.aTimeout = 2 * time.Second
			c.call(5*time.Second, 0)
			c.reset()
			el, err := c.call(200*time.Millisecond, 1500)
			time.Sleep(100 * time.Millisecond)
			cancelledAt100 := c.bCanceled.Load()
			time.Sleep(1700 * time.Millisecond)
			name := "A 传 ctx"
			if fresh {
				name = "A 用 Background"
			}
			P("%-16s 客户端 %s,用时 %s;放弃后 100 ms:B 被取消 %d 次;1.8 秒后:B 做完 %d 次、被取消 %d 次", name, em(err), Ms(el), cancelledAt100, c.bFinished.Load(), c.bCanceled.Load())
			c.close()
		}
	}
}
