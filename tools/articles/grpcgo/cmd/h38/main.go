package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"math/rand"
	"os"
	"os/exec"
	"runtime"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	. "grpcgo/common"
	"grpcgo/pb"
)

var insec = grpc.WithTransportCredentials(insecure.NewCredentials())

func us(d time.Duration) string { return fmt.Sprintf("%d µs", d.Microseconds()) }

func pct(ds []time.Duration, p float64) time.Duration {
	sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })
	return ds[int(float64(len(ds)-1)*p)]
}

// pool 是应用层的连接池:n 条 ClientConn,按策略选一条。
type pool struct {
	cs       []*grpc.ClientConn
	cls      []pb.DemoClient
	inflight []atomic.Int64
	rr       atomic.Uint64
}

func newPool(addr string, n int, connect bool) *pool {
	p := &pool{inflight: make([]atomic.Int64, n)}
	for i := 0; i < n; i++ {
		c, _ := grpc.NewClient(addr, insec)
		if connect {
			c.Connect()
		}
		p.cs = append(p.cs, c)
		p.cls = append(p.cls, pb.NewDemoClient(c))
	}
	return p
}
func (p *pool) close() {
	for _, c := range p.cs {
		c.Close()
	}
}

func (p *pool) pick(strategy string) int {
	switch strategy {
	case "random":
		return rand.Intn(len(p.cs))
	case "least":
		best, bv := 0, int64(1<<60)
		start := int(p.rr.Add(1)) % len(p.cs)
		for k := 0; k < len(p.cs); k++ {
			i := (start + k) % len(p.cs)
			if v := p.inflight[i].Load(); v < bv {
				best, bv = i, v
			}
		}
		return best
	}
	return int(p.rr.Add(1)) % len(p.cs)
}

func (p *pool) call(strategy string, req *pb.Req) error {
	i := p.pick(strategy)
	p.inflight[i].Add(1)
	defer p.inflight[i].Add(-1)
	_, err := p.cls[i].Unary(context.Background(), req)
	return err
}

func runLoad(workers int, dur time.Duration, f func() error) (qps float64, p50, p99 time.Duration) {
	var stop atomic.Bool
	var wg sync.WaitGroup
	var mu sync.Mutex
	var all []time.Duration
	t0 := time.Now()
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var mine []time.Duration
			for !stop.Load() {
				s := time.Now()
				f()
				mine = append(mine, time.Since(s))
			}
			mu.Lock()
			all = append(all, mine...)
			mu.Unlock()
		}()
	}
	time.Sleep(dur)
	stop.Store(true)
	wg.Wait()
	el := time.Since(t0)
	return float64(len(all)) / el.Seconds(), pct(all, 0.5), pct(all, 0.99)
}

// ---------- 子进程:只做服务端,可以报告 goroutine 与内存 ----------

func child(opts string) {
	var so []grpc.ServerOption
	var sleepFn func(r *pb.Req) time.Duration
	switch opts {
	case "limit100":
		so = append(so, grpc.MaxConcurrentStreams(100))
		sleepFn = func(r *pb.Req) time.Duration { return 10 * time.Millisecond }
	case "limit8":
		so = append(so, grpc.MaxConcurrentStreams(8))
		sleepFn = func(r *pb.Req) time.Duration {
			if r.N == 1 {
				return 200 * time.Millisecond
			}
			return 1 * time.Millisecond
		}
	default:
		sleepFn = func(r *pb.Req) time.Duration { return 0 }
	}
	addr, _ := Start(&DemoServer{OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) {
		if d := sleepFn(r); d > 0 {
			time.Sleep(d)
		}
		return &pb.Resp{}, nil
	}}, so...)
	fmt.Println(addr)
	sc := bufio.NewScanner(os.Stdin)
	for sc.Scan() {
		if sc.Text() == "stat" {
			runtime.GC()
			runtime.GC()
			var m runtime.MemStats
			runtime.ReadMemStats(&m)
			fmt.Printf("%d %d %d\n", runtime.NumGoroutine(), m.HeapAlloc, m.StackInuse)
		}
	}
}

type proc struct {
	cmd  *exec.Cmd
	in   io.WriteCloser
	out  *bufio.Reader
	addr string
}

