import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g57')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/pprof"
	"strconv"
	"sync"
	"testing"
	"time"
)

var mu sync.Mutex
var counter int

//go:noinline
func critical() {
	mu.Lock()
	counter++
	time.Sleep(time.Millisecond) // 在锁里“工作” 1 ms
	mu.Unlock()
}

func write(name, path string) {
	f, _ := os.Create(path)
	pprof.Lookup(name).WriteTo(f, 0)
	f.Close()
}

func main() {
	mode := os.Args[1]
	switch mode {
	case "contend":
		bf, _ := strconv.Atoi(os.Args[2])  // block rate
		mf, _ := strconv.Atoi(os.Args[3])  // mutex fraction
		runtime.SetBlockProfileRate(bf)
		runtime.SetMutexProfileFraction(mf)
		var wg sync.WaitGroup
		t0 := time.Now()
		for g := 0; g < 8; g++ {
			wg.Add(1)
			go func() { defer wg.Done(); for i := 0; i < 20; i++ { critical() } }()
		}
		wg.Wait()
		fmt.Printf("TOTAL %.3f\n", time.Since(t0).Seconds())
		write("block", os.Args[4]+".block")
		write("mutex", os.Args[4]+".mutex")
	case "chan":
		runtime.SetBlockProfileRate(1)
		runtime.SetMutexProfileFraction(1)
		ch := make(chan int)
		go func() { time.Sleep(300 * time.Millisecond); ch <- 1 }()
		<-ch
		write("block", os.Args[2]+".block")
		write("mutex", os.Args[2]+".mutex")
	case "cost":
		for _, r := range []int{0, 1} {
			runtime.SetBlockProfileRate(r)
			runtime.SetMutexProfileFraction(r)
			var m sync.Mutex
			res := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { m.Lock(); m.Unlock() } })
			fmt.Printf("  速率 %d(无竞争的 Lock+Unlock):%d ns/次\n", r, res.NsPerOp())
			var wg sync.WaitGroup
			var m2 sync.Mutex
			t0 := time.Now()
			const N = 200000
			for g := 0; g < 8; g++ {
				wg.Add(1)
				go func() { defer wg.Done(); for i := 0; i < N; i++ { m2.Lock(); m2.Unlock() } }()
			}
			wg.Wait()
			fmt.Printf("  速率 %d(8 个 goroutine 争同一把锁,各 %d 次):平均每次 %.0f ns\n", r, N, float64(time.Since(t0).Nanoseconds())/(8*N))
		}
	}
}
'''
d = gdir('bm1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr).rstrip()
def pp(path, n=6, unit='ms'):
    r = subprocess.run([GO, 'tool', 'pprof', '-top', f'-nodecount={n}', f'-unit={unit}', str(d / 'app'), str(d / path)], capture_output=True, text=True, env=genv())
    return [l for l in (r.stdout + r.stderr).split('\n') if l.strip() and not re.match(r'(Time|File|Build ID):', l)]
def delay_and_count(path):
    r = subprocess.run([GO, 'tool', 'pprof', '-raw', str(d / 'app'), str(d / path)], capture_output=True, text=True, env=genv())
    tot_c = tot_d = 0
    for l in r.stdout.split('\n'):
        m = re.match(r'\s*(\d+)\s+(\d+):', l)
        if m: tot_c += int(m.group(1)); tot_d += int(m.group(2))
    return tot_c, tot_d / 1e6
print('== 一:8 个 goroutine 争同一把 sync.Mutex,每次在锁里睡 1 ms,各 20 次(共 160 次、至少 160 ms 的串行时间)。SetBlockProfileRate(1) 与 SetMutexProfileFraction(1)(Go 1.27.1,arm64 macOS)')
o = run('contend', 1, 1, d / 'c1')
print('  ' + o)
print('  -- block profile(-top,delay):')
for l in pp('c1.block'): print('    ' + l)
print('  -- mutex profile(-top,delay):')
for l in pp('c1.mutex'): print('    ' + l)
print('== 二:block profile 也记录 channel 等待,mutex profile 不记录(main 在 <-ch 上等 300 ms)')
run('chan', d / 'c2')
c, ms = delay_and_count('c2.block'); print(f'  block profile:{c} 次事件,累计延迟 {ms:.0f} ms')
c, ms = delay_and_count('c2.mutex'); print(f'  mutex profile:{c} 次事件,累计延迟 {ms:.0f} ms')
print('== 三:采样设置对读数的影响(同一个竞争程序,各 5 次;第一栏是 block 的事件数与累计延迟,第二栏是 mutex 的)')
for bf, mf in ((1, 1), (1000000, 10), (100000000, 100)):
    rows = []
    for i in range(5):
        run('contend', bf, mf, d / 'c3')
        rows.append((delay_and_count('c3.block'), delay_and_count('c3.mutex')))
    bd = [r[0][1] for r in rows]; bc = [r[0][0] for r in rows]; md = [r[1][1] for r in rows]; mc = [r[1][0] for r in rows]
    print(f'  block rate={bf:>9d}, mutex fraction={mf:>3d}:block 延迟 {min(bd):6.0f}–{max(bd):6.0f} ms(事件 {min(bc)}–{max(bc)} 次);mutex 延迟 {min(md):6.0f}–{max(md):6.0f} ms(事件 {min(mc)}–{max(mc)} 次)')
print('== 四:打开 profile 的代价(速率 0 vs 1)')
print(run('cost'))
print('== 五:文档原文(go doc)')
for sym in ('runtime.SetBlockProfileRate', 'runtime.SetMutexProfileFraction'):
    r, o = go(gdir('doc1'), 'doc', sym)
    for l in o.split('\n')[3:12]:
        if l.strip(): print('  ' + l.strip())
