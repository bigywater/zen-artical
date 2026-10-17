package main

import (
	"context"
	"fmt"
	"io"
	"net"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/resolver"
	"google.golang.org/grpc/resolver/manual"
	"google.golang.org/grpc/status"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

type backend struct {
	idx  int
	addr string
	hits atomic.Int64
	stop func()
}

func newBackend(idx int, opts ...grpc.ServerOption) *backend {
	b := &backend{idx: idx}
	b.addr, b.stop = Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		b.hits.Add(1)
		return &pb.Resp{N: int32(idx)}, nil
	}}, opts...)
	return b
}

// l4 是一个四层(TCP)负载均衡器:每接受一条新连接,就按轮流顺序选一个后端,之后只搬运字节,看不懂 HTTP/2。
type l4 struct {
	Addr  string
	ln    net.Listener
	mu    sync.Mutex
	bs    []*backend
	next  int
	conns atomic.Int64
}

func newL4(bs []*backend) *l4 {
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", FreePort()))
	if err != nil {
		panic(err)
	}
	l := &l4{Addr: ln.Addr().String(), ln: ln, bs: bs}
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			l.mu.Lock()
			b := l.bs[l.next%len(l.bs)]
			l.next++
			l.mu.Unlock()
			l.conns.Add(1)
			s, err := net.Dial("tcp", b.addr)
			if err != nil {
				c.Close()
				continue
			}
			go func() { io.Copy(s, c); s.Close() }()
			go func() { io.Copy(c, s); c.Close() }()
		}
	}()
	return l
}
func (l *l4) add(b *backend) { l.mu.Lock(); l.bs = append(l.bs, b); l.mu.Unlock() }
func (l *l4) close()         { l.ln.Close() }

func hits(bs []*backend) []int64 {
	var o []int64
	for _, b := range bs {
		o = append(o, b.hits.Load())
	}
	return o
}
func reset(bs []*backend) {
	for _, b := range bs {
		b.hits.Store(0)
	}
}
func calls(cl pb.DemoClient, n int) int {
	fail := 0
	for i := 0; i < n; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		if _, err := cl.Unary(ctx, &pb.Req{}); err != nil {
			fail++
		}
		cancel()
	}
	return fail
}

