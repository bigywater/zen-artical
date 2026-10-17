import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g44')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"sort"
	"strconv"
	"sync"
	"syscall"
	"time"
)

func rss() float64 {
	var ru syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &ru)
	return float64(ru.Maxrss) / (1 << 20)
}

func med(xs []float64) float64 { sort.Float64s(xs); return xs[len(xs)/2] }

func main() {
	mode := os.Args[1]
	switch mode {
	case "mem":
		n, _ := strconv.Atoi(os.Args[2])
		runtime.GC()
		var m0, m1 runtime.MemStats
		runtime.ReadMemStats(&m0)
		r0 := rss()
		var wg sync.WaitGroup
		ready := make(chan struct{}, 1024)
		release := make(chan struct{})
		t0 := time.Now()
		for i := 0; i < n; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); ready <- struct{}{}; <-release }()
			if i%1024 == 1023 { for j := 0; j < 1024; j++ { <-ready } }
		}
		for len(ready) > 0 { <-ready }
		el := time.Since(t0)
		time.Sleep(50 * time.Millisecond)
		runtime.ReadMemStats(&m1)
		fmt.Printf("  %d 个 goroutine(都阻塞在 channel 上):NumGoroutine = %d;创建 + 就绪 %.0f ms(每个 %.0f ns)\n", n, runtime.NumGoroutine(), float64(el.Milliseconds()), float64(el.Nanoseconds())/float64(n))
		fmt.Printf("    StackInuse +%.0f MiB;HeapInuse +%.0f MiB;MSpanInuse +%.0f MiB;Sys +%.0f MiB;进程最大 RSS 增加 %.0f MiB\n", float64(m1.StackInuse-m0.StackInuse)/(1<<20), float64(m1.HeapInuse-m0.HeapInuse)/(1<<20), float64(m1.MSpanInuse-m0.MSpanInuse)/(1<<20), float64(m1.Sys-m0.Sys)/(1<<20), rss()-r0)
		fmt.Printf("    折算每个 goroutine:栈 %.0f 字节 + 堆 %.0f 字节(g 结构体等)+ span 元数据 %.0f 字节;Sys 合计 %.0f 字节\n", float64(m1.StackInuse-m0.StackInuse)/float64(n), float64(m1.HeapInuse-m0.HeapInuse)/float64(n), float64(m1.MSpanInuse-m0.MSpanInuse)/float64(n), float64(m1.Sys-m0.Sys)/float64(n))
		close(release)
		wg.Wait()
	case "create":
		const N = 500_000
		var xs, ys []float64
		for rep := 0; rep < 5; rep++ {
			var wg sync.WaitGroup
			t0 := time.Now()
			for i := 0; i < N; i++ {
				wg.Add(1)
				go func() { wg.Done() }()
			}
			wg.Wait()
			xs = append(xs, float64(time.Since(t0).Nanoseconds())/N)
			t0 = time.Now()
			ch := make(chan int)
			go func() { for i := 0; i < N; i++ { ch <- i }; close(ch) }()
			s := 0
			for v := range ch { s += v }
			ys = append(ys, float64(time.Since(t0).Nanoseconds())/N)
			_ = s
		}
		fmt.Printf("  go func(){ wg.Done() }() 创建并跑完:中位 %.0f ns/个(5 轮:%.0f / %.0f / %.0f / %.0f / %.0f);对照:无缓冲 channel 一次发送加接收 %.0f ns\n", med(append([]float64{}, xs...)), xs[0], xs[1], xs[2], xs[3], xs[4], med(ys))
	case "pingpong":
		const N = 500_000
		for _, procs := range []int{1, 2, 10} {
			runtime.GOMAXPROCS(procs)
			var xs []float64
			for rep := 0; rep < 5; rep++ {
				a, b := make(chan int), make(chan int)
				go func() { for v := range a { b <- v }; close(b) }()
				t0 := time.Now()
				for i := 0; i < N; i++ { a <- i; <-b }
				xs = append(xs, float64(time.Since(t0).Nanoseconds())/N)
				close(a)
			}
			fmt.Printf("  GOMAXPROCS=%2d:两个 goroutine 经无缓冲 channel 来回一次(两次切换):中位 %.0f ns\n", procs, med(xs))
		}
	case "threads":
		n, _ := strconv.Atoi(os.Args[2])
		r0 := rss()
		var wg sync.WaitGroup
		started := make(chan struct{}, 256)
		release := make(chan struct{})
		t0 := time.Now()
		for i := 0; i < n; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				runtime.LockOSThread()
				started <- struct{}{}
				<-release
			}()
		}
		for i := 0; i < n; i++ { <-started }
		el := time.Since(t0)
		fmt.Printf("  %d 个 LockOSThread 的 goroutine(各占一个 OS 线程):创建 %.0f ms(每个 %.0f µs);进程最大 RSS 增加 %.0f MiB(每个线程约 %.0f KiB)\n", n, float64(el.Milliseconds()), float64(el.Microseconds())/float64(n), rss()-r0, (rss()-r0)*1024/float64(n))
		close(release)
		wg.Wait()
	case "maxthreads":
		old := debug.SetMaxThreads(500)
		fmt.Println("  SetMaxThreads(500) 返回旧值:", old)
		var wg sync.WaitGroup
		release := make(chan struct{})
		for i := 0; i < 1000; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); runtime.LockOSThread(); <-release }()
		}
		time.Sleep(3 * time.Second)
		fmt.Println("  不应该走到这里")
	}
}
'''
d = gdir('gc1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a, tmo=300):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=tmo)
    return p
print('== 一:一个 goroutine 占多少内存(Go 1.27.1,arm64)')
for n in (10_000, 100_000, 500_000):
    print(run('mem', n).stdout.rstrip())
print('== 二:创建一个 goroutine 要多久')
print(run('create').stdout.rstrip())
print('== 三:goroutine 之间切换的成本(两个 goroutine 经无缓冲 channel 来回)')
print(run('pingpong').stdout.rstrip())
print('== 四:对照 OS 线程:每个 goroutine 调用 runtime.LockOSThread 并阻塞,就会占住一个线程')
for n in (1000, 2000, 4000):
    p = run('threads', n)
    out = p.stdout.rstrip()
    if out: print(out)
    else:
        ls = [re.sub(r'0x[0-9a-f]+', '0x…', l.strip()) for l in p.stderr.split('\n') if 'failed to create' in l or 'errno' in l or 'fatal' in l]
        print(f'  {n} 个 LockOSThread 的 goroutine:失败,退出码 {p.returncode};' + ' / '.join(ls[:3]))
print('  本机对单个进程线程数的限制:' + subprocess.run(['sysctl', '-n', 'kern.num_taskthreads'], capture_output=True, text=True).stdout.strip() + '(kern.num_taskthreads)')
print('== 五:Go 自己的线程数上限:debug.SetMaxThreads(500) 之后要 1000 个线程')
p = run('maxthreads', tmo=120)
lines = [re.sub(r'0x[0-9a-f]+', '0x…', l.strip()) for l in (p.stdout + p.stderr).split('\n') if l.strip() and not l.startswith(('\t', 'goroutine', 'main.', 'runtime.', 'created'))]
print(f'  退出码 {p.returncode};' + ' / '.join(lines[:4])[:320])
