import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g38')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sort"
	"sync/atomic"
	"time"
)

type Node struct {
	next *Node
	val  [6]int
}

var sink *Node

// 一批会不断分配的工作:保留一部分,丢弃一部分
func churn(d time.Duration) {
	keep := make([]*Node, 0, 1<<16)
	t0 := time.Now()
	for time.Since(t0) < d {
		for i := 0; i < 1000; i++ {
			n := &Node{}
			n.val[0] = i
			if i%16 == 0 { keep = append(keep, n) }
			sink = n
		}
		if len(keep) > 1<<16-1000 { keep = keep[:0] }
	}
}

func median(xs []float64) float64 { sort.Float64s(xs); return xs[len(xs)/2] }

func main() {
	mode := os.Args[1]
	switch mode {
	case "trace":
		churn(1200 * time.Millisecond)
	case "store":
		const N = 2_000_000
		heap := make([]*Node, N)
		for i := range heap { heap[i] = &Node{} }
		for i := range heap { heap[i].next = heap[(i*7919)%N] }
		const OPS = 50_000_000
		run := func(label string, bg bool) {
			var stop atomic.Bool
			var cycles atomic.Int64
			done := make(chan struct{})
			if bg {
				go func() {
					for !stop.Load() { runtime.GC(); cycles.Add(1) }
					close(done)
				}()
				time.Sleep(50 * time.Millisecond)
			}
			var ptrNs, intNs []float64
			for rep := 0; rep < 5; rep++ {
				t0 := time.Now()
				for i := 0; i < OPS; i++ {
					a := heap[i&(N-1)%N]
					b := heap[(i*31+7)%N]
					a.next = b
				}
				ptrNs = append(ptrNs, float64(time.Since(t0).Nanoseconds())/OPS)
				t0 = time.Now()
				for i := 0; i < OPS; i++ {
					a := heap[i&(N-1)%N]
					_ = heap[(i*31+7)%N]
					a.val[0] = i
				}
				intNs = append(intNs, float64(time.Since(t0).Nanoseconds())/OPS)
			}
			if bg { stop.Store(true); <-done }
			fmt.Printf("  %-34s 指针写 a.next = b 中位 %.2f ns/次;整数写 a.val[0] = i 中位 %.2f ns/次", label, median(ptrNs), median(intNs))
			if bg { fmt.Printf(";这段时间后台 runtime.GC() 完成了 %d 轮", cycles.Load()) }
			fmt.Println()
		}
		run("GC 空闲(没有后台 GC)", false)
		run("后台不停地 runtime.GC()", true)
		runtime.KeepAlive(heap)
	}
}
'''
print('== 一:一次 GC 在 gctrace 里长什么样(GODEBUG=gctrace=1,同一个分配循环跑 1.2 s;Go 1.27.1)')
d = gdir('gc1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
e = dict(os.environ); e['GODEBUG'] = 'gctrace=1'
p = subprocess.run([str(d / 'app'), 'trace'], capture_output=True, text=True, env=e)
gl = [l for l in p.stderr.split('\n') if l.startswith('gc ')]
print(f'  共 {len(gl)} 次 GC;前 4 行:')
for l in gl[:4]: print('    ' + l)
m = re.match(r'gc (\d+) @([\d.]+)s (\d+)%: ([\d.]+)\+([\d.]+)\+([\d.]+) ms clock, ([\d.]+)\+([\d.]+)/([\d.]+)/([\d.]+)\+([\d.]+) ms cpu, (\d+)->(\d+)->(\d+) MB, (\d+) MB goal, (\d+) MB stacks, (\d+) MB globals, (\d+) P', gl[0])
if m:
    g = m.groups()
    print(f'  逐段解释第 1 行:@{g[1]}s 时开始;GC 占总 CPU 的 {g[2]}%;墙钟时间 三段 = {g[3]} + {g[4]} + {g[5]} ms(清扫终止 STW + 并发标记 + 标记终止 STW);CPU 时间 = {g[6]} + {g[7]}/{g[8]}/{g[9]} + {g[10]} ms(STW + 辅助/后台/空闲标记 + STW);堆 {g[11]}→{g[12]}→{g[13]} MB(GC 开始时 → 标记结束时 → 存活),目标 {g[14]} MB,{g[17]} 个 P')
st = [re.match(r'gc \d+ @[\d.]+s \d+%: ([\d.]+)\+([\d.]+)\+([\d.]+) ms clock', l) for l in gl]
st = [tuple(map(float, x.groups())) for x in st if x]
if st:
    print(f'  {len(st)} 次 GC 的两次 STW 耗时(ms):清扫终止最大 {max(x[0] for x in st):.3f}、标记终止最大 {max(x[2] for x in st):.3f};并发标记墙钟时间中位 {sorted(x[1] for x in st)[len(st) // 2]:.3f}')

print('== 二:运行时源码里对这三个阶段与写屏障的描述(runtime/mgc.go、runtime/mbarrier.go 原样摘录)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/'
def sed(f, a, b):
    o = subprocess.run(['sed', '-n', f'{a},{b}p', base + f], capture_output=True, text=True).stdout.rstrip()
    print(f'  {f}:{a}-{b}')
    for l in o.split('\n'): print('    ' + l)
sed('mgc.go', 8, 12)
sed('mgc.go', 25, 27)
sed('mgc.go', 36, 46)
sed('mbarrier.go', 24, 34)

print('== 三:写屏障在汇编里:给堆对象的指针字段赋值,与给整数字段赋值的对照(go build -gcflags=-S)')
ASM = r'''
package main

