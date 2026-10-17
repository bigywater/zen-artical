import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g65')
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

var rw sync.RWMutex

func ms(d time.Duration) float64 { return float64(d.Microseconds()) / 1000 }

func spinFor(d time.Duration) { end := time.Now().Add(d); for time.Now().Before(end) {} }

func main() {
	runtime.GOMAXPROCS(8)
	switch os.Args[1] {
	case "recursive":
		// A 持读锁;B 调 Lock 开始等;A 再调一次 RLock
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			rw.RLock()
			time.Sleep(50 * time.Millisecond) // 让 B 的 Lock 排上队
			fmt.Println("  A: 已持有读锁,现在第二次 RLock …")
			rw.RLock()
			fmt.Println("  A: 第二次 RLock 成功(不应该走到这里)")
		}()
		go func() {
			defer wg.Done()
			time.Sleep(10 * time.Millisecond)
			fmt.Println("  B: 调用 Lock …")
			rw.Lock()
			fmt.Println("  B: Lock 成功(不应该走到这里)")
		}()
		wg.Wait()
	case "tryrlock":
		rw.RLock()
		go func() { rw.Lock() }()
		time.Sleep(20 * time.Millisecond)
		fmt.Printf("  已有读者、且有写者在排队时,TryRLock() = %v\n", rw.TryRLock())
		fmt.Printf("  只有读者、没有写者时(换新锁),TryRLock() = ")
		var rw2 sync.RWMutex
		rw2.RLock()
		fmt.Printf("%v\n", rw2.TryRLock())
	case "timeline":
		// R1 在 t=0 持读锁 100 ms;W 在 t=10 ms 请求写锁(持有 20 ms);R2 在 t=20 ms 请求读锁
		t0 := time.Now()
		var wg sync.WaitGroup
		var r2got, wgot time.Duration
		wg.Add(3)
		go func() { defer wg.Done(); rw.RLock(); time.Sleep(100 * time.Millisecond); rw.RUnlock() }()
		go func() { defer wg.Done(); time.Sleep(10 * time.Millisecond); rw.Lock(); wgot = time.Since(t0); time.Sleep(20 * time.Millisecond); rw.Unlock() }()
		go func() { defer wg.Done(); time.Sleep(20 * time.Millisecond); rw.RLock(); r2got = time.Since(t0); rw.RUnlock() }()
		wg.Wait()
		fmt.Printf("  R1 在 0 ms 拿到读锁并持有 100 ms;W 在 10 ms 请求写锁,在 %.0f ms 拿到;R2 在 20 ms 请求读锁,在 %.0f ms 才拿到\n", ms(wgot), ms(r2got))
	case "writerwait":
		// 8 个读者不停地读(每次持锁 1 ms),写者请求 30 次写锁,量它每次等多久
		var stop atomic.Bool
		var wg sync.WaitGroup
		for i := 0; i < 8; i++ { wg.Add(1); go func() { defer wg.Done(); for !stop.Load() { rw.RLock(); spinFor(time.Millisecond); rw.RUnlock() } }() }
		time.Sleep(20 * time.Millisecond)
		var waits []float64
		for i := 0; i < 30; i++ {
			t := time.Now(); rw.Lock(); waits = append(waits, ms(time.Since(t))); rw.Unlock()
			time.Sleep(3 * time.Millisecond)
		}
		stop.Store(true); wg.Wait()
		sort.Float64s(waits)
		fmt.Printf("  8 个读者连续读(每次持锁约 1 ms),写者 30 次 Lock 的等待:最小 %.2f ms / 中位 %.2f ms / 最大 %.2f ms\n", waits[0], waits[15], waits[29])
	case "crossover":
		hold, _ := strconv.Atoi(os.Args[2])
		for _, kind := range []string{"RWMutex.RLock", "Mutex.Lock"} {
			var m sync.Mutex
			var rwl sync.RWMutex
			const N = 1_600_000
			var wg sync.WaitGroup
			n := N
			if hold >= 1000 { n = N / 100 }
			t0 := time.Now()
			for g := 0; g < 8; g++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					for i := 0; i < n/8; i++ {
						if kind == "Mutex.Lock" { m.Lock() } else { rwl.RLock() }
						if hold > 0 { spinFor(time.Duration(hold) * time.Nanosecond) }
						if kind == "Mutex.Lock" { m.Unlock() } else { rwl.RUnlock() }
					}
				}()
			}
			wg.Wait()
			fmt.Printf("  持有 %6d ns:%-14s 8 个 goroutine,总耗时 %8.1f ms(%d 次)\n", hold, kind, ms(time.Since(t0)), n)
		}
	}
}
'''
d = gdir('rw1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a, tmo=60):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=tmo)
    return (p.stdout + p.stderr).rstrip()
print('== 一:递归读锁:A 持读锁,B 调 Lock 开始排队,A 再调一次 RLock(Go 1.27.1,arm64 macOS)')
o = run('recursive')
print('\n'.join('  ' + l.strip() for l in o.split('\n') if l.strip() and not l.startswith('\t') and 'main.' not in l and 'sync.' not in l and 'runtime.' not in l and not l.startswith('/')))
print('== 二:写者排队时,新来的读者怎么办')
print(run('timeline'))
print(run('tryrlock'))
print('== 三:读者不停地读,写者会不会饿死')
print(run('writerwait'))
print('== 四:什么时候读写锁值得:8 个 goroutine 都只读,临界区持有的时间不同(Mutex 对 RWMutex)')
for h in (0, 100, 1000, 100000):
    print(run('crossover', h))
print('== 五:文档原文')
r, o = go(gdir('doc1'), 'doc', 'sync.RWMutex')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('If any goroutine calls RWMutex.Lock'))
print('  ' + ' '.join(ls[i:i + 7]))
