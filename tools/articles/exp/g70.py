import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g70')
SRC = r'''
package main

import (
	"context"
	"fmt"
	"os"
	"runtime"
	"sort"
	"sync"
	"time"
)

func gen(ctx context.Context, n int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for i := 0; i < n; i++ {
			select {
			case out <- i:
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

func gen2(n int) <-chan int { // 没有取消机制的版本
	out := make(chan int)
	go func() { defer close(out); for i := 0; i < n; i++ { out <- i } }()
	return out
}

//go:noinline
func heavy(x int) int { s := x; for i := 0; i < 20000; i++ { s = s*1664525 + 1013904223 }; return s }

func stage(ctx context.Context, in <-chan int, f func(int) int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for v := range in {
			select {
			case out <- f(v):
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

func fanOut(ctx context.Context, in <-chan int, n int, f func(int) int) []<-chan int {
	var outs []<-chan int
	for i := 0; i < n; i++ { outs = append(outs, stage(ctx, in, f)) }
	return outs
}

func merge(ctx context.Context, cs ...<-chan int) <-chan int {
	out := make(chan int)
	var wg sync.WaitGroup
	for _, c := range cs {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for v := range c {
				select {
				case out <- v:
				case <-ctx.Done():
					return
				}
			}
		}()
	}
	go func() { wg.Wait(); close(out) }()
	return out
}

func main() {
	runtime.GOMAXPROCS(8)
	switch os.Args[1] {
	case "leak":
		base := runtime.NumGoroutine()
		// 没有取消机制:消费者只读 3 个就走
		for i := 0; i < 100; i++ {
			c := gen2(1000)
			<-c; <-c; <-c
		}
		time.Sleep(50 * time.Millisecond)
		fmt.Printf("  没有取消机制:100 条流水线各只读 3 个元素就丢弃 → goroutine 数 %d → %d\n", base, runtime.NumGoroutine())
		base = runtime.NumGoroutine()
		for i := 0; i < 100; i++ {
			ctx, cancel := context.WithCancel(context.Background())
			c := stage(ctx, gen(ctx, 1000), func(x int) int { return x * x })
			<-c; <-c; <-c
			cancel()
		}
		time.Sleep(50 * time.Millisecond)
		fmt.Printf("  读 3 个后 cancel():同样 100 条两级流水线 → goroutine 数 %d → %d(起点 101 里包含上一组已经泄漏的 100 个,这一组没有新增)\n", base, runtime.NumGoroutine())
	case "order":
		ctx := context.Background()
		in := gen(ctx, 2000)
		outs := fanOut(ctx, in, 4, func(x int) int { time.Sleep(time.Duration(x%3) * 100 * time.Microsecond); return x })
		var got []int
		for v := range merge(ctx, outs...) { got = append(got, v) }
		inversions := 0
		for i := 1; i < len(got); i++ { if got[i] < got[i-1] { inversions++ } }
		sorted := append([]int(nil), got...)
		sort.Ints(sorted)
		ok := true
		for i, v := range sorted { if v != i { ok = false } }
		fmt.Printf("  4 个 worker 并行处理 0..1999:收到 %d 个,元素齐全=%v,输出里“比前一个小”的位置有 %d 处(顺序被打乱)\n", len(got), ok, inversions)
	case "scale":
		for _, n := range []int{1, 2, 4, 8} {
			ctx := context.Background()
			t0 := time.Now()
			in := gen(ctx, 20000)
			outs := fanOut(ctx, in, n, heavy)
			sum := 0
			for v := range merge(ctx, outs...) { sum ^= v }
			fmt.Printf("  第二级 worker 数 = %d:处理 2 万个元素用时 %.0f ms\n", n, float64(time.Since(t0).Microseconds())/1000)
			_ = sum
		}
	case "buffer":
		for _, cap := range []int{0, 1, 16, 256} {
			const N = 1_000_000
			a := make(chan int, cap)
			b := make(chan int, cap)
			c := make(chan int, cap)
			t0 := time.Now()
			go func() { for i := 0; i < N; i++ { a <- i }; close(a) }()
			go func() { for v := range a { b <- v + 1 }; close(b) }()
			go func() { for v := range b { c <- v * 2 }; close(c) }()
			s := 0
			for v := range c { s += v }
			fmt.Printf("  三级流水线,每级 channel 容量 %3d:100 万个元素 %6.0f ms,%4.0f ns/个\n", cap, float64(time.Since(t0).Microseconds())/1000, float64(time.Since(t0).Nanoseconds())/N)
			_ = s
		}
	}
}
'''
d = gdir('pp1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:消费者提前走掉,没有取消机制的流水线会泄漏 goroutine(Go 1.27.1,arm64 macOS)')
print(run('leak'))
print('== 二:fan-out 并行处理,fan-in 合并之后顺序乱了')
print(run('order'))
print('== 三:瓶颈在第二级(每个元素约 20000 次乘加)时,增加 worker 能提速多少')
print(run('scale'))
print('== 四:流水线级间 channel 的容量对吞吐的影响(几乎不做事的三级流水线)')
print(run('buffer'))
