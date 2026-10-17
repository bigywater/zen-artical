import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g46')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"sync"
	"time"
)

var sink uint64

func spin(d time.Duration) {
	t0 := time.Now()
	x := uint64(1)
	for time.Since(t0) < d {
		for i := 0; i < 1000; i++ { x = x*6364136223846793005 + 1442695040888963407 }
	}
	sink += x
}

func main() {
	mode := os.Args[1]
	n, _ := strconv.Atoi(os.Args[2])
	switch mode {
	case "speedup":
		var wg sync.WaitGroup
		t0 := time.Now()
		for i := 0; i < n; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); spin(5 * time.Millisecond) }()
		}
		wg.Wait()
		fmt.Printf("%d\n", time.Since(t0).Milliseconds())
	case "spawn":
		// 一个 goroutine 一口气创建 n 个任务,然后自己也忙一会儿
		var wg sync.WaitGroup
		for i := 0; i < n; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); spin(3 * time.Millisecond) }()
		}
		spin(20 * time.Millisecond)
		wg.Wait()
		fmt.Println("done", runtime.GOMAXPROCS(0))
	}
}
'''
d = gdir('ws1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(mode, n, env=None, tmo=120):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run([str(d / 'app'), mode, str(n)], capture_output=True, text=True, env=e, timeout=tmo)

print('== 一:一个 goroutine 创建了全部任务,其它 P 怎么拿到活:200 个各自忙 5 ms 的 goroutine(总共 1000 ms 的 CPU 工作),不同 GOMAXPROCS 下的墙钟时间')
base = None
for pp in (1, 2, 4, 8, 10):
    ts = sorted(int(run('speedup', 200, {'GOMAXPROCS': str(pp)}).stdout.strip()) for _ in range(5))
    m = ts[2]
    if base is None: base = m
    print(f'  GOMAXPROCS={pp:2d}:{ts} ms(中位 {m} ms);相对 1 个 P 的加速比 {base / m:.2f}(理想 {pp})')

print('== 二:schedtrace 看各个 P 的本地队列:GODEBUG=schedtrace=1,scheddetail=1(每 1 ms 一次),任务数 1000,GOMAXPROCS=4')
p = run('spawn', 1000, {'GOMAXPROCS': '4', 'GODEBUG': 'schedtrace=1,scheddetail=1'})
txt = p.stderr
blocks = re.split(r'(?=^SCHED )', txt, flags=re.M)
rows = []
for b in blocks:
    m = re.match(r'SCHED (\d+)ms: gomaxprocs=(\d+) idleprocs=(\d+) threads=(\d+) spinningthreads=(\d+) needspinning=\d+ idlethreads=(\d+) runqueue=(\d+)', b)
    if not m: continue
    t, gm, idle, thr, spin_, idlet, grq = map(int, m.groups())
    ps = [int(x) for x in re.findall(r'P\d+: status=\d+ schedtick=\d+ syscalltick=\d+ m=\S+ runqsize=(\d+)', b)]
    rows.append((t, idle, thr, spin_, grq, ps))
print(f'  共 {len(rows)} 个采样点;挑选其中变化有代表性的几个(时间 ms | idleprocs | spinningthreads | 全局队列 runqueue | 各 P 本地队列 runqsize):')
shown = 0; last = None
for t, idle, thr, spin_, grq, ps in rows:
    key = (idle, grq, tuple(ps))
    if key != last and shown < 10:
        print(f'    {t:3d} ms | idle={idle} | spinning={spin_} | 全局 {grq:4d} | 本地 {ps}')
        shown += 1
    last = key
mx = max((max(ps) if ps else 0) for *_, ps in rows)
print(f'  所有采样里单个 P 本地队列的最大长度:{mx}')
print(f'  全局队列的最大长度:{max(r[4] for r in rows)}')

print('== 三:运行时源码里窃取的几个关键点(runtime/proc.go 原样摘录)')
base_src = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/proc.go'
def grep_ctx(pat, before, after, maxl=14):
    n = int(subprocess.run(['grep', '-n', '-m', '1', pat, base_src], capture_output=True, text=True).stdout.split(':')[0])
    o = subprocess.run(['sed', '-n', f'{n - before},{n + after}p', base_src], capture_output=True, text=True).stdout.rstrip().split('\n')
    print(f'  proc.go:{n - before}-{n + after}')
    for l in o[:maxl]: print('    ' + l)
grep_ctx('^func runqgrab', 3, 12)
grep_ctx('n = n - n/2', 3, 3)
grep_ctx('^const stealTries\\|const stealTries = 4', 0, 0, 1)
grep_ctx('stealTimersOrRunNextG := i == stealTries-1', 3, 4)
grep_ctx('^var runqsize\\|len(pp.runq)\\|runq        \\[256\\]guintptr', 0, 0, 1)