func spawn(opts string) *proc {
	cmd := exec.Command(os.Args[0], "child", opts)
	in, _ := cmd.StdinPipe()
	o, _ := cmd.StdoutPipe()
	cmd.Start()
	rd := bufio.NewReader(o)
	a, _ := rd.ReadString('\n')
	return &proc{cmd, in, rd, strings.TrimSpace(a)}
}
func (p *proc) stat() (g, heap, stack int64) {
	fmt.Fprintln(p.in, "stat")
	l, _ := p.out.ReadString('\n')
	fmt.Sscan(l, &g, &heap, &stack)
	return
}
func (p *proc) close() { p.in.Close(); p.cmd.Wait() }

func main() {
	if len(os.Args) > 1 && os.Args[1] == "child" {
		child(os.Args[2])
		return
	}

	Sec("一:服务端 MaxConcurrentStreams(100)、handler 10 ms、400 个并发调用者:连接池大小 1、2、4、8 的吞吐(理论上限 = 连接数 × 100 / 10 ms)")
	{
		p := spawn("limit100")
		for _, n := range []int{1, 2, 4, 8} {
			pl := newPool(p.addr, n, true)
			time.Sleep(100 * time.Millisecond)
			q, p50, p99 := runLoad(400, 2*time.Second, func() error { return pl.call("rr", &pb.Req{}) })
			P("%d 条连接:%7.0f 请求/秒(理论上限 %d);p50 %s、p99 %s", n, q, n*100*100, us(p50), us(p99))
			pl.close()
		}
		p.close()
	}

	Sec("二:选连接的策略:服务端 MaxConcurrentStreams(8),10% 的请求是慢请求(200 ms),其余 1 ms;48 个并发调用者(多于 4 × 8 = 32 个名额),池里 4 条连接,轮流 vs 随机 vs 选在途最少的")
	{
		p := spawn("limit8")
		for _, st := range []string{"rr", "random", "least"} {
			pl := newPool(p.addr, 4, true)
			time.Sleep(100 * time.Millisecond)
			rng := rand.New(rand.NewSource(1))
			var mu sync.Mutex
			q, p50, p99 := runLoad(48, 3*time.Second, func() error {
				mu.Lock()
				slow := rng.Intn(100) < 10
				mu.Unlock()
				n := int32(0)
				if slow {
					n = 1
				}
				return pl.call(st, &pb.Req{N: n})
			})
			name := map[string]string{"rr": "轮流", "random": "随机", "least": "在途最少"}[st]
			P("%-6s %7.0f 请求/秒;p50 %s、p99 %s", name, q, us(p50), us(p99))
			pl.close()
		}
		p.close()
	}

	Sec("三:冷启动:新建 8 条连接的池后马上发 200 个并发调用,第一批调用的延迟:建池时调用了 Connect() 并等待 vs 没有预热")
	{
		p := spawn("none")
		for _, warm := range []bool{false, true} {
			pl := newPool(p.addr, 8, warm)
			if warm {
				time.Sleep(200 * time.Millisecond)
			}
			var mu sync.Mutex
			var ds []time.Duration
			var wg sync.WaitGroup
			t0 := time.Now()
			for i := 0; i < 200; i++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					s := time.Now()
					pl.call("rr", &pb.Req{})
					mu.Lock()
					ds = append(ds, time.Since(s))
					mu.Unlock()
				}()
			}
			wg.Wait()
			name := "没有预热"
			if warm {
				name = "Connect() 并等 200 ms"
			}
			P("%-22s 200 个并发调用:p50 %s、p99 %s、最慢 %s;总耗时 %s", name, us(pct(ds, 0.5)), us(pct(ds, 0.99)), us(pct(ds, 1)), Ms(time.Since(t0)))
			pl.close()
		}
		p.close()
	}

	Sec("四:一条空闲连接的代价:服务端子进程里 1000 条连接(都已建立、没有请求)的 goroutine 数与内存(runtime.GC 之后)")
	{
		p := spawn("none")
		g0, h0, s0 := p.stat()
		pl := newPool(p.addr, 1000, true)
		time.Sleep(2 * time.Second)
		g1, h1, s1 := p.stat()
		P("基线 %d 个 goroutine;1000 条空闲连接后 %d 个(每条连接 +%.1f);堆 +%.1f KiB/条;goroutine 栈 +%.1f KiB/条", g0, g1, float64(g1-g0)/1000, float64(h1-h0)/1000/1024, float64(s1-s0)/1000/1024)
		pl.close()
		time.Sleep(1 * time.Second)
		g2, _, _ := p.stat()
		P("关闭这 1000 条连接之后:%d 个 goroutine", g2)
		p.close()
	}
}
