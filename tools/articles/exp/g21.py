import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g21')
def mk_defers(n):
    return '\n'.join('\tdefer inc()' for _ in range(n))
SRC = r'''
package main

import (
	"fmt"
	"sort"
	"sync"
	"testing"
)

var cnt int
var mu sync.Mutex

//go:noinline
func inc() { cnt++ }

//go:noinline
func noDefer() { inc() }

//go:noinline
func oneDefer() {
	defer inc()
}

//go:noinline
func lockDefer() {
	mu.Lock()
	defer mu.Unlock()
	cnt++
}

//go:noinline
func lockDirect() {
	mu.Lock()
	cnt++
	mu.Unlock()
}

//go:noinline
func eightDefers() {
''' + mk_defers(8) + r'''
}

//go:noinline
func nineDefers() {
''' + mk_defers(9) + r'''
}

//go:noinline
func loopDefer() {
	for i := 0; i < 1; i++ {
		defer inc()
	}
}

//go:noinline
func manyReturns(a int) int {
	defer inc()
	defer inc()
	defer inc()
	defer inc()
	if a == 0 { return 0 }
	if a == 1 { return 1 }
	if a == 2 { return 2 }
	return 3
}

//go:noinline
func withRecover() (r int) {
	defer func() { if e := recover(); e != nil { r = 1 } }()
	return 0
}

//go:noinline
func withPanic() (r int) {
	defer func() { if e := recover(); e != nil { r = 1 } }()
	panic("x")
}

''' + GBENCH + r'''
func main() {
	bench("noDefer:直接调用 inc()", func(b *testing.B) { for i := 0; i < b.N; i++ { noDefer() } })
	bench("oneDefer:defer inc()", func(b *testing.B) { for i := 0; i < b.N; i++ { oneDefer() } })
	bench("lockDirect:Lock + 直接 Unlock", func(b *testing.B) { for i := 0; i < b.N; i++ { lockDirect() } })
	bench("lockDefer:Lock + defer Unlock", func(b *testing.B) { for i := 0; i < b.N; i++ { lockDefer() } })
	bench("eightDefers:8 个 defer(最多可以内联展开的数量)", func(b *testing.B) { for i := 0; i < b.N; i++ { eightDefers() } })
	bench("nineDefers:9 个 defer", func(b *testing.B) { for i := 0; i < b.N; i++ { nineDefers() } })
	bench("loopDefer:循环里的 defer(循环 1 次)", func(b *testing.B) { for i := 0; i < b.N; i++ { loopDefer() } })
	bench("manyReturns:4 个 defer × 4 个 return", func(b *testing.B) { for i := 0; i < b.N; i++ { manyReturns(i & 3) } })
	bench("withRecover:正常返回(defer 里有 recover)", func(b *testing.B) { for i := 0; i < b.N; i++ { withRecover() } })
	bench("withPanic:panic 后被 recover 接住", func(b *testing.B) { for i := 0; i < b.N; i++ { withPanic() } })
	fmt.Printf("  AllocsPerRun:oneDefer %.0f、eightDefers %.0f、nineDefers %.0f、loopDefer %.0f、manyReturns %.0f、withPanic %.0f\n",
		testing.AllocsPerRun(1000, oneDefer), testing.AllocsPerRun(1000, eightDefers), testing.AllocsPerRun(1000, nineDefers), testing.AllocsPerRun(1000, loopDefer), testing.AllocsPerRun(1000, func() { manyReturns(1) }), testing.AllocsPerRun(1000, func() { withPanic() }))
	_ = sort.Ints
}
'''
print('== 一:不同写法的 defer 成本(Go 1.27.1,arm64;每个函数 //go:noinline,7 轮取中位数)')
r = grun('df1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 二:编译器怎么分类:-gcflags=-d=defer=1 的诊断,与汇编里调用的运行时函数')
r2 = grun('df2', {'main.go': SRC}, gcflags='-d=defer=1 -S')
dl = [(int(m.group(1)), m.group(2)) for m in (re.match(r'^\./main\.go:(\d+):\d+: (.*defer)$', l) for l in r2['cout'].split('\n')) if m]
starts = [(i + 1, re.match(r'func (\w+)', l).group(1)) for i, l in enumerate(SRC.split('\n')) if re.match(r'func (\w+)', l)]
agg = {}
for ln, kind in dl:
    fn = [n for st, n in starts if st <= ln][-1]
    agg.setdefault(fn, {}).setdefault(kind, 0)
    agg[fn][kind] += 1
for fn, d in agg.items(): print(f'  {fn:12s} ' + '、'.join(f'{k} × {v}' for k, v in d.items()))
print('  各函数汇编里的 defer 相关调用(去重):')
for fn in ('noDefer', 'oneDefer', 'lockDefer', 'eightDefers', 'nineDefers', 'loopDefer', 'manyReturns', 'withPanic'):
    ls = asm_fn(r2['cout'], fn, ('deferproc', 'deferreturn', 'deferrangefunc'))
    names = sorted({re.search(r'(runtime\.\w+)', l).group(1) for l in ls if re.search(r'runtime\.\w+', l)})
    print(f'    {fn:12s} {", ".join(names) if names else "(没有调用 runtime 的 defer 函数)"}')

print('== 三:关闭 open-coded defer(-gcflags=-d=noopendefer=1)后,同一份代码的成本')
BM = SRC.split('func main() {')[0] + r'''
func main() {
	bench("noDefer", func(b *testing.B) { for i := 0; i < b.N; i++ { noDefer() } })
	bench("oneDefer", func(b *testing.B) { for i := 0; i < b.N; i++ { oneDefer() } })
	bench("lockDefer", func(b *testing.B) { for i := 0; i < b.N; i++ { lockDefer() } })
	bench("eightDefers", func(b *testing.B) { for i := 0; i < b.N; i++ { eightDefers() } })
	bench("loopDefer", func(b *testing.B) { for i := 0; i < b.N; i++ { loopDefer() } })
	_ = fmt.Sprint
	_ = sort.Ints
}
'''
for label, fl in [('默认', None), ('-gcflags=-d=noopendefer=1(关闭 open-coded defer)', '-d=noopendefer=1')]:
    rr = grun('df3', {'main.go': BM}, gcflags=fl)
    print(f'  {label}:')
    print('  ' + (rr['out'] if rr['crc'] == 0 else rr['cout']).replace('\n', '\n  '))
print('== 四:源码里 open-coded defer 的限制(walk/stmt.go 与 ssagen/ssa.go 中的条件,原样摘录)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/cmd/compile/internal/'
def excerpt(f, pat, before, after):
    n = int(subprocess.run(['grep', '-n', '-m', '1', pat, base + f], capture_output=True, text=True).stdout.split(':')[0])
    o = subprocess.run(['sed', '-n', f'{n - before},{n + after}p', base + f], capture_output=True, text=True).stdout.rstrip()
    print(f'  {f}:{n - before}-{n + after}')
    for l in o.split('\n'): print('    ' + l)
excerpt('walk/stmt.go', 'NumDefers > maxOpenDefers', 0, 10)
excerpt('ssagen/ssa.go', 's.curfn.NumReturns\\*s.curfn.NumDefers > 15', 1, 7)