type N struct {
	next *N
	v    int
}

//go:noinline
func storePtr(a, b *N) { a.next = b }

//go:noinline
func storeInt(a *N, x int) { a.v = x }

func main() {
	a, b := &N{}, &N{}
	storePtr(a, b)
	storeInt(a, 1)
	println(a.v)
}
'''
r = grun('gc2', {'main.go': ASM}, gcflags='-S')
for fn in ('storePtr', 'storeInt'):
    ls = asm_fn(r['cout'], fn, ('writeBarrier', 'gcWriteBarrier', 'STP', 'MOVD'))
    print(f'  main.{fn} 的汇编(与写屏障有关的指令):')
    for l in ls[:9]: print('    ' + l)
print('  storePtr 里对 runtime.writeBarrier 标志的检查与 runtime.gcWriteBarrier 调用的个数:' + str(len([l for l in asm_fn(r['cout'], 'storePtr', ('writeBarrier', 'gcWriteBarrier')) if 'CALL' in l or 'writeBarrier(SB)' in l])))

print('== 四:写屏障的代价:一个有 200 万个节点的存活堆,GC 空闲与后台不停做 GC 时,指针写 vs 整数写(5 轮取中位数)')
p = subprocess.run([str(d / 'app'), 'store'], capture_output=True, text=True, timeout=900)
print(p.stdout.rstrip() or p.stderr[:300])

print('== 五:Go 1.27.1 默认的 GC 实现(goexperiment.greenteagc)与关掉它之后,同一个负载的 gctrace 对比')
print('  go env GOEXPERIMENT = ' + go(d, 'env', 'GOEXPERIMENT')[1])
rc, o = go(d, 'list', '-f', '{{context.ToolTags}}')
print('  go list 的 ToolTags 里与 GC 有关的:' + ' '.join(t for t in o.strip('[]').split() if 'gc' in t))
rc, o = go(d, 'build', '-o', 'app_nogt', env=dict(GOEXPERIMENT='nogreenteagc')); assert rc == 0, o
def summarize(binp):
    e2 = dict(os.environ); e2['GODEBUG'] = 'gctrace=1'
    pp = subprocess.run([binp, 'trace'], capture_output=True, text=True, env=e2)
    lines = [l for l in pp.stderr.split('\n') if l.startswith('gc ')]
    mk = [re.match(r'gc \d+ @[\d.]+s \d+%: ([\d.]+)\+([\d.]+)\+([\d.]+) ms clock, ([\d.]+)\+([\d.]+)/([\d.]+)/([\d.]+)\+([\d.]+) ms cpu', l) for l in lines]
    mk = [tuple(map(float, x.groups())) for x in mk if x]
    cpu = sum(x[3] + x[4] + x[5] + x[6] + x[7] for x in mk)
    return len(lines), cpu, max(x[0] + x[2] for x in mk) if mk else 0
for label, binp in [('默认(greenteagc 开)', str(d / 'app')), ('GOEXPERIMENT=nogreenteagc', str(d / 'app_nogt'))]:
    rows = [summarize(binp) for _ in range(3)]
    print(f'  {label}:3 次运行的 GC 次数 {[r[0] for r in rows]};每次运行 GC 的 CPU 时间合计(ms){[round(r[1], 1) for r in rows]};两次 STW 之和的最大值(ms){[round(r[2], 3) for r in rows]}')
