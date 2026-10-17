import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g48')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sort"
	"syscall"
	"time"
	"unsafe"
)

// 阻塞 d 微秒的系统调用:select(0, nil, nil, nil, &tv)
func selectSleep(us int64, raw bool) {
	tv := syscall.Timeval{Sec: us / 1_000_000, Usec: int32(us % 1_000_000)}
	if raw {
		syscall.RawSyscall6(syscall.SYS_SELECT, 0, 0, 0, 0, uintptr(unsafe.Pointer(&tv)), 0)
	} else {
		syscall.Syscall6(syscall.SYS_SELECT, 0, 0, 0, 0, uintptr(unsafe.Pointer(&tv)), 0)
	}
}

func stats(xs []float64) string {
	sort.Float64s(xs)
	return fmt.Sprintf("最小 %.0f µs / 中位 %.0f µs / 最大 %.0f µs", xs[0], xs[len(xs)/2], xs[len(xs)-1])
}

func main() {
	if os.Getenv("GOMAXPROCS") == "" { runtime.GOMAXPROCS(1) }
	mode := os.Args[1]
	raw := mode == "raw"
	for _, us := range []int64{100, 1000, 10000, 100000} {
		var delays, totals []float64
		for trial := 0; trial < 20; trial++ {
			ch := make(chan time.Time, 1)
			t0 := time.Now()
			go func() { ch <- time.Now() }() // 另一个可运行的 goroutine,只有一个 P,它得等 P 空出来
			selectSleep(us, raw)
			tEnd := time.Now()
			tb := <-ch
			delays = append(delays, float64(tb.Sub(t0).Nanoseconds())/1000)
			totals = append(totals, float64(tEnd.Sub(t0).Nanoseconds())/1000)
		}
		fmt.Printf("  系统调用阻塞 %6d µs:另一个 goroutine 开始运行的延迟 %s;系统调用本身耗时中位 %.0f µs\n", us, stats(delays), func() float64 { sort.Float64s(totals); return totals[len(totals)/2] }())
	}
}
'''
d = gdir('sh1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a, env=None, tmo=120):
    e = dict(os.environ); e.update(env or {})
    p = subprocess.run([str(d / 'app'), *a], capture_output=True, text=True, timeout=tmo, env=e)
    return (p.stdout + p.stderr).rstrip()
print('== 一:GOMAXPROCS=1,一个 goroutine 进入阻塞的系统调用时,另一个等着运行的 goroutine 多久能拿到 P(syscall.Syscall6,会通知运行时 entersyscall)')
print(run('normal'))
print('== 二:绕开运行时的系统调用(syscall.RawSyscall6,不通知运行时):P 不会被移交')
print(run('raw'))
print('== 三:同样的负载,GOMAXPROCS=4:有空闲的 P 时,另一个 goroutine 几乎不用等')
print(run('normal', env={'GOMAXPROCS': '4'}).replace('GOMAXPROCS=1', 'GOMAXPROCS=4'))
print('== 四:运行时源码里 sysmon 与 retake 的说明(runtime/proc.go 原样摘录)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/proc.go'
def ctx(pat, before, after):
    n = int(subprocess.run(['grep', '-n', '-m', '1', pat, base], capture_output=True, text=True).stdout.split(':')[0])
    o = subprocess.run(['sed', '-n', f'{n - before},{n + after}p', base], capture_output=True, text=True).stdout.rstrip()
    print(f'  proc.go:{n - before}-{n + after}')
    for l in o.split('\n'): print('    ' + l)
ctx('start with 20us sleep', 1, 9)
ctx("Retake the P if it's there for more than 1 sysmon tick", 0, 22)