func main() {
	Sec("一:四层负载均衡器后面的长连接:6 个客户端各连一次(均衡器按连接轮流分给 2 个后端),各发 100 次调用;然后加入第 3 个后端,6 个客户端再各发 100 次;最后再新建 3 个客户端各发 100 次")
	{
		bs := []*backend{newBackend(0), newBackend(1)}
		lb := newL4(bs)
		var cls []pb.DemoClient
		var conns []*grpc.ClientConn
		for i := 0; i < 6; i++ {
			c, _ := grpc.NewClient(lb.Addr, insec)
			conns = append(conns, c)
			cls = append(cls, pb.NewDemoClient(c))
		}
		for _, cl := range cls {
			calls(cl, 100)
		}
		P("2 个后端时,6 个客户端各发 100 次:各后端收到 %v;均衡器接受的连接 %d 条", hits(bs), lb.conns.Load())
		b3 := newBackend(2)
		lb.add(b3)
		bs = append(bs, b3)
		reset(bs)
		for _, cl := range cls {
			calls(cl, 100)
		}
		P("加入第 3 个后端后,原来的 6 个客户端再各发 100 次:各后端收到 %v;均衡器接受的连接仍是 %d 条", hits(bs), lb.conns.Load())
		reset(bs)
		var extra []*grpc.ClientConn
		for i := 0; i < 3; i++ {
			c, _ := grpc.NewClient(lb.Addr, insec)
			extra = append(extra, c)
			calls(pb.NewDemoClient(c), 100)
		}
		P("再新建 3 个客户端各发 100 次:各后端收到 %v;均衡器接受的连接 %d 条", hits(bs), lb.conns.Load())
		for _, c := range extra {
			c.Close()
		}
		for _, c := range conns {
			c.Close()
		}
		lb.close()
		for _, b := range bs {
			b.stop()
		}
	}

	Sec("二:请求量不均的客户端:4 个客户端经四层均衡器连 2 个后端,调用次数分别是 1000、100、100、100")
	{
		bs := []*backend{newBackend(0), newBackend(1)}
		lb := newL4(bs)
		loads := []int{1000, 100, 100, 100}
		var wg sync.WaitGroup
		var conns []*grpc.ClientConn
		var cls []pb.DemoClient
		for range loads {
			c, _ := grpc.NewClient(lb.Addr, insec)
			conns = append(conns, c)
			cl := pb.NewDemoClient(c)
			cls = append(cls, cl)
			calls(cl, 1) // 按顺序建立连接,让连接分配可复现
		}
		reset(bs)
		for i, n := range loads {
			wg.Add(1)
			go func(i, n int) { defer wg.Done(); calls(cls[i], n) }(i, n)
		}
		wg.Wait()
		h := hits(bs)
		P("4 个客户端轮流被分到 2 个后端(每个后端 2 条连接),但请求数:各后端收到 %v(后端 0 占 %.0f%%)", h, 100*float64(h[0])/float64(h[0]+h[1]))
		for _, c := range conns {
			c.Close()
		}
		lb.close()
		for _, b := range bs {
			b.stop()
		}
	}

	Sec("三:客户端自己做 round_robin(直接拿到 3 个后端地址)时,同样不均匀的客户端负载:每个请求都轮流,后端收到的次数")
	{
		bs := []*backend{newBackend(0), newBackend(1), newBackend(2)}
		loads := []int{1000, 100, 100, 100}
		var wg sync.WaitGroup
		for _, n := range loads {
			r := manual.NewBuilderWithScheme("demo")
			var as []resolver.Address
			for _, b := range bs {
				as = append(as, resolver.Address{Addr: b.addr})
			}
			r.InitialState(resolver.State{Addresses: as})
			c, _ := grpc.NewClient("demo:///svc", insec, grpc.WithResolvers(r), grpc.WithDefaultServiceConfig(`{"loadBalancingConfig":[{"round_robin":{}}]}`))
			cl := pb.NewDemoClient(c)
			calls(cl, 3)
			defer c.Close()
			wg.Add(1)
			go func(n int) { defer wg.Done(); calls(cl, n) }(n)
		}
		reset(bs)
		wg.Wait()
		P("1000+100+100+100 次调用,各后端收到 %v", hits(bs))
		for _, b := range bs {
			b.stop()
		}
	}

	Sec("四:服务端 MaxConnectionAge 让长连接定期重建:后端设 MaxConnectionAge = 1 s(宽限 1 s),经四层均衡器;6 个客户端每 20 ms 调用一次;第 2 秒加入第 3 个后端")
	{
		ka := grpc.KeepaliveParams(keepalive.ServerParameters{MaxConnectionAge: 1 * time.Second, MaxConnectionAgeGrace: 1 * time.Second})
		bs := []*backend{newBackend(0, ka), newBackend(1, ka)}
		lb := newL4(bs)
		var stopAll atomic.Bool
		var wg sync.WaitGroup
		var failed atomic.Int64
		var conns []*grpc.ClientConn
		for i := 0; i < 6; i++ {
			c, _ := grpc.NewClient(lb.Addr, insec)
			conns = append(conns, c)
			cl := pb.NewDemoClient(c)
			wg.Add(1)
			go func() {
				defer wg.Done()
				for !stopAll.Load() {
					failed.Add(int64(calls(cl, 1)))
					time.Sleep(20 * time.Millisecond)
				}
			}()
		}
		var b3 *backend
		type snap struct {
			t float64
			h []int64
		}
		var snaps []snap
		t0 := time.Now()
		for sec := 1; sec <= 8; sec++ {
			time.Sleep(time.Until(t0.Add(time.Duration(sec) * time.Second)))
			if sec == 2 {
				b3 = newBackend(2, ka)
				lb.add(b3)
				bs = append(bs, b3)
			}
			snaps = append(snaps, snap{time.Since(t0).Seconds(), hits(bs)})
			reset(bs)
		}
		stopAll.Store(true)
		wg.Wait()
		for _, s := range snaps {
			P("第 %.0f 秒内各后端收到的次数 %v", s.t, s.h)
		}
		P("整个过程中失败的调用 %d 个;均衡器共接受 %d 条连接", failed.Load(), lb.conns.Load())
		_ = status.Code
		for _, c := range conns {
			c.Close()
		}
		lb.close()
		for _, b := range bs {
			b.stop()
		}
	}
}
