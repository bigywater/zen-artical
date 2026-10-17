import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g51')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sort"
	"testing"
	"time"
)

func med(xs []float64) (float64, float64, float64) {
	sort.Float64s(xs)
	return xs[0], xs[len(xs)/2], xs[len(xs)-1]
}

func heapNow() uint64 { runtime.GC(); var m runtime.MemStats; runtime.ReadMemStats(&m); return m.HeapAlloc }

func main() {
	switch os.Args[1] {
	case "alloc":
		a := testing.AllocsPerRun(1000, func() { t := time.NewTimer(time.Hour); t.Stop() })
		fmt.Printf("  time.NewTimer(1h)+Stop:每次 %.0f 次分配\n", a)
		a = testing.AllocsPerRun(1000, func() { t := time.AfterFunc(time.Hour, func() {}); t.Stop() })
		fmt.Printf("  time.AfterFunc(1h, f)+Stop:每次 %.0f 次分配\n", a)
		a = testing.AllocsPerRun(1000, func() { t := time.NewTicker(time.Hour); t.Stop() })
		fmt.Printf("  time.NewTicker(1h)+Stop:每次 %.0f 次分配\n", a)
		a = testing.AllocsPerRun(1000, func() { time.Sleep(time.Microsecond) })
		fmt.Printf("  time.Sleep(1µs):每次 %.0f 次分配\n", a)
		const N = 200000
		keep := make([]*time.Timer, 0, N)
		h0 := heapNow()
		for i := 0; i < N; i++ { keep = append(keep, time.NewTimer(time.Hour)) }
		h1 := heapNow()
		fmt.Printf("  保留 %d 个 time.NewTimer(1h):堆增加 %.1f MB,平均每个 %.0f 字节(含存放指针的切片 8 字节)\n", N, float64(h1-h0)/1e6, float64(h1-h0)/N)
		keep2 := make([]*time.Timer, 0, N)
		for i := 0; i < N; i++ { keep2 = append(keep2, time.AfterFunc(time.Hour, func() {})) }
		h2 := heapNow()
		fmt.Printf("  再保留 %d 个 time.AfterFunc(1h):堆又增加 %.1f MB,平均每个 %.0f 字节\n", N, float64(h2-h1)/1e6, float64(h2-h1)/N)
		runtime.KeepAlive(keep); runtime.KeepAlive(keep2)
	case "chan":
		t := time.NewTimer(time.Hour)
		fmt.Printf("  NewTimer(1h):cap(t.C)=%d len(t.C)=%d\n", cap(t.C), len(t.C))
		t2 := time.NewTimer(time.Millisecond)
		time.Sleep(20 * time.Millisecond)
		fmt.Printf("  NewTimer(1ms) 到期 20ms 后、还没人读:len(t.C)=%d cap(t.C)=%d\n", len(t2.C), cap(t2.C))
		ok := t2.Reset(time.Hour)
		select {
		case <-t2.C: fmt.Println("  Reset 之后仍然读到旧的到期值")
		default: fmt.Printf("  Reset(1h) 返回 %v;Reset 之后立刻读 t.C:没有旧值(非阻塞读走了 default)\n", ok)
		}
		t3 := time.NewTimer(time.Millisecond)
		time.Sleep(20 * time.Millisecond)
		fmt.Printf("  到期未读的定时器 Stop() 返回 %v\n", t3.Stop())
		select {
		case <-t3.C: fmt.Println("  Stop 之后仍能读到旧值")
		default: fmt.Println("  Stop 之后读 t.C:没有旧值")
		}
	case "prec":
		for _, d := range []time.Duration{10 * time.Microsecond, 100 * time.Microsecond, time.Millisecond, 10 * time.Millisecond} {
			var xs []float64
			for i := 0; i < 200; i++ {
				t0 := time.Now()
				time.Sleep(d)
				xs = append(xs, float64(time.Since(t0)-d)/1000)
			}
			a, b, c := med(xs)
			fmt.Printf("  time.Sleep(%7v) 超时(实际耗时 − 请求):最小 %6.0f µs / 中位 %6.0f µs / 最大 %7.0f µs(200 次)\n", d, a, b, c)
		}
		for _, d := range []time.Duration{100 * time.Microsecond, time.Millisecond} {
			var xs []float64
			for i := 0; i < 200; i++ {
				tm := time.NewTimer(d)
				t0 := time.Now()
				<-tm.C
				xs = append(xs, float64(time.Since(t0)-d)/1000)
			}
			a, b, c := med(xs)
			fmt.Printf("  NewTimer(%7v) 并 <-t.C 超时:最小 %6.0f µs / 中位 %6.0f µs / 最大 %7.0f µs(200 次)\n", d, a, b, c)
		}
	case "scale":
		// 在已有 n 个“待触发”的定时器时,再创建+停止一个新的要多久
		for _, kind := range []string{"AfterFunc", "NewTimer(无人等待)", "NewTimer(有 goroutine 阻塞在 t.C)"} {
			for _, n := range []int{1000, 100000, 1000000} {
				var keep []*time.Timer
				for i := 0; i < n; i++ {
					switch kind {
					case "AfterFunc": keep = append(keep, time.AfterFunc(time.Hour+time.Duration(i)*time.Millisecond, func() {}))
					case "NewTimer(无人等待)": keep = append(keep, time.NewTimer(time.Hour+time.Duration(i)*time.Millisecond))
					default:
						tm := time.NewTimer(time.Hour + time.Duration(i)*time.Millisecond)
						keep = append(keep, tm)
						go func() { <-tm.C }()
					}
				}
				time.Sleep(200 * time.Millisecond)
				const M = 200000
				t0 := time.Now()
				for i := 0; i < M; i++ {
					var t *time.Timer
					if kind == "AfterFunc" { t = time.AfterFunc(30*time.Minute, func() {}) } else { t = time.NewTimer(30 * time.Minute) }
					t.Stop()
				}
				el := time.Since(t0)
				fmt.Printf("  %-34s 已有 %7d 个:创建+Stop 一个新的 %5.0f ns\n", kind, n, float64(el.Nanoseconds())/M)
				for _, t := range keep { t.Stop() }
				keep = nil
				runtime.GC()
			}
		}
	}
}
'''
d = gdir('tm1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a, env=None, tmo=300):
    e = dict(os.environ); e.update(env or {})
    p = subprocess.run([str(d / 'app'), *a], capture_output=True, text=True, timeout=tmo, env=e)
    return (p.stdout + p.stderr).rstrip()
print('== 一:一个定时器占多少内存、分配几次(Go 1.27.1,arm64 macOS)')
print(run('alloc'))
print('== 二:定时器的通道:Go 1.23 起 cap 和 len 恒为 0,Reset/Stop 之后不会读到旧值')
print(run('chan'))
print('== 三:到点之后多久被唤醒(超时 = 实际耗时 − 请求的时长)')
print(run('prec'))
print('== 四:已有大量待触发的定时器时,创建并停止一个新的要多久')
print(run('scale'))
print('== 五:运行时源码(runtime/time.go)里的说明')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/time.go'
def ctx(pat, before, after):
    n = int(subprocess.run(['grep', '-n', '-m', '1', pat, base], capture_output=True, text=True).stdout.split(':')[0])
    o = subprocess.run(['sed', '-n', f'{n - before},{n + after}p', base], capture_output=True, text=True).stdout.rstrip()
    print(f'  time.go:{n - before}-{n + after}')
    for l in o.split('\n'): print('    ' + l)
ctx('^// A timers is a per-P set of timers', 0, 9)
ctx('^// needsAdd reports whether', 0, 5)
for sym, a, b in (('time.Timer.Stop', 11, 18), ('time.NewTimer', 4, 12)):
    r, o = go(gdir('doc1'), 'doc', sym)
    print(f'  go doc {sym}(节选):')
    for l in o.split('\n')[a:b]: print('    ' + l.strip())
