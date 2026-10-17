import sys, os, re, time, statistics, subprocess, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g69')
SRC = r'''
package main

import (
	"context"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"golang.org/x/time/rate"
)

func ms(d time.Duration) string { return fmt.Sprintf("%.0f", float64(d.Microseconds())/1000) }

func main() {
	switch os.Args[1] {
	case "allow":
		l := rate.NewLimiter(10, 5) // 每秒 10 个令牌,桶容量 5
		t0 := time.Now()
		var res []string
		for i := 0; i < 8; i++ { res = append(res, fmt.Sprint(l.Allow())) }
		fmt.Printf("  NewLimiter(10/s, burst 5),桶是满的,连续调用 Allow() 8 次:%v\n", res)
		time.Sleep(105 * time.Millisecond)
		fmt.Printf("  等 105 ms 后再 Allow():%v;紧接着再 Allow():%v\n", l.Allow(), l.Allow())
		time.Sleep(1200 * time.Millisecond)
		n := 0
		for l.Allow() { n++ }
		fmt.Printf("  再空闲 1.2 秒(攒了 12 个令牌,但桶只装 5 个)后,连续 Allow() 成功了 %d 次(总用时 %s ms)\n", n, ms(time.Since(t0)))
	case "wait":
		l := rate.NewLimiter(20, 1)
		ctx := context.Background()
		t0 := time.Now()
		var ts []float64
		for i := 0; i < 11; i++ { l.Wait(ctx); ts = append(ts, float64(time.Since(t0).Microseconds())/1000) }
		var gaps []float64
		for i := 1; i < len(ts); i++ { gaps = append(gaps, ts[i]-ts[i-1]) }
		fmt.Printf("  NewLimiter(20/s, burst 1),连续 Wait 11 次,每次放行的时刻(ms):")
		for _, x := range ts { fmt.Printf(" %.0f", x) }
		fmt.Println()
		mn, mx := gaps[0], gaps[0]
		for _, g := range gaps { if g < mn { mn = g }; if g > mx { mx = g } }
		fmt.Printf("  相邻两次放行的间隔:最小 %.1f ms / 最大 %.1f ms(理论 50 ms)\n", mn, mx)
	case "errors":
		l := rate.NewLimiter(10, 5)
		fmt.Printf("  WaitN(ctx, 6)(超过桶容量 5):%v\n", l.WaitN(context.Background(), 6))
		l2 := rate.NewLimiter(1, 1)
		l2.Allow() // 用掉桶里的令牌
		ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
		defer cancel()
		t0 := time.Now()
		err := l2.Wait(ctx) // 需要等约 1 秒,超过 200 ms 的期限
		fmt.Printf("  速率 1/s,桶已空,ctx 期限 200 ms,Wait 返回:%v(耗时 %s ms,没有真的等 1 秒)\n", err, ms(time.Since(t0)))
	case "reserve":
		l := rate.NewLimiter(10, 1)
		l.Allow()
		r := l.Reserve()
		fmt.Printf("  桶空时 Reserve():OK=%v,Delay=%s ms\n", r.OK(), ms(r.Delay()))
		r.Cancel()
		r2 := l.Reserve()
		fmt.Printf("  Cancel 之后再 Reserve():Delay=%s ms(取消把令牌还回去了)\n", ms(r2.Delay()))
		l3 := rate.NewLimiter(10, 1)
		l3.Allow()
		r3 := l3.Reserve(); r4 := l3.Reserve(); r5 := l3.Reserve()
		fmt.Printf("  不 Cancel,连续 Reserve 3 次:Delay = %s / %s / %s ms(预约一个比一个往后排)\n", ms(r3.Delay()), ms(r4.Delay()), ms(r5.Delay()))
	case "throughput":
		for _, g := range []int{1, 8, 64} {
			l := rate.NewLimiter(1000, 10)
			ctx := context.Background()
			var wg sync.WaitGroup
			var mu sync.Mutex
			n := 0
			t0 := time.Now()
			end := t0.Add(3 * time.Second)
			for i := 0; i < g; i++ {
				wg.Add(1)
				go func() { defer wg.Done(); for time.Now().Before(end) { if l.Wait(ctx) == nil { mu.Lock(); n++; mu.Unlock() } } }()
			}
			wg.Wait()
			fmt.Printf("  限速 1000/s,%d 个 goroutine 共用一个限流器各自循环 Wait,3 秒内通过 %d 次(%.0f 次/秒)\n", g, n, float64(n)/time.Since(t0).Seconds())
		}
	case "cost":
		l := rate.NewLimiter(rate.Inf, 1)
		r1 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { l.Allow() } })
		l2 := rate.NewLimiter(1000, 1000)
		r2 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { l2.Allow() } })
		r3 := testing.Benchmark(func(b *testing.B) { b.RunParallel(func(pb *testing.PB) { for pb.Next() { l2.Allow() } }) })
		fmt.Printf("  Allow():rate.Inf %d ns/次;有限速率(单线程)%d ns/次;有限速率(%d 个 P 并行)%d ns/次\n", r1.NsPerOp(), r2.NsPerOp(), 10, r3.NsPerOp())
	}
}
'''
d = gdir('rl1'); write(d, {'main.go': SRC}); mod(d)
rc, o = goget(d, 'golang.org/x/time@latest'); print('goget:', rc, o[-120:]); assert rc == 0
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 零:依赖版本')
print('  ' + re.search(r'golang.org/x/time v\S+', open(d / 'go.mod').read()).group(0))
print('== 一:Allow:桶满时能连续放行几个,空闲后桶能攒多少')
print(run('allow'))
print('== 二:Wait:把请求均匀地摊开')
print(run('wait'))
print('== 三:两种 Wait 的错误')
print(run('errors'))
print('== 四:Reserve 与 Cancel')
print(run('reserve'))
print('== 五:多个 goroutine 共用一个限流器,总吞吐是多少')
print(run('throughput'))
print('== 六:调用本身多贵')
print(run('cost'))
print('== 七:源码里的说明(rate.go)')
src = glob.glob(str(GT / '_gopath' / 'pkg' / 'mod' / 'golang.org' / 'x' / 'time@*' / 'rate' / 'rate.go'))[0]
t = open(src).read()
m = re.search(r'// A Limiter controls how frequently events are allowed to happen\..*?\ntype Limiter struct', t, re.S)
print('  ' + '\n  '.join(l.strip() for l in m.group(0).split('\n') if l.strip() and not l.startswith('type')))
