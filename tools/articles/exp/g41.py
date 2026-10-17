import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g41')
SRC = r'''
package main

import (
	"flag"
	"fmt"
	"runtime"
	"runtime/metrics"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

type Node struct {
	next *Node
	pad  [5]int
}

var live []*Node

func hist(name string) (maxS, p99 float64, total uint64) {
	s := []metrics.Sample{{Name: name}}
	metrics.Read(s)
	h := s[0].Value.Float64Histogram()
	for _, c := range h.Counts { total += c }
	if total == 0 { return }
	var cum uint64
	got99 := false
	for i, c := range h.Counts {
		cum += c
		if c > 0 {
			hi := h.Buckets[i+1]
			if hi > 1e9 { hi = h.Buckets[i] }
			maxS = hi
		}
		if !got99 && float64(cum) >= 0.99*float64(total) {
			p99 = h.Buckets[i+1]; if p99 > 1e9 { p99 = h.Buckets[i] }; got99 = true
		}
	}
	return
}

func main() {
	liveMB := flag.Int("live", 50, "存活堆 MB")
	gor := flag.Int("g", 0, "额外的空闲 goroutine 数")
	dur := flag.Duration("dur", 2*time.Second, "运行时间")
	procs := flag.Int("p", 0, "GOMAXPROCS(0 表示不改)")
	allocs := flag.Int("alloc", 2, "分配 goroutine 数")
	gcloop := flag.Bool("gcloop", false, "另起一个 goroutine 不停调用 runtime.GC()")
	flag.Parse()
	if *procs > 0 { runtime.GOMAXPROCS(*procs) }
	n := *liveMB * (1 << 20) / 56
	live = make([]*Node, n)
	for i := range live { live[i] = &Node{} }
	for i := range live { live[i].next = live[(i*7919)%n] }
	var wg sync.WaitGroup
	block := make(chan struct{})
	for i := 0; i < *gor; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); <-block }()
	}
	runtime.GC()
	var ops atomic.Int64
	stop := make(chan struct{})
	if *gcloop {
		go func() {
			for {
				select {
				case <-stop:
					return
				default:
				}
				runtime.GC()
			}
		}()
	}
	for w := 0; w < *allocs; w++ {
		go func() {
			var sink *Node
			for {
				select {
				case <-stop:
					return
				default:
				}
				for i := 0; i < 1000; i++ { sink = &Node{}; sink.pad[0] = i }
				ops.Add(1000)
			}
			_ = sink
		}()
	}
	// 另一个 goroutine 每 1 ms 睡一次,记录实际多睡了多久(从应用角度看到的延迟)
	var jit []float64
	var m0 runtime.MemStats
	runtime.ReadMemStats(&m0)
	t0 := time.Now()
	for time.Since(t0) < *dur {
		s := time.Now()
		time.Sleep(time.Millisecond)
		jit = append(jit, float64(time.Since(s)-time.Millisecond)/1e6)
	}
	close(stop)
	var m1 runtime.MemStats
	runtime.ReadMemStats(&m1)
	sort.Float64s(jit)
	q := func(p float64) float64 { return jit[int(p*float64(len(jit)-1))] }
	pmax, p99, pn := hist("/sched/pauses/total/gc:seconds")
	smax, _, _ := hist("/sched/pauses/stopping/gc:seconds")
	fmt.Printf("live=%dMB g=%d P=%d GC=%d 次 | 总停顿(stop+run)直方图:最大≈%.0fµs p99≤%.0fµs(%d 次) 停止阶段最大≈%.0fµs | 1ms 睡眠的多余延迟:p50=%.2fms p99=%.2fms p99.9=%.2fms max=%.2fms(%d 次采样) | 累计 PauseTotal=%.2fms\n",
		*liveMB, *gor, runtime.GOMAXPROCS(0), m1.NumGC-m0.NumGC, pmax*1e6, p99*1e6, pn, smax*1e6, q(.5), q(.99), q(.999), jit[len(jit)-1], len(jit), float64(m1.PauseTotalNs-m0.PauseTotalNs)/1e6)
	runtime.KeepAlive(live)
	close(block)
	wg.Wait()
}
'''
d = gdir('gp1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(args):
    p = subprocess.run([str(d / 'app'), *map(str, args)], capture_output=True, text=True, timeout=120)
    return (p.stdout.strip() or p.stderr.strip())
print('== 一:不同堆大小下的 GC 停顿(2 个 goroutine 持续分配垃圾,各跑 2 秒;Go 1.27.1,arm64,10 个 P)')
for live in (10, 100, 500, 1000):
    print('  ' + run(['-live', live]))
print('== 二:goroutine 数量的影响(存活堆 50 MB,额外 N 个阻塞的 goroutine)')
for g in (0, 10_000, 100_000, 500_000):
    print('  ' + run(['-live', 50, '-g', g]))
print('== 三:GOMAXPROCS 的影响(存活堆 100 MB)')
for pp in (1, 2, 4, 10):
    print('  ' + run(['-live', 100, '-p', pp]))
print('== 四:停顿很短,但应用看到的延迟为什么还是几十毫秒?对照实验(存活堆 500 MB):没有 GC / 只有后台连续 GC / 2 个分配 goroutine 引发的 GC')
print('  不分配、不 GC(基线):  ' + run(['-live', 500, '-alloc', 0]))
print('  只有一个 goroutine 不停 runtime.GC():  ' + run(['-live', 500, '-alloc', 0, '-gcloop']))
print('  2 个分配 goroutine(同第一节):  ' + run(['-live', 500]))
print('  10 个分配 goroutine(超过 P 的数量,抢满 CPU):  ' + run(['-live', 500, '-alloc', 10]))
