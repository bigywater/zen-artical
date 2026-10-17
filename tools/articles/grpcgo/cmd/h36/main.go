package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
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

func child() {
	addr, _ := Start(&DemoServer{
		OnUnary: func(ctx context.Context, r *pb.Req) (*pb.Resp, error) { return &pb.Resp{Payload: r.Payload}, nil },
		OnBidi: func(st pb.Demo_BidiServer) error {
			for {
				m, err := st.Recv()
				if err != nil {
					return nil
				}
				st.Send(&pb.Resp{Payload: m.Payload})
			}
		},
	}, grpc.MaxRecvMsgSize(64<<20))
	fmt.Println(addr)
	io.Copy(io.Discard, os.Stdin)
}

type result struct {
	qps      float64
	p50, p99 time.Duration
	errs     int64
}

// run 用 workers 个 goroutine,在 conns 条连接上(轮流分配),连续发 payload 大小的 Unary,持续 dur。
func run(addr string, conns, workers, payload int, dur time.Duration) result {
	var cs []*grpc.ClientConn
	for i := 0; i < conns; i++ {
		c, _ := grpc.NewClient(addr, insec)
		cs = append(cs, c)
		pb.NewDemoClient(c).Unary(context.Background(), &pb.Req{})
	}
	defer func() {
		for _, c := range cs {
			c.Close()
		}
	}()
	req := &pb.Req{Payload: make([]byte, payload)}
	var stop atomic.Bool
	var wg sync.WaitGroup
	var mu sync.Mutex
	var all []time.Duration
	var errs atomic.Int64
	t0 := time.Now()
	for w := 0; w < workers; w++ {
		wg.Add(1)
		cl := pb.NewDemoClient(cs[w%conns])
		go func() {
			defer wg.Done()
			var mine []time.Duration
			for !stop.Load() {
				s := time.Now()
				if _, err := cl.Unary(context.Background(), req); err != nil {
					errs.Add(1)
				}
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
	sort.Slice(all, func(i, j int) bool { return all[i] < all[j] })
	return result{float64(len(all)) / el.Seconds(), all[len(all)/2], all[len(all)*99/100], errs.Load()}
}

func us(d time.Duration) string { return fmt.Sprintf("%d µs", d.Microseconds()) }

func main() {
	if len(os.Args) > 1 && os.Args[1] == "child" {
		child()
		return
	}
	cmd := exec.Command(os.Args[0], "child")
	in, _ := cmd.StdinPipe()
	o, _ := cmd.StdoutPipe()
	cmd.Start()
	a, _ := bufio.NewReader(o).ReadString('\n')
	addr := strings.TrimSpace(a)
	defer func() { in.Close(); cmd.Wait() }()
	dur := 2 * time.Second

	Sec(fmt.Sprintf("一:连接数对吞吐的影响:小消息(空 payload)的 Unary,64 个并发调用者,服务端是另一个进程;本机 %d 个逻辑 CPU", runtime.NumCPU()))
	{
		for _, k := range []int{1, 2, 4, 8, 16} {
			r := run(addr, k, 64, 0, dur)
			P("%2d 条连接:%8.0f 请求/秒;p50 %s、p99 %s;错误 %d", k, r.qps, us(r.p50), us(r.p99), r.errs)
		}
	}

	Sec("二:大一点的消息(64 KiB payload,请求和响应各一份)的连接数曲线,64 个并发调用者")
	{
		for _, k := range []int{1, 2, 4, 8, 16} {
			r := run(addr, k, 64, 64<<10, dur)
			P("%2d 条连接:%8.0f 请求/秒(%.0f MiB/秒 请求方向);p50 %s、p99 %s;错误 %d", k, r.qps, r.qps*64/1024, us(r.p50), us(r.p99), r.errs)
		}
	}

	Sec("三:一条连接上并发调用者数的曲线(小消息):1、4、16、64、256 个并发调用者的吞吐与延迟")
	{
		for _, w := range []int{1, 4, 16, 64, 256} {
			r := run(addr, 1, w, 0, dur)
			P("%3d 个并发调用者:%8.0f 请求/秒;p50 %s、p99 %s;错误 %d", w, r.qps, us(r.p50), us(r.p99), r.errs)
		}
	}

	Sec("四:一个调用者(无并发)的往返:Unary vs 同一个 Bidi 流上来回 echo(小消息)")
	{
		r := run(addr, 1, 1, 0, dur)
		P("Unary:%8.0f 次/秒;p50 %s、p99 %s", r.qps, us(r.p50), us(r.p99))
		c, _ := grpc.NewClient(addr, insec)
		cl := pb.NewDemoClient(c)
		st, _ := cl.Bidi(context.Background())
		var all []time.Duration
		t0 := time.Now()
		for time.Since(t0) < dur {
			s := time.Now()
			st.Send(&pb.Req{})
			st.Recv()
			all = append(all, time.Since(s))
		}
		el := time.Since(t0)
		sort.Slice(all, func(i, j int) bool { return all[i] < all[j] })
		P("Bidi 流:%8.0f 次/秒;p50 %s、p99 %s", float64(len(all))/el.Seconds(), us(all[len(all)/2]), us(all[len(all)*99/100]))
		c.Close()
	}
}
