import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g52')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"testing"
	"time"
)

func heap() float64 {
	runtime.GC(); runtime.GC()
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return float64(m.HeapAlloc) / 1e6
}

func main() {
	h0 := heap()
	const N = 100000
	switch os.Args[1] {
	case "ticker":
		for i := 0; i < N; i++ { time.NewTicker(time.Hour) } // 不保存、不 Stop
		fmt.Printf("  %d 个 NewTicker(1h) 丢掉不 Stop:GC 之后堆 %.1f MB → %.1f MB(增加 %.1f MB)\n", N, h0, heap(), heap()-h0)
	case "tick":
		for i := 0; i < N; i++ { _ = time.Tick(time.Hour) }
		fmt.Printf("  %d 个 time.Tick(1h) 丢掉:GC 之后堆 %.1f MB → %.1f MB(增加 %.1f MB)\n", N, h0, heap(), heap()-h0)
	case "after":
		ch := make(chan int)
		for i := 0; i < N; i++ {
			select {
			case <-ch:
			case <-time.After(time.Hour): // 经典写法:循环里每次一个 time.After,条件很快满足时 after 不会触发
				_ = i
			default:
			}
		}
		fmt.Printf("  循环 %d 次,每次 select 里放一个 time.After(1h):GC 之后堆 %.1f MB → %.1f MB(增加 %.1f MB)\n", N, h0, heap(), heap()-h0)
	case "timer":
		for i := 0; i < N; i++ { time.NewTimer(time.Hour) }
		fmt.Printf("  %d 个 NewTimer(1h) 丢掉不 Stop:GC 之后堆 %.1f MB → %.1f MB(增加 %.1f MB)\n", N, h0, heap(), heap()-h0)
	case "keep":
		var keep []*time.Ticker
		for i := 0; i < N; i++ { keep = append(keep, time.NewTicker(time.Hour)) }
		fmt.Printf("  %d 个 NewTicker(1h) 放进切片保留(对照):GC 之后堆 %.1f MB → %.1f MB(增加 %.1f MB)\n", N, h0, heap(), heap()-h0)
		runtime.KeepAlive(keep)
	case "cost":
		ch := make(chan int)
		a1 := testing.AllocsPerRun(10000, func() {
			select { case <-ch: case <-time.After(time.Hour): default: }
		})
		tm := time.NewTimer(time.Hour)
		a2 := testing.AllocsPerRun(10000, func() {
			tm.Reset(time.Hour)
			select { case <-ch: case <-tm.C: default: }
		})
		const M = 1000000
		t0 := time.Now()
		for i := 0; i < M; i++ { select { case <-ch: case <-time.After(time.Hour): default: } }
		e1 := time.Since(t0)
		t0 = time.Now()
		for i := 0; i < M; i++ { tm.Reset(time.Hour); select { case <-ch: case <-tm.C: default: } }
		e2 := time.Since(t0)
		fmt.Printf("  每轮 select 里放 time.After(1h):%.0f 次分配,%.0f ns/轮;复用一个 Timer 并 Reset:%.0f 次分配,%.0f ns/轮(各 %d 轮)\n", a1, float64(e1.Nanoseconds())/M, a2, float64(e2.Nanoseconds())/M, M)
	case "slow":
		tk := time.NewTicker(10 * time.Millisecond)
		defer tk.Stop()
		got := 0
		end := time.Now().Add(600 * time.Millisecond)
		for time.Now().Before(end) {
			<-tk.C
			got++
			time.Sleep(55 * time.Millisecond) // 接收方比周期慢
		}
		fmt.Printf("  周期 10 ms 的 Ticker,接收方每次处理 55 ms:600 ms 里收到 %d 个 tick(按周期应有 60 个)\n", got)
	}
}
'''
d = gdir('tk1'); write(d, {'main.go': SRC}); mod(d, go='1.27')
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
d2 = gdir('tk2'); write(d2, {'main.go': SRC}); mod(d2, go='1.22')
rc, o = go(d2, 'build', '-o', 'app'); assert rc == 0, o
def run(dd, mode, gd=None, tmo=300):
    e = dict(os.environ)
    if gd: e['GODEBUG'] = gd
    p = subprocess.run([str(dd / 'app'), mode], capture_output=True, text=True, timeout=tmo, env=e)
    return (p.stdout + p.stderr).rstrip()
def one(dd, mode, gd=None):
    return run(dd, mode, gd).split('\n')[0]
print('== 一:不保存、不 Stop 的定时器和 Ticker,GC 之后堆有没有增长(Go 1.27.1,arm64 macOS,go.mod 写 go 1.27)')
for mode in ('ticker', 'tick', 'timer', 'after'):
    print(run(d, mode))
print(run(d, 'keep'))
print('== 二:想复现“Go 1.23 之前会泄漏”:GODEBUG=asynctimerchan=1 与 go.mod 写 go 1.22')
print('  [go 1.27 + GODEBUG=asynctimerchan=1] ' + one(d, 'ticker', 'asynctimerchan=1'))
print('  [go.mod 写 go 1.22] ' + run(d2, 'ticker').strip())
print('  [go.mod 写 go 1.22,select+time.After 循环] ' + run(d2, 'after').strip())
gd = open(GOROOT + '/doc/godebug.md').read().split('\n')
for k in ('Go 1.27 removed the `asynctimerchan` setting', 'This setting will be removed in Go 1.27.'):
    i = next(i for i, l in enumerate(gd) if k in l)
    print('  godebug.md:' + str(i + 1) + ': ' + gd[i].strip())
print('== 三:没有泄漏不等于没有成本:热循环里每轮 time.After 与复用一个 Timer')
print(run(d, 'cost'))
print('== 四:仍然保留的 Ticker:接收方太慢时 tick 被丢弃(文档:will adjust the time interval or drop ticks)')
print(run(d, 'slow'))
print('== 五:文档原文(go doc)')
for sym, a, b in (('time.NewTicker', 3, 18), ('time.After', 3, 14)):
    r, o = go(gdir('doc1'), 'doc', sym)
    print(f'  go doc {sym}(节选):')
    for l in o.split('\n')[a:b]:
        if l.strip(): print('    ' + l.strip())
