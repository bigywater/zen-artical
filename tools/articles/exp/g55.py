import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g55')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/pprof"
	"strconv"
	"sync"
	"time"
)

var sink uint64

//go:noinline
func workA(n int) { x := sink; for i := 0; i < n; i++ { x = x*6364136223846793005 + 1442695040888963407 }; sink = x }

//go:noinline
func workB(n int) { x := sink; for i := 0; i < n; i++ { x = x*6364136223846793005 + 1442695040888963407 }; sink = x }

//go:noinline
func workC(n int) { x := sink; for i := 0; i < n; i++ { x = x*6364136223846793005 + 1442695040888963407 }; sink = x }

const unit = 2_000_000 // 一个单位的迭代数

// 一轮:A 6 单位,B 3 单位,C 1 单位,返回各自实际花的纳秒
func cycle(acc *[3]time.Duration) {
	t := time.Now(); workA(6 * unit); acc[0] += time.Since(t)
	t = time.Now(); workB(3 * unit); acc[1] += time.Since(t)
	t = time.Now(); workC(1 * unit); acc[2] += time.Since(t)
}

func main() {
	mode := os.Args[1]
	ms, _ := strconv.Atoi(os.Args[2])
	f, _ := os.Create(os.Args[3])
	pprof.StartCPUProfile(f)
	end := time.Now().Add(time.Duration(ms) * time.Millisecond)
	switch mode {
	case "one":
		var acc [3]time.Duration
		for time.Now().Before(end) { cycle(&acc) }
		tot := acc[0] + acc[1] + acc[2]
		fmt.Printf("TRUE %.1f %.1f %.1f\n", 100*float64(acc[0])/float64(tot), 100*float64(acc[1])/float64(tot), 100*float64(acc[2])/float64(tot))
	case "multi":
		var wg sync.WaitGroup
		for g := 0; g < runtime.GOMAXPROCS(0); g++ {
			wg.Add(1)
			go func() { defer wg.Done(); var acc [3]time.Duration; for time.Now().Before(end) { cycle(&acc) } }()
		}
		wg.Wait()
	case "sleepy":
		// 每轮先 workA,再 Sleep 4ms
		for time.Now().Before(end) { workA(2 * unit); time.Sleep(4 * time.Millisecond) }
	}
	pprof.StopCPUProfile()
	f.Close()
}
'''
d = gdir('pf1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(mode, ms, env=None):
    e = dict(os.environ); e.update(env or {})
    prof = str(d / f'{mode}.prof')
    p = subprocess.run([str(d / 'app'), mode, str(ms), prof], capture_output=True, text=True, timeout=120, env=e)
    return p.stdout.strip(), prof
def top(prof, n=6):
    r = subprocess.run([GO, 'tool', 'pprof', '-top', f'-nodecount={n}', str(d / 'app'), prof], capture_output=True, text=True, env=genv())
    return [l for l in (r.stdout + r.stderr).split('\n') if l.strip() and not l.startswith('Time:') and not l.startswith('File:') and not l.startswith('Build ID')]
def share(prof):
    r = subprocess.run([GO, 'tool', 'pprof', '-top', '-nodecount=10', str(d / 'app'), prof], capture_output=True, text=True, env=genv())
    out = {}
    for l in r.stdout.split('\n'):
        m = re.match(r'\s*\S+\s+\S+%\s+\S+%\s+(\S+?)(s|ms)\s+\S+%\s+main\.work([ABC])', l)
        if m: out[m.group(3)] = float(m.group(1)) * (1 if m.group(2) == 's' else .001)
    tot = sum(out.values())
    return {k: 100 * v / tot for k, v in out.items()} if tot else {}
print('== 一:单个 goroutine 空转 5 秒,A:B:C 的 CPU 时间之比约 6:3:1(Go 1.27.1,arm64 macOS)')
o, prof = run('one', 5000, {'GOMAXPROCS': '4'})
t = o.split()
print(f'  程序自己用 time.Now 量的真实占比:A {t[1]}% / B {t[2]}% / C {t[3]}%')
for l in top(prof): print('  ' + l)
print('== 二:4 个 goroutine 同时空转 2 秒(GOMAXPROCS=4):Total samples 可以超过墙钟时间')
o, prof = run('multi', 2000, {'GOMAXPROCS': '4'})
for l in top(prof, 6): print('  ' + l)
print('== 三:每轮 workA 之后 time.Sleep(4ms)(跑 3 秒):睡着的时间不会算进 CPU profile,但调用 Sleep 的路径会')
o, prof = run('sleepy', 3000, {'GOMAXPROCS': '4'})
for l in top(prof, 8): print('  ' + l)
print('== 四:采样窗口越短,估计越不准:C 的真实占比约 10%,每种窗口各跑 6 次')
for ms in (100, 300, 1000, 4000):
    vals = []
    for i in range(6):
        o, prof = run('one', ms, {'GOMAXPROCS': '4'})
        s = share(prof)
        if 'C' in s: vals.append(s['C'])
        else: vals.append(0.0)
    print(f'  窗口 {ms:5d} ms:C 的估计占比 最小 {min(vals):4.1f}% / 中位 {statistics.median(vals):4.1f}% / 最大 {max(vals):4.1f}%(6 次)')
print('== 五:源码里为什么是 100 Hz(runtime/pprof/pprof.go 原文)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/pprof/pprof.go'
n = int(subprocess.run(['grep', '-n', 'The runtime routines allow a variable profiling rate', base], capture_output=True, text=True).stdout.split(':')[0])
for l in subprocess.run(['sed', '-n', f'{n},{n + 9}p', base], capture_output=True, text=True).stdout.rstrip().split('\n'): print('  ' + l.strip())
