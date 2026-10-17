import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g53')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/metrics"
	"sync/atomic"
	"syscall"
	"time"
)

var stop atomic.Bool

func cpu() float64 {
	var r syscall.Rusage
	syscall.Getrusage(0, &r)
	return float64(r.Utime.Sec+r.Stime.Sec) + float64(r.Utime.Usec+r.Stime.Usec)/1e6
}

func released() float64 {
	s := []metrics.Sample{{Name: "/memory/classes/heap/released:bytes"}}
	metrics.Read(s)
	return float64(s[0].Value.Uint64()) / 1e6
}

func main() {
	switch os.Args[1] {
	case "idle":
		c0 := cpu()
		time.Sleep(3500 * time.Millisecond)
		fmt.Printf("  完全空闲 3.5 秒:进程用掉的 CPU 时间 %.3f 秒\n", cpu()-c0)
	case "busy":
		n := runtime.GOMAXPROCS(0)
		for i := 0; i < n; i++ { go func() { x := 0; for !stop.Load() { x++ } ; _ = x }() }
		time.Sleep(3500 * time.Millisecond)
		stop.Store(true)
	case "forcegc":
		var m runtime.MemStats
		if len(os.Args) > 2 { runtime.GC() }
		runtime.ReadMemStats(&m)
		fmt.Printf("  启动后 %s:NumGC=%d,然后什么都不做,空闲 130 秒(不分配)\n", map[bool]string{true: "先调用了一次 runtime.GC()", false: "没有调用过 runtime.GC()"}[len(os.Args) > 2], m.NumGC)
		time.Sleep(130 * time.Second)
		runtime.ReadMemStats(&m)
		fmt.Printf("  130 秒后 NumGC=%d\n", m.NumGC)
	case "scav":
		buf := make([][]byte, 0, 100)
		for i := 0; i < 100; i++ { b := make([]byte, 4<<20); for j := 0; j < len(b); j += 4096 { b[j] = 1 }; buf = append(buf, b) }
		fmt.Printf("  分配并触碰 400 MB 之后:已归还给操作系统的堆 %.1f MB\n", released())
		buf = nil
		runtime.GC()
		t0 := time.Now()
		for time.Since(t0) < 12*time.Second {
			fmt.Printf("  释放引用并 GC 后第 %4.1f 秒:已归还 %.1f MB\n", time.Since(t0).Seconds(), released())
			time.Sleep(2 * time.Second)
		}
	}
}
'''
d = gdir('sm1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(mode, gd=None, env=None, tmo=300):
    e = dict(os.environ)
    if gd: e['GODEBUG'] = gd
    e.update(env or {})
    p = subprocess.run([str(d / 'app'), mode], capture_output=True, text=True, timeout=tmo, env=e)
    return (p.stdout + p.stderr).rstrip()
fg = subprocess.Popen([str(d / 'app'), 'forcegc'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ, GODEBUG='gctrace=1'))
fg2 = subprocess.Popen([str(d / 'app'), 'forcegc', 'pre'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ, GODEBUG='gctrace=1'))
def keep(txt, pat):
    return '\n'.join('  ' + l.strip() for l in txt.split('\n') if re.search(pat, l))
print('== 一:用 GODEBUG=schedtrace=1000 看调度器:完全空闲 vs 每个 P 都在空转(GOMAXPROCS=4,Go 1.27.1,arm64 macOS)')
o = run('idle', 'schedtrace=1000', {'GOMAXPROCS': '4'})
print(keep(o, 'SCHED')[:1400])
o = run('busy', 'schedtrace=1000', {'GOMAXPROCS': '4'})
print(keep(o, 'SCHED')[:1400])
print('== 二:空闲时 sysmon 的睡眠:进程的 CPU 时间(用 getrusage 读自己)')
for i in range(3): print(run('idle', None, {'GOMAXPROCS': '4'}))
print('== 三:空闲进程每 2 分钟被强制 GC 一次(gctrace=1,下面是进程输出,等待了约 130 秒)')
for lab, f in (('[A 没有调用过 runtime.GC()]', fg), ('[B 先调用一次 runtime.GC()]', fg2)):
    out, _ = f.communicate(timeout=300)
    print(lab)
    print('\n'.join('  ' + l for l in out.strip().split('\n')))
print('== 四:运行时源码(runtime/proc.go sysmon 函数里的注释与代码)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/proc.go'
def rng(a, b):
    o = subprocess.run(['sed', '-n', f'{a},{b}p', base], capture_output=True, text=True).stdout.rstrip()
    print(f'  {os.path.basename(base)}:{a}-{b}')
    for l in o.split('\n'): print('    ' + l)
def find(pat, nth=1):
    r = subprocess.run(['grep', '-n', pat, base], capture_output=True, text=True).stdout.strip().split('\n')
    return int(r[nth - 1].split(':')[0])
n = find('// poll network if not polled for more than 10ms'); rng(n, n + 3)
n = find('// Check if we need to update GOMAXPROCS at most once per second'); rng(n, n + 3)
n = find('// Kick the scavenger awake'); rng(n - 1, n + 1)
n = find('// retake P.s blocked in syscalls'); rng(n, n + 1)
n = find('// check if we need to force a GC'); rng(n, n + 1)
n = find('^var forcegcperiod'); rng(n - 5, n)
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/mgc.go'
n = find('it.s been more than forcegcperiod'); rng(n - 1, n + 1); n = find('lastgc != 0 && t.now-lastgc > forcegcperiod'); rng(n - 1, n)
