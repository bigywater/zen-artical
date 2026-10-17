import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g61')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

const total = 20_000_000

type padded struct {
	v atomic.Int64
	_ [120]byte
}

type packed struct{ v atomic.Int64 }

func timeit(g int, body func(id, n int)) float64 {
	var wg sync.WaitGroup
	n := total / g
	start := make(chan struct{})
	for i := 0; i < g; i++ {
		wg.Add(1)
		go func(id int) { defer wg.Done(); <-start; body(id, n) }(i)
	}
	t0 := time.Now()
	close(start)
	wg.Wait()
	return float64(time.Since(t0).Nanoseconds()) / float64(total)
}

func med3(f func() float64) float64 {
	xs := []float64{f(), f(), f()}
	sort.Float64s(xs)
	return xs[1]
}

var plainCounter int64
var sink int64

func main() {
	runtime.GOMAXPROCS(8)
	kind := os.Args[1]
	g, _ := strconv.Atoi(os.Args[2])
	var ai atomic.Int64
	var mu sync.Mutex
	var mc int64
	var pk [8]packed
	var pd [8]padded
	var f func() float64
	switch kind {
	case "plain":
		f = func() float64 { return timeit(g, func(id, n int) { var x int64; for i := 0; i < n; i++ { x++ }; atomic.AddInt64(&sink, x) }) }
	case "atomic":
		f = func() float64 { return timeit(g, func(id, n int) { for i := 0; i < n; i++ { ai.Add(1) } }) }
	case "cas":
		f = func() float64 { return timeit(g, func(id, n int) { for i := 0; i < n; i++ { for { o := ai.Load(); if ai.CompareAndSwap(o, o+1) { break } } } }) }
	case "mutex":
		f = func() float64 { return timeit(g, func(id, n int) { for i := 0; i < n; i++ { mu.Lock(); mc++; mu.Unlock() } }) }
	case "atomic-packed":
		f = func() float64 { return timeit(g, func(id, n int) { for i := 0; i < n; i++ { pk[id].v.Add(1) } }) }
	case "atomic-padded":
		f = func() float64 { return timeit(g, func(id, n int) { for i := 0; i < n; i++ { pd[id].v.Add(1) } }) }
	}
	fmt.Printf("%.1f\n", med3(f))
}
'''
d = gdir('at1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(kind, g):
    p = subprocess.run([str(d / 'app'), kind, str(g)], capture_output=True, text=True, timeout=300)
    return float(p.stdout.strip())
print('== 一:同一个计数器,不同写法的每次操作耗时(总共 2000 万次分到 G 个 goroutine 上,墙钟时间 ÷ 2000 万;每格取 3 次中位数;Go 1.27.1,arm64 macOS,GOMAXPROCS=8)')
print('  单位 ns/次')
res = {}
for kind in ('atomic', 'cas', 'mutex'):
    row = []
    for g in (1, 2, 4, 8):
        v = run(kind, g); res[(kind, g)] = v; row.append(f'G={g}: {v:6.1f}')
    print(f'  {kind:7s} ' + '  '.join(row))
print('== 二:没有共享时的对照:每个 goroutine 用自己的局部变量累加后一次性 atomic.Add(只是看成本下限)')
row = []
for g in (1, 8):
    row.append(f'G={g}: {run("plain", g):6.1f}')
print('  局部变量 ' + '  '.join(row))
print('== 三:伪共享:每个 goroutine 有自己的 atomic 计数器,但相邻放在一起 vs 隔开 128 字节(8 个 goroutine,各自的计数器互不共享)')
for kind, lab in (('atomic-packed', '相邻放置(无填充)'), ('atomic-padded', '各占 128 字节')):
    row = []
    for g in (1, 8):
        row.append(f'G={g}: {run(kind, g):6.1f}')
    print(f'  {lab:14s} ' + '  '.join(row))
print('== 四:atomic.Int64.Add 在 arm64 上编译成什么指令(go build -gcflags=-S)')
S2 = r'''
package main

import "sync/atomic"

var v atomic.Int64

//go:noinline
func add() int64 { return v.Add(1) }

//go:noinline
func cas(o int64) bool { return v.CompareAndSwap(o, o+1) }

func main() { add(); cas(1) }
'''
r = grun('at2', {'main.go': S2}, gcflags='-S')
for fn in ('main.add', 'main.cas'):
    blk = [x for x in re.split(r'\n(?=main\.\S+ STEXT)', r['cout']) if x.startswith(fn + ' STEXT')][0]
    ins = []
    for l in blk.split('\n'):
        m = re.match(r'\s*0x[0-9a-f]+ \d+ \(([^)]*)\)\s+(.*)', l)
        if m and 'FUNCDATA' not in l and 'PCDATA' not in l: ins.append(re.sub(r'\s+', ' ', m.group(2)))
    print(f'  {fn}:' + ' ; '.join(ins[:8]))
print('== 五:sync/atomic 包文档的开头')
r2, o = go(gdir('doc1'), 'doc', 'sync/atomic')
for l in o.split('\n')[3:20]:
    if l.strip(): print('  ' + l.strip())
