import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g62')
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
	"testing"
	"time"
	"unsafe"
)

type Config struct {
	A    int
	_    [6]int
	B    int
	Name string
}

const total = 40_000_000

func timeit(g int, body func(n int)) float64 {
	var wg sync.WaitGroup
	n := total / g
	start := make(chan struct{})
	for i := 0; i < g; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); <-start; body(n) }()
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

var sink int

func catch(label string, f func()) {
	defer func() { fmt.Printf("  %s:%v\n", label, recover()) }()
	f()
}

func main() {
	runtime.GOMAXPROCS(8)
	switch os.Args[1] {
	case "read":
		g, _ := strconv.Atoi(os.Args[2])
		var p atomic.Pointer[Config]
		p.Store(&Config{A: 1, B: 1})
		var v atomic.Value
		v.Store(&Config{A: 1, B: 1})
		var mu sync.Mutex
		var rw sync.RWMutex
		cfg := &Config{A: 1, B: 1}
		res := map[string]float64{}
		res["atomic.Pointer.Load"] = med3(func() float64 { return timeit(g, func(n int) { s := 0; for i := 0; i < n; i++ { s += p.Load().A }; sink += s }) })
		res["atomic.Value.Load"] = med3(func() float64 { return timeit(g, func(n int) { s := 0; for i := 0; i < n; i++ { s += v.Load().(*Config).A }; sink += s }) })
		res["RWMutex.RLock"] = med3(func() float64 { return timeit(g, func(n int) { s := 0; for i := 0; i < n; i++ { rw.RLock(); s += cfg.A; rw.RUnlock() }; sink += s }) })
		res["Mutex.Lock"] = med3(func() float64 { return timeit(g, func(n int) { s := 0; for i := 0; i < n; i++ { mu.Lock(); s += cfg.A; mu.Unlock() }; sink += s }) })
		for _, k := range []string{"atomic.Pointer.Load", "atomic.Value.Load", "RWMutex.RLock", "Mutex.Lock"} {
			fmt.Printf("  G=%d %-20s %7.1f ns/次\n", g, k, res[k])
		}
	case "inplace", "cow":
		// 不变量:A == B。写者每约 5µs 更新一次配置(共 2 万次);读者不停地读,读到 A != B 就算违反
		const readers = 6
		var stop atomic.Bool
		var viol, reads atomic.Int64
		var wg sync.WaitGroup
		shared := &Config{}
		var p atomic.Pointer[Config]
		p.Store(&Config{})
		for r := 0; r < readers; r++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				var v, n int64
				for !stop.Load() {
					var c Config
					if os.Args[1] == "inplace" { c = *shared } else { c = *p.Load() }
					n++
					if c.A != c.B { v++ }
				}
				viol.Add(v); reads.Add(n)
			}()
		}
		for i := 1; i <= 20000; i++ {
			if os.Args[1] == "inplace" { *shared = Config{A: i, B: i} } else { p.Store(&Config{A: i, B: i}) }
			for t0 := time.Now(); time.Since(t0) < 5*time.Microsecond; {}
		}
		stop.Store(true); wg.Wait()
		fmt.Printf("  读 %d 次,读到 A != B 的有 %d 次\n", reads.Load(), viol.Load())
	case "panics":
		var v atomic.Value
		catch("v.Store(nil)", func() { v.Store(nil) })
		v.Store(1)
		catch("先 Store(int),再 Store(string)", func() { v.Store("x") })
		var w atomic.Value
		w.Store(&Config{})
		catch("Store(*Config) 后 Store(Config)", func() { w.Store(Config{}) })
		fmt.Printf("  零值 Value.Load() = %v\n", (&atomic.Value{}).Load())
	case "alloc":
		var v atomic.Value
		var p atomic.Pointer[Config]
		c := &Config{A: 1}
		cv := Config{A: 1}
		fmt.Printf("  atomic.Value.Store(*Config):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { v.Store(c) }))
		var v2 atomic.Value
		fmt.Printf("  atomic.Value.Store(Config 值,%d 字节):每次 %.0f 次分配\n", unsafe.Sizeof(cv), testing.AllocsPerRun(1000, func() { v2.Store(cv) }))
		fmt.Printf("  atomic.Pointer.Store(*Config):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { p.Store(c) }))
		fmt.Printf("  atomic.Value.Load():每次 %.0f 次分配;atomic.Pointer.Load():每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { _ = v.Load() }), testing.AllocsPerRun(1000, func() { _ = p.Load() }))
	}
}
'''
d = gdir('av1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=300)
    return (p.stdout + p.stderr).rstrip()
print('== 一:读多写少的配置,四种读法的耗时(4000 万次读,分给 G 个 goroutine;每格 3 次中位数;Go 1.27.1,arm64 macOS,GOMAXPROCS=8)')
for g in (1, 8): print(run('read', g))
rc, o = go(d, 'build', '-race', '-o', 'app_race'); assert rc == 0, o
print('== 二:为什么要“复制一份、改好、再替换”:配置有 A == B 的不变量;6 个读者不停地读,写者更新 2 万次')
for m, lab in (('inplace', '原地整体覆盖同一个 Config'), ('cow', '新建 Config 再 atomic.Pointer.Store')):
    print(f'  [{lab}] 普通编译:' + run(m).strip())
    p = subprocess.run([str(d / 'app_race'), m], capture_output=True, text=True, timeout=300)
    t = p.stdout + p.stderr
    print(f'  [{lab}] -race 编译:退出码 {p.returncode},WARNING: DATA RACE {t.count("WARNING: DATA RACE")} 次')
print('== 三:atomic.Value 的限制(运行时 panic 的原文)')
print(run('panics'))
print('== 四:分配')
print(run('alloc'))
print('== 五:go vet 能不能发现“复制了原子值”')
V = r'''
package main

import "sync/atomic"

type S struct {
	v atomic.Value
	p atomic.Pointer[int]
}

func main() {
	var a S
	b := a
	_ = b
}
'''
dd = gdir('av2'); write(dd, {'main.go': V}); mod(dd)
rc, o = go(dd, 'vet', './...')
print('  go vet 输出:')
for l in o.split('\n'): print('    ' + l)
