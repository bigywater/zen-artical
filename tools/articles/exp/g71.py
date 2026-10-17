import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g71')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/sync/errgroup"
)

type result struct {
	wall    time.Duration
	peakG   int64
	maxConc int64
	alloc   uint64
	sys     uint64
}

func measure(run func(job func())) result {
	runtime.GC()
	var m0, m1 runtime.MemStats
	runtime.ReadMemStats(&m0)
	var peak, cur, maxc atomic.Int64
	stop := make(chan struct{})
	done := make(chan struct{})
	go func() {
		defer close(done)
		for {
			select {
			case <-stop: return
			default:
				if g := int64(runtime.NumGoroutine()); g > peak.Load() { peak.Store(g) }
				time.Sleep(200 * time.Microsecond)
			}
		}
	}()
	jobKind := os.Args[2]
	work := func() {
		n := cur.Add(1)
		for { m := maxc.Load(); if n <= m || maxc.CompareAndSwap(m, n) { break } }
		if jobKind == "sleep" { time.Sleep(5 * time.Millisecond) } else { x := 0; for i := 0; i < 50; i++ { x += i }; sink.Add(int64(x)) }
		cur.Add(-1)
	}
	t0 := time.Now()
	run(work)
	w := time.Since(t0)
	close(stop); <-done
	runtime.ReadMemStats(&m1)
	return result{w, peak.Load(), maxc.Load(), m1.TotalAlloc - m0.TotalAlloc, m1.Sys}
}

var sink atomic.Int64

func main() {
	runtime.GOMAXPROCS(8)
	pattern := os.Args[1]
	total, _ := strconv.Atoi(os.Args[3])
	limit, _ := strconv.Atoi(os.Args[4])
	r := measure(func(job func()) {
		var wg sync.WaitGroup
		switch pattern {
		case "workers":
			ch := make(chan struct{}, 0)
			for i := 0; i < limit; i++ { wg.Add(1); go func() { defer wg.Done(); for range ch { job() } }() }
			for i := 0; i < total; i++ { ch <- struct{}{} }
			close(ch)
		case "sem-before":
			sem := make(chan struct{}, limit)
			for i := 0; i < total; i++ { sem <- struct{}{}; wg.Add(1); go func() { defer wg.Done(); job(); <-sem }() }
		case "sem-inside":
			sem := make(chan struct{}, limit)
			for i := 0; i < total; i++ { wg.Add(1); go func() { defer wg.Done(); sem <- struct{}{}; job(); <-sem }() }
		case "errgroup":
			var g errgroup.Group
			g.SetLimit(limit)
			for i := 0; i < total; i++ { g.Go(func() error { job(); return nil }) }
			g.Wait()
		case "unbounded":
			for i := 0; i < total; i++ { wg.Add(1); go func() { defer wg.Done(); job() }() }
		}
		wg.Wait()
	})
	fmt.Printf("%d %d %d %d %d\n", r.wall.Milliseconds(), r.peakG, r.maxConc, r.alloc/1024, r.sys/1024/1024)
}
'''
d = gdir('wp1'); write(d, {'main.go': SRC}); mod(d)
rc, o = goget(d, 'golang.org/x/sync@v0.24.0'); assert rc == 0, o
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(pattern, kind, total, limit):
    rows = []
    for i in range(3):
        p = subprocess.run([str(d / 'app'), pattern, kind, str(total), str(limit)], capture_output=True, text=True, timeout=300)
        rows.append([int(x) for x in p.stdout.split()])
    rows.sort(key=lambda r: r[0])
    return rows[1]
names = [('workers', '固定 N 个 worker 读任务 channel'), ('sem-before', '信号量:先占位再起 goroutine'), ('sem-inside', '信号量:先起 goroutine 再在里面占位'), ('errgroup', 'errgroup.SetLimit(N)'), ('unbounded', '不限制,每个任务一个 goroutine')]
for sec, kind, total, limit, title in (('一', 'sleep', 2000, 50, '2000 个各睡 5 ms 的任务,并发上限 50'), ('二', 'cpu', 1_000_000, 8, '100 万个几乎不做事的任务(50 次加法),并发上限 8')):
    print(f'== {sec}:{title}(Go 1.27.1,arm64 macOS,GOMAXPROCS=8;每种 3 次取用时中位数的那一次)')
    print('  列:用时 ms / 峰值 goroutine 数 / 同时在做事的最大个数 / 累计分配 KiB / 进程向系统申请的内存 MiB')
    for pat, label in names:
        r = run(pat, kind, total, limit)
        print(f'  {label:24s} {r[0]:6d} ms / {r[1]:7d} / {r[2]:6d} / {r[3]:9d} KiB / {r[4]:4d} MiB')
