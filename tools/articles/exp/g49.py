import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g49')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"os/signal"
	"runtime"
	"sort"
	"sync/atomic"
	"syscall"
	"time"
)

var stop atomic.Bool

func spinNoCall() {
	// 没有函数调用的死循环:不依赖原子变量以外的任何东西
	var n uint64
	for {
		n++
		if n&0xfffffff == 0 && stop.Load() { return }
	}
}

func main() {
	mode := os.Args[1]
	switch mode {
	case "latency":
		// 一个 goroutine 死循环,另一个 goroutine 想在 10 ms 后醒来
		go spinNoCall()
		time.Sleep(time.Millisecond)
		var xs []float64
		for i := 0; i < 30; i++ {
			t0 := time.Now()
			time.Sleep(10 * time.Millisecond)
			xs = append(xs, float64(time.Since(t0).Microseconds())/1000)
		}
		stop.Store(true)
		sort.Float64s(xs)
		fmt.Printf("  main 每次 time.Sleep(10ms) 实际耗时:最小 %.1f ms / 中位 %.1f ms / 最大 %.1f ms(30 次,GOMAXPROCS=%d,GODEBUG=%q)\n", xs[0], xs[15], xs[29], runtime.GOMAXPROCS(0), os.Getenv("GODEBUG"))
	case "gc":
		go spinNoCall()
		time.Sleep(time.Millisecond)
		t0 := time.Now()
		runtime.GC()
		fmt.Printf("  死循环 goroutine 在跑时调用 runtime.GC():耗时 %.1f ms(GOMAXPROCS=%d,GODEBUG=%q)\n", float64(time.Since(t0).Microseconds())/1000, runtime.GOMAXPROCS(0), os.Getenv("GODEBUG"))
		stop.Store(true)
	case "sigurg":
		c := make(chan os.Signal, 4096)
		signal.Notify(c, syscall.SIGURG)
		go spinNoCall()
		time.Sleep(time.Millisecond)
		time.Sleep(1 * time.Second)
		stop.Store(true)
		time.Sleep(10 * time.Millisecond)
		fmt.Printf("  死循环的 goroutine 占着唯一的 P 跑了约 1 秒:收到 SIGURG %d 次(GOMAXPROCS=%d,GODEBUG=%q)\n", len(c), runtime.GOMAXPROCS(0), os.Getenv("GODEBUG"))
	}
}
'''
d = gdir('ap1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(mode, env=None, tmo=4):
    e = dict(os.environ); e.update(env or {})
    t0 = time.time()
    try:
        p = subprocess.run([str(d / 'app'), mode], capture_output=True, text=True, env=e, timeout=tmo)
        return (p.stdout + p.stderr).rstrip()
    except subprocess.TimeoutExpired:
        return f'  (超时:{tmo} s 内没有结束,被我杀掉了;GOMAXPROCS={e.get("GOMAXPROCS", "默认")},GODEBUG={e.get("GODEBUG", "")!r})'
print('== 一:只有 1 个 P,一个 goroutine 在没有函数调用的死循环里,另一个 goroutine 想睡 10 ms 后醒来(Go 1.27.1,arm64)')
print(run('latency', {'GOMAXPROCS': '1'}))
print(run('latency', {'GOMAXPROCS': '1', 'GODEBUG': 'asyncpreemptoff=1'}, tmo=15))
print('== 二:GC 需要停下所有 goroutine:死循环 goroutine 在跑时调用 runtime.GC()(GOMAXPROCS=2)')
print(run('gc', {'GOMAXPROCS': '2'}))
print(run('gc', {'GOMAXPROCS': '2', 'GODEBUG': 'asyncpreemptoff=1'}))
print('== 三:抢占信号 SIGURG:死循环占着 P 约 1 秒,os/signal 收到多少次 SIGURG')
print(run('sigurg', {'GOMAXPROCS': '1'}))
print(run('sigurg', {'GOMAXPROCS': '1', 'GODEBUG': 'asyncpreemptoff=1'}))
print('== 四:死循环在汇编里有没有抢占点(go build -gcflags=-S,spinNoCall 的循环体)')
r = grun('ap2', {'main.go': SRC}, gcflags='-S')
blk = [x for x in re.split(r'\n(?=main\.\S+ STEXT)', r['cout']) if x.startswith('main.spinNoCall STEXT')][0]
print('  ' + re.sub(r'\s+', ' ', blk.split('\n')[0])[:130])
ins = [re.sub(r'^\s*0x[0-9a-f]+ \d+ \(', '(', l).replace(str(GT) + '/', '').strip()[:100] for l in blk.split('\n') if not l.strip().startswith('rel ') and re.match(r'\s*0x', l)]
for l in ins[:14]: print('    ' + l)
print(f'  这个函数的汇编里 CALL 指令的个数:{len([l for l in ins if "CALL" in l])}(上面是整个函数:LEAF|NOFRAME,没有栈检查的序言,也没有任何调用)')
print('== 五:运行时源码里关于异步抢占与 SIGURG 的说明')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/'
def grep(f, pat, before=0, after=6, n=1):
    ln = subprocess.run(['grep', '-n', '-m', str(n), pat, base + f], capture_output=True, text=True).stdout.split(':')[0]
    if not ln: print(f'  {f}: (没找到 {pat})'); return
    ln = int(ln)
    o = subprocess.run(['sed', '-n', f'{ln - before},{ln + after}p', base + f], capture_output=True, text=True).stdout.rstrip()
    print(f'  {f}:{ln - before}-{ln + after}')
    for l in o.split('\n'): print('    ' + l)
grep('preempt.go', 'A goroutine can be preempted at any safe-point', 0, 15)
grep('proc.go', 'forcePreemptNS is the time slice', 0, 2)
grep('extern.go', 'asyncpreemptoff: asyncpreemptoff=1', 0, 2)
grep('signal_unix.go', 'sigPreempt is the signal used', 0, 1)
