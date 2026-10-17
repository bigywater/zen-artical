import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g39')
SRC = r'''
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"runtime/metrics"
	"sync"
	"sync/atomic"
	"time"
)

type Node struct {
	next *Node
	pad  [5]int
}

var live []*Node
var ops atomic.Int64

func main() {
	liveMB := flag.Int("live", 50, "存活堆 MB")
	dur := flag.Duration("dur", 2*time.Second, "运行时间")
	workers := flag.Int("w", 4, "分配 goroutine 数")
	setPct := flag.Int("setgc", 0, "运行中途调用 debug.SetGCPercent(非 0 时)")
	flag.Parse()
	n := *liveMB * (1 << 20) / 56
	live = make([]*Node, n)
	for i := range live { live[i] = &Node{} }
	for i := range live { live[i].next = live[(i*7919)%n] }
	runtime.GC()

	read := func() (gogc uint64, goal uint64, cycles uint64) {
		s := []metrics.Sample{{Name: "/gc/gogc:percent"}, {Name: "/gc/heap/goal:bytes"}, {Name: "/gc/cycles/total:gc-cycles"}}
		metrics.Read(s)
		return s[0].Value.Uint64(), s[1].Value.Uint64(), s[2].Value.Uint64()
	}
	lv := []metrics.Sample{{Name: "/gc/heap/live:bytes"}}
	metrics.Read(lv)
	liveBytes := lv[0].Value.Uint64()
	g0, goal0, c0 := read()
	var wg sync.WaitGroup
	stop := make(chan struct{})
	for w := 0; w < *workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var sink *Node
			for {
				select {
				case <-stop:
					return
				default:
				}
				for i := 0; i < 1000; i++ {
					sink = &Node{}
					sink.pad[0] = i
				}
				ops.Add(1000)
			}
			_ = sink
		}()
	}
	t0 := time.Now()
	if *setPct != 0 {
		time.Sleep(*dur / 2)
		old := debug.SetGCPercent(*setPct)
		fmt.Fprintf(os.Stderr, "SetGCPercent(%d) 返回旧值 %d\n", *setPct, old)
		time.Sleep(*dur / 2)
	} else {
		time.Sleep(*dur)
	}
	close(stop)
	wg.Wait()
	g1, goal1, c1 := read()
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	fmt.Printf("gogc=%d→%d live_MB=%.2f goal_MB=%.1f→%.1f cycles=%d ops_per_s=%.0f heapsys_MB=%.0f\n", g0, g1, float64(liveBytes)/(1<<20), float64(goal0)/(1<<20), float64(goal1)/(1<<20), c1-c0, float64(ops.Load())/time.Since(t0).Seconds(), float64(ms.HeapSys)/(1<<20))
	runtime.KeepAlive(live)
}
'''
d = gdir('pc1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(env=None, args=(), trace=False, tmo=60):
    e = dict(os.environ)
    if trace: e['GODEBUG'] = 'gctrace=1'
    e.update(env or {})
    p = subprocess.run([str(d / 'app'), *args], capture_output=True, text=True, env=e, timeout=tmo)
    return p.stdout.strip(), p.stderr
def parse(line):
    return dict(x.split('=') for x in line.split())
print('== 一:GOGC 与堆目标:存活堆 50 MB,4 个 goroutine 持续分配垃圾 2 秒,不同 GOGC(runtime/metrics 读出的值)')
rows = []
for gogc in ('25', '50', '100', '200', '400', '800'):
    o, _ = run({'GOGC': gogc}, ['-live', '50'])
    m = parse(o); rows.append((gogc, m))
    print(f'  GOGC={gogc:>3s}:{o}')
print('  对照:运行开始时(刚做完一次 GC)的堆目标 = 存活堆 × (1 + GOGC/100)(栈与全局变量在这个程序里不到 1 MB,忽略):')
for gogc, m in rows:
    live = float(m['live_MB']); g0 = float(m['goal_MB'].split('→')[0]); pred = live * (1 + int(gogc) / 100)
    print(f'    GOGC={gogc:>3s}:存活堆 {live:.2f} MB;开始时的目标 {g0:.1f} MB;按 {live:.2f} × (1 + {gogc}/100) = {pred:.1f} MB 预测,差 {g0 - pred:+.1f} MB')
print('  运行结束时读到的目标比开始时大,和分配速度有关:同样的 GOGC=100,不同的分配 goroutine 数,结束时的目标:')
for w in (1, 2, 4):
    o, _ = run({'GOGC': '100'}, ['-live', '50', '-w', str(w)])
    m = parse(o); print(f'    {w} 个分配 goroutine:目标 {m["goal_MB"]}(MB,开始→结束);吞吐 {float(m["ops_per_s"]) / 1e6:.1f} M 次/秒')

print('== 二:GOGC 的取舍:GC 次数、GC 的 CPU 时间(gctrace)、分配吞吐与内存占用(同样的 2 秒)')
def agg(err):
    ls = [l for l in err.split('\n') if l.startswith('gc ')]
    cpu = 0.0; stw = 0.0; assist = 0.0; peak = 0
    for l in ls:
        m = re.match(r'gc \d+ @[\d.]+s \d+%: ([\d.]+)\+([\d.]+)\+([\d.]+) ms clock, ([\d.]+)\+([\d.]+)/([\d.]+)/([\d.]+)\+([\d.]+) ms cpu, (\d+)->(\d+)->(\d+) MB', l)
        if m:
            g = list(map(float, m.groups()))
            cpu += g[3] + g[4] + g[5] + g[6] + g[7]; assist += g[4]; stw = max(stw, g[0] + g[2]); peak = max(peak, g[8], g[9])
    return len(ls), cpu, assist, stw, peak
for gogc in ('25', '50', '100', '200', '400', '800'):
    o, err = run({'GOGC': gogc}, ['-live', '50'], trace=True)
    m = parse(o); n, cpu, assist, stw, peak = agg(err)
    print(f'  GOGC={gogc:>3s}:GC {n:5d} 次;GC CPU 合计 {cpu:7.0f} ms(其中 assist {assist:6.0f} ms);峰值堆(gctrace 第一/二个数)约 {peak:.0f} MB;吞吐 {float(m["ops_per_s"]) / 1e6:6.1f} M 次分配/秒')

print('== 三:GOGC=off 与运行时 SetGCPercent')
o, err = run({'GOGC': 'off'}, ['-live', '50', '-dur', '1s'], trace=True)
print(f'  GOGC=off,运行 1 秒:{o};gctrace 行数 {len([l for l in err.split(chr(10)) if l.startswith("gc ")])}(没有任何一次由分配触发的 GC)')
o, err = run({'GOGC': '100'}, ['-live', '50', '-dur', '2s', '-setgc', '400'], trace=True)
print('  运行中途 debug.SetGCPercent(400):' + o + ';' + [l for l in err.split('\n') if 'SetGCPercent' in l][0])
ls = [l for l in err.split('\n') if l.startswith('gc ')]
goals = [int(re.search(r'(\d+) MB goal', l).group(1)) for l in ls if re.search(r'(\d+) MB goal', l)]
print(f'    gctrace 里的 “MB goal” 序列(前半 GOGC=100,后半 400):' + ' '.join(map(str, goals[:6])) + ' … ' + ' '.join(map(str, goals[-6:])))

print('== 四:最小堆目标 4 MB:存活堆很小时的 GC 频率(存活堆 1 MB)')
o, err = run({'GOGC': '100'}, ['-live', '1', '-dur', '1s'], trace=True)
ls = [l for l in err.split('\n') if l.startswith('gc ')]
print(f'  {o}')
print('  前 3 行 gctrace:'); [print('    ' + l[:120]) for l in ls[:3]]
print('== 五:分配得快会触发 mark assist:同样的负载把 worker 数从 1 加到 8,assist 时间(gctrace 的 CPU 时间第二段第一个数)')
for w in (1, 4, 8):
    o, err = run({'GOGC': '100'}, ['-live', '200', '-w', str(w), '-dur', '2s'], trace=True)
    n, cpu, assist, stw, peak = agg(err); m = parse(o)
    print(f'  {w} 个分配 goroutine:GC {n} 次;GC CPU {cpu:.0f} ms,其中 assist {assist:.0f} ms;吞吐 {float(m["ops_per_s"]) / 1e6:.1f} M 次/秒')
