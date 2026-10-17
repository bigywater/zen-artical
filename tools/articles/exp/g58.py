import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g58')
SRC = r'''
package main

import (
	"context"
	"fmt"
	"os"
	"runtime"
	"runtime/trace"
	"sync"
	"time"
)

var mu sync.Mutex
var sink [][]byte

//go:noinline
func holdLock() {
	mu.Lock()
	time.Sleep(5 * time.Millisecond)
	mu.Unlock()
}

//go:noinline
func spin(ms int) {
	end := time.Now().Add(time.Duration(ms) * time.Millisecond)
	x := 0
	for time.Now().Before(end) { x++ }
	_ = x
}

func work() {
	var wg sync.WaitGroup
	for g := 0; g < 200; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < 400; i++ { sink = append(sink[:0], make([]byte, 512)) ; runtime.Gosched() }
		}()
	}
	wg.Wait()
}

func main() {
	mode := os.Args[1]
	if mode != "plain" {
		f, _ := os.Create(os.Args[2])
		trace.Start(f)
		defer func() { trace.Stop(); f.Close() }()
	}
	switch mode {
	case "sync":
		var wg sync.WaitGroup
		for g := 0; g < 4; g++ {
			wg.Add(1)
			go func() { defer wg.Done(); for i := 0; i < 5; i++ { holdLock() } }()
		}
		wg.Wait()
	case "sched":
		runtime.GOMAXPROCS(1)
		var wg sync.WaitGroup
		var tm sync.Mutex
		var sumStart, sumEnd time.Duration
		for g := 0; g < 20; g++ {
			wg.Add(1)
			created := time.Now()
			go func() {
				defer wg.Done()
				st := time.Since(created)
				spin(20)
				en := time.Since(created)
				tm.Lock(); sumStart += st; sumEnd += en; tm.Unlock()
			}()
		}
		wg.Wait()
		fmt.Printf("  程序自己量的:20 个 goroutine 从创建到第一次运行的等待之和 %.0f ms;从创建到结束的总时间之和 %.0f ms,减去它们各自的 20 ms 空转 = %.0f ms 的排队时间\n", float64(sumStart.Microseconds())/1000, float64(sumEnd.Microseconds())/1000, float64(sumEnd.Microseconds())/1000-400)
	case "task":
		ctx, task := trace.NewTask(context.Background(), "请求")
		for _, step := range []string{"解析", "查询", "渲染"} {
			trace.WithRegion(ctx, step, func() { time.Sleep(10 * time.Millisecond) })
		}
		trace.Log(ctx, "category", "done")
		task.End()
	case "traced", "plain":
		t0 := time.Now()
		work()
		fmt.Printf("%.3f\n", time.Since(t0).Seconds())
	}
}
'''
d = gdir('tr1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr).rstrip()
def tprof(kind, tf):
    r = subprocess.run([GO, 'tool', 'trace', f'-pprof={kind}', str(d / tf)], capture_output=True, env=genv())
    (d / f'{tf}.{kind}.pb').write_bytes(r.stdout)
    r2 = subprocess.run([GO, 'tool', 'pprof', '-top', '-nodecount=8', '-unit=ms', str(d / 'app'), str(d / f'{tf}.{kind}.pb')], capture_output=True, text=True, env=genv())
    return [l for l in (r2.stdout + r2.stderr).split('\n') if l.strip() and not re.match(r'(Time|File|Build ID):', l)]
print('== 一:4 个 goroutine 各 5 次抢同一把锁(每次持锁 5 ms),trace 之后用 go tool trace -pprof=sync 看同步阻塞(Go 1.27.1,arm64 macOS)')
run('sync', d / 't_sync.out')
print(f'  trace 文件 {os.path.getsize(d / "t_sync.out")} 字节')
for l in tprof('sync', 't_sync.out'): print('  ' + l)
print('== 二:GOMAXPROCS=1,20 个各自空转 20 ms 的 goroutine 同时就绪,go tool trace -pprof=sched 看“可运行但没在跑”的时间')
print(run('sched', d / 't_sched.out'))
print(f'  trace 文件 {os.path.getsize(d / "t_sched.out")} 字节')
for l in tprof('sched', 't_sched.out'): print('  ' + l)
print('== 三:用户标注:trace.NewTask 与 trace.WithRegion(三个各睡 10 ms 的步骤),trace 里能读到什么')
run('task', d / 't_task.out')
r = subprocess.run([GO, 'tool', 'trace', '-d=parsed', str(d / 't_task.out')], capture_output=True, text=True, env=genv())
lines = (r.stdout + r.stderr).split('\n')
sel = [l.strip()[:150] for l in lines if re.search(r'Task|Region|Log', l) and ('请求' in l or '解析' in l or '查询' in l or '渲染' in l or 'category' in l)]
print(f'  go tool trace -d=parsed 总共 {len([l for l in lines if l.strip()])} 行事件;与标注相关的 {len(sel)} 行,前 8 行:')
for l in sel[:8]: print('    ' + l)
ev = {}
for l in sel:
    m = re.search(r'(RegionBegin|RegionEnd) Time=(\d+) Task=1 Type="(.+?)"', l)
    if m: ev[(m.group(1), m.group(3))] = int(m.group(2))
for nm in ('解析', '查询', '渲染'):
    if ('RegionBegin', nm) in ev and ('RegionEnd', nm) in ev:
        print(f'  区域 {nm}:{(ev[("RegionEnd", nm)] - ev[("RegionBegin", nm)]) / 1e6:.2f} ms(代码里是 time.Sleep(10ms))')
print('== 四:开着 trace 的代价:200 个 goroutine 各分配 400 次并 Gosched,每种各跑 5 次')
for mode in ('plain', 'traced'):
    ts = []; sz = []
    for i in range(5):
        ts.append(float(run(mode, d / 't_ov.out')))
        if mode == 'traced': sz.append(os.path.getsize(d / 't_ov.out') / 1e6)
    extra = f';trace 文件 {min(sz):.1f}–{max(sz):.1f} MB' if sz else ''
    print(f'  {mode:7s}:耗时 最小 {min(ts):.3f} s / 中位 {statistics.median(ts):.3f} s / 最大 {max(ts):.3f} s{extra}')
print('== 五:文档与帮助的原文')
r, o = go(gdir('doc1'), 'doc', 'runtime/trace')
ls = o.split('\n')
for l in ls[3:13]:
    if l.strip(): print('  ' + l.strip())
r = subprocess.run([GO, 'tool', 'trace', '-h'], capture_output=True, text=True, env=genv())
for l in (r.stdout + r.stderr).split('\n'):
    if re.match(r'\s*- (net|sync|syscall|sched):', l): print('  ' + l.strip())
