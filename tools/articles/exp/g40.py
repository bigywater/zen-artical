import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g40')
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
	"syscall"
	"time"
)

type Node struct {
	next *Node
	pad  [5]int
}

var live []*Node
var ops atomic.Int64

func sample(names ...string) []metrics.Sample {
	s := make([]metrics.Sample, len(names))
	for i, n := range names { s[i].Name = n }
	metrics.Read(s)
	return s
}

func main() {
	liveMB := flag.Int("live", 200, "存活堆 MB")
	dur := flag.Duration("dur", 3*time.Second, "运行时间")
	workers := flag.Int("w", 4, "分配 goroutine 数")
	flag.Parse()
	n := *liveMB * (1 << 20) / 56
	live = make([]*Node, n)
	for i := range live { live[i] = &Node{} }
	for i := range live { live[i].next = live[(i*7919)%n] }
	runtime.GC()
	cur := debug.SetMemoryLimit(-1)
	fmt.Fprintf(os.Stderr, "SetMemoryLimit(-1) 读到当前限制:%d\n", cur)

	b0 := sample("/gc/cycles/total:gc-cycles", "/cpu/classes/gc/total:cpu-seconds", "/cpu/classes/total:cpu-seconds")
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
	var peak uint64
	t0 := time.Now()
	for time.Since(t0) < *dur {
		s := sample("/memory/classes/total:bytes")
		if v := s[0].Value.Uint64(); v > peak { peak = v }
		time.Sleep(3 * time.Millisecond)
	}
	el := time.Since(t0)
	close(stop)
	wg.Wait()
	b1 := sample("/gc/cycles/total:gc-cycles", "/cpu/classes/gc/total:cpu-seconds", "/cpu/classes/total:cpu-seconds", "/gc/limiter/last-enabled:gc-cycle", "/gc/heap/goal:bytes")
	var ru syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &ru)
	gcCPU := b1[1].Value.Float64() - b0[1].Value.Float64()
	totCPU := b1[2].Value.Float64() - b0[2].Value.Float64()
	fmt.Printf("cycles=%d ops_per_s=%.1fM peak_total_MB=%.0f maxrss_MB=%.0f gc_cpu_pct=%.1f limiter_last_cycle=%d goal_MB=%.0f\n",
		b1[0].Value.Uint64()-b0[0].Value.Uint64(), float64(ops.Load())/el.Seconds()/1e6, float64(peak)/(1<<20), float64(ru.Maxrss)/(1<<20), gcCPU/totCPU*100, b1[3].Value.Uint64(), float64(b1[4].Value.Uint64())/(1<<20))
	runtime.KeepAlive(live)
}
'''
d = gdir('ml1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(env=None, args=(), tmo=90):
    e = dict(os.environ); e.pop('GOMEMLIMIT', None); e.pop('GOGC', None)
    e.update(env or {})
    p = subprocess.run([str(d / 'app'), *args], capture_output=True, text=True, env=e, timeout=tmo)
    return p.stdout.strip(), p.stderr.strip()
print('== 一:几种设置下的表现(存活堆 200 MB,4 个 goroutine 持续分配垃圾,各跑 3 秒;Go 1.27.1,arm64)')
CASES = [
    ('A 不设限制,GOGC=100(默认)', {}),
    ('B GOMEMLIMIT=300MiB,GOGC=100', {'GOMEMLIMIT': '300MiB'}),
    ('C GOMEMLIMIT=300MiB,GOGC=off', {'GOMEMLIMIT': '300MiB', 'GOGC': 'off'}),
    ('D GOMEMLIMIT=240MiB,GOGC=off(只比存活堆多一点)', {'GOMEMLIMIT': '240MiB', 'GOGC': 'off'}),
    ('E GOMEMLIMIT=150MiB,GOGC=100(低于存活堆)', {'GOMEMLIMIT': '150MiB'}),
]
res = {}
for label, env in CASES:
    o, err = run(env)
    res[label] = o
    print(f'  {label}:')
    print('    ' + o)
    if label.startswith('A') or label.startswith('E'): print('    (stderr)' + err.split('\n')[0])

print('== 二:GOMEMLIMIT 的写法与默认值')
for val in ('512MiB', '1GiB', '1.5GiB', '100MB', '123456789', 'off'):
    o, err = run({'GOMEMLIMIT': val}, ['-live', '1', '-dur', '100ms'])
    fe = [l for l in err.split('\n') if l.startswith('fatal error')]
    print(f'  GOMEMLIMIT={val:10s} → {fe[0] if fe else err.split(chr(10))[0]}')
o, err = run({}, ['-live', '1', '-dur', '100ms'])
print(f'  不设置 → {err.split(chr(10))[0]}(math.MaxInt64 = 9223372036854775807,即没有限制)')

print('== 三:限制是软的:低于存活堆时程序没有被杀(对照 A 与 E)')
for label in [c[0] for c in CASES if c[0].startswith(('A', 'E'))]:
    print(f'  {label}:{res[label]}')
