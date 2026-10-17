package main

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
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

// counter 统计服务端 handler 的并发数峰值和调用次数。
type counter struct{ cur, peak, calls atomic.Int64 }

func (c *counter) enter() {
	c.calls.Add(1)
	n := c.cur.Add(1)
	for {
		p := c.peak.Load()
		if n <= p || c.peak.CompareAndSwap(p, n) {
			break
		}
	}
}
func (c *counter) leave() { c.cur.Add(-1) }

func sleepSrv(c *counter, d time.Duration) *DemoServer {
	return &DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		c.enter()
		defer c.leave()
		select {
		case <-time.After(d):
		case <-ctx.Done():
			return nil, ctx.Err()
		}
		return &pb.Resp{}, nil
	}}
}

func count(tap *Tap, dir, typ string) int {
	n := 0
	for _, e := range tap.Snapshot() {
		if e.Dir == dir && e.Type == typ {
			n++
		}
	}
	return n
}

func main() {
	Sec("一:服务端用 MaxConcurrentStreams(4) 时,连接开头的 SETTINGS 帧里有没有 MAX_CONCURRENT_STREAMS;不设置时呢")
	for _, lim := range []uint32{0, 4} {
		var opts []grpc.ServerOption
		if lim > 0 {
			opts = append(opts, grpc.MaxConcurrentStreams(lim))
		}
		addr, stop := Start(&DemoServer{}, opts...)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		pb.NewDemoClient(conn).Unary(context.Background(), &pb.Req{})
		time.Sleep(50 * time.Millisecond)
		for _, e := range tap.Snapshot() {
			if e.Dir == "S→C" && e.Type == "SETTINGS" && !strings.Contains(e.Flags, "ACK") && e.Info != "" {
				P("MaxConcurrentStreams(%d):服务端第一个 SETTINGS:%s", lim, e.Info)
				break
			}
		}
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("二:一条连接上同时发 20 个调用,每个 handler 睡 200 ms:服务端同时在处理的调用数(峰值)和总耗时,限制 4 与不限制对比")
	for _, lim := range []uint32{0, 4} {
		var opts []grpc.ServerOption
		if lim > 0 {
			opts = append(opts, grpc.MaxConcurrentStreams(lim))
		}
		var c counter
		addr, stop := Start(sleepSrv(&c, 200*time.Millisecond), opts...)
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{}) // 先建好连接
		c.peak.Store(0)
		c.calls.Store(0)
		tap.Reset()
		var wg sync.WaitGroup
		var mu sync.Mutex
		var done []time.Duration
		t0 := time.Now()
		for i := 0; i < 20; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				_, err := cl.Unary(context.Background(), &pb.Req{})
				if err != nil {
					panic(err)
				}
				mu.Lock()
				done = append(done, time.Since(t0))
				mu.Unlock()
			}()
		}
		time.Sleep(100 * time.Millisecond)
		hdrAt100 := count(tap, "C→S", "HEADERS")
		wg.Wait()
		total := time.Since(t0)
		time.Sleep(50 * time.Millisecond)
		sort.Slice(done, func(i, j int) bool { return done[i] < done[j] })
		buckets := map[int]int{}
		for _, d := range done {
			buckets[int(d.Milliseconds())/200]++
		}
		var bs []string
		for b := 0; b < 8; b++ {
			if buckets[b] > 0 {
				bs = append(bs, fmt.Sprintf("%d–%d ms:%d 个", b*200, b*200+200, buckets[b]))
			}
		}
		name := "不限制"
		if lim > 0 {
			name = fmt.Sprintf("限制 %d", lim)
		}
		P("%s:服务端 handler 同时在处理的峰值 %d;总耗时 %s;前 100 ms 内客户端发出的 HEADERS %d 个;RST_STREAM %d 个;所有 20 个都成功", name, c.peak.Load(), Ms(total), hdrAt100, count(tap, "C→S", "RST_STREAM")+count(tap, "S→C", "RST_STREAM"))
		P("    完成时刻分布:%s", strings.Join(bs, ";"))
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("三:排队的时间算在 deadline 里:限制 4、handler 200 ms、20 个调用各带 500 ms 的 deadline")
	for round := 1; round <= 3; round++ {
		var c counter
		addr, stop := Start(sleepSrv(&c, 200*time.Millisecond), grpc.MaxConcurrentStreams(4))
		tap := NewTap(addr)
		conn, _ := grpc.NewClient(tap.Addr, insec)
		cl := pb.NewDemoClient(conn)
		ctx0, c0 := context.WithTimeout(context.Background(), 2*time.Second)
		cl.Unary(ctx0, &pb.Req{})
		c0()
		c.calls.Store(0)
		tap.Reset()
		var wg sync.WaitGroup
		var ok, dl, other atomic.Int64
		for i := 0; i < 20; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
				defer cancel()
				_, err := cl.Unary(ctx, &pb.Req{})
				switch status.Code(err) {
				case codes.OK:
					ok.Add(1)
				case codes.DeadlineExceeded:
					dl.Add(1)
				default:
					other.Add(1)
				}
			}()
		}
		wg.Wait()
		time.Sleep(100 * time.Millisecond)
		P("第 %d 轮:成功 %d 个,DeadlineExceeded %d 个,其它 %d 个", round, ok.Load(), dl.Load(), other.Load())
		P("    服务端 handler 实际被调用 %d 次;客户端发出的 HEADERS %d 个;客户端发出的 RST_STREAM %d 个", c.calls.Load(), count(tap, "C→S", "HEADERS"), count(tap, "C→S", "RST_STREAM"))
		var w [4]int
		for _, e := range tap.Snapshot() {
			if e.Dir == "C→S" && e.Type == "HEADERS" {
				ms := e.T.Milliseconds()
				switch {
				case ms < 100:
					w[0]++
				case ms < 300:
					w[1]++
				case ms < 450:
					w[2]++
				default:
					w[3]++
				}
			}
		}
		P("    客户端发出 HEADERS 的时刻分布:0–100 ms %d 个;100–300 ms %d 个;300–450 ms %d 个;450 ms 之后 %d 个", w[0], w[1], w[2], w[3])
		conn.Close()
		tap.Close()
		stop()
	}

	Sec("四:限制是“每条连接”的:40 个并发调用、handler 100 ms、每条连接限制 4,客户端用 1、2、4、10 条连接(应用自己轮流分配)")
	for _, k := range []int{1, 2, 4, 10} {
		var c counter
		addr, stop := Start(sleepSrv(&c, 100*time.Millisecond), grpc.MaxConcurrentStreams(4))
		var cls []pb.DemoClient
		var conns []*grpc.ClientConn
		for i := 0; i < k; i++ {
			conn, _ := grpc.NewClient(addr, insec)
			conns = append(conns, conn)
			cls = append(cls, pb.NewDemoClient(conn))
			cls[i].Unary(context.Background(), &pb.Req{})
		}
		c.peak.Store(0)
		var wg sync.WaitGroup
		t0 := time.Now()
		for i := 0; i < 40; i++ {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				cls[i%k].Unary(context.Background(), &pb.Req{})
			}(i)
		}
		wg.Wait()
		P("%2d 条连接:服务端同时处理的峰值 %d;40 个调用总耗时 %s", k, c.peak.Load(), Ms(time.Since(t0)))
		for _, cn := range conns {
			cn.Close()
		}
		stop()
	}

	Sec("五:长流占着名额:限制 2,先开 2 个一直不结束的服务端流,再发一个普通的 Unary 调用,它要等多久")
	{
		var c counter
		release := make(chan struct{})
		var started atomic.Int64
		var unaryAt atomic.Int64
		srv := &DemoServer{
			OnServerStream: func(r *pb.Req, st pb.Demo_ServerStreamServer) error {
				started.Add(1)
				<-release
				return nil
			},
			OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
				c.enter()
				defer c.leave()
				return &pb.Resp{}, nil
			},
		}
		addr, stop := Start(srv, grpc.MaxConcurrentStreams(2))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		cl.Unary(context.Background(), &pb.Req{})
		c.calls.Store(0)
		for i := 0; i < 2; i++ {
			if _, err := cl.ServerStream(context.Background(), &pb.Req{}); err != nil {
				panic(err)
			}
		}
		for started.Load() < 2 {
			time.Sleep(time.Millisecond)
		}
		t0 := time.Now()
		res := make(chan time.Duration, 1)
		go func() {
			_, err := cl.Unary(context.Background(), &pb.Req{})
			if err != nil {
				panic(err)
			}
			res <- time.Since(t0)
		}()
		time.Sleep(600 * time.Millisecond)
		unaryAt.Store(c.calls.Load())
		P("2 个长流占满名额 600 ms 后:这个 Unary 调用已到达服务端的次数 %d(没有到达就还在客户端排队)", unaryAt.Load())
		close(release)
		d := <-res
		P("长流结束(释放)之后,Unary 调用在开始后 %s 才完成;服务端 handler 共被调用 %d 次", Ms(d), c.calls.Load())
		conn.Close()
		stop()
	}

	Sec("六:服务端不设限制时,一条连接上 300 个并发调用(handler 200 ms),服务端同时处理的峰值是多少(客户端在拿到服务端 SETTINGS 之前的默认配额读源码是 100)")
	{
		var c counter
		addr, stop := Start(sleepSrv(&c, 200*time.Millisecond))
		conn, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(conn)
		var wg sync.WaitGroup
		t0 := time.Now()
		for i := 0; i < 300; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); cl.Unary(context.Background(), &pb.Req{}) }()
		}
		wg.Wait()
		P("全新的连接上直接发 300 个并发调用(没有预热):峰值 %d;总耗时 %s", c.peak.Load(), Ms(time.Since(t0)))
		conn.Close()
		stop()
	}
}
