import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g35')
SRC = r'''
package main

import (
	"fmt"
	"math"
	"strings"
)

type T struct{ n int }
type I interface{ M() int }

func (t *T) M() int { return t.n }

func add(a, b int) int { return a + b }

func abs(x int) int {
	if x < 0 { return -x }
	return x
}

func sum(xs []int) int {
	s := 0
	for _, x := range xs { s += x }
	return s
}

func forWithBreak(n int) int {
	for i := 0; i < n; i++ {
		if i > 5 { break }
	}
	return n
}

func withClosure(n int) func() int { return func() int { return n } }

func withDefer() { defer fmt.Println("x") }

func withRecover() any { return recover() }

func withGo() { go add(1, 2) }

func withSelect(c chan int) int {
	select {
	case v := <-c:
		return v
	default:
		return 0
	}
}

func withSwitch(x int) int {
	switch x {
	case 1: return 10
	case 2: return 20
	case 3: return 30
	}
	return 0
}

func callsMethod(t *T) int { return t.M() }

func callsInterface(i I) int { return i.M() }

func callsFuncValue(f func(int) int) int { return f(1) }

func recursive(n int) int {
	if n <= 1 { return 1 }
	return n * recursive(n-1)
}

func panics(x int) int {
	if x < 0 { panic("neg") }
	return x
}

func usesStd(s string) bool { return strings.HasPrefix(s, "a") && math.Abs(-1) > 0 }

func big(x int) int {
	x += 1; x *= 2; x -= 3; x ^= 4; x |= 5; x &= 0xff; x += 6; x *= 7; x -= 8; x ^= 9
	x += 10; x *= 11; x -= 12; x ^= 13; x |= 14; x &= 0xffff; x += 15; x *= 16; x -= 17; x ^= 18
	return x
}

func caller() int {
	t := &T{1}
	return add(1, 2) + abs(-3) + callsMethod(t) + sum([]int{1, 2}) + panics(1) + withSwitch(2)
}

func main() { fmt.Println(caller(), big(1), recursive(5), usesStd("abc")) }
'''
print('== 一:每个函数能不能内联,以及代价(go build -gcflags=-m=2 的原样诊断;预算是 80;Go 1.27.1)')
r = grun('in1', {'main.go': SRC}, gcflags='-m=2')
rows = {}
for l in r['cout'].split('\n'):
    m = re.match(r'\./main\.go:(\d+):\d+: (can inline|cannot inline) (\S+?)(?: with cost (\d+) as:.*|: (.*))?$', l)
    if m: rows[m.group(3)] = (m.group(2), m.group(4), m.group(5))
order = ['add', 'abs', 'sum', 'forWithBreak', 'withClosure', 'withDefer', 'withRecover', 'withGo', 'withSelect', 'withSwitch', 'callsMethod', 'callsInterface', 'callsFuncValue', 'recursive', 'panics', 'usesStd', 'big', 'caller', 'main']
for n in order:
    if n in rows:
        k, cost, why = rows[n]
        print(f'  {n:16s} ' + (f'可以内联,代价 {cost}' if k == 'can inline' else f'不能内联:{why}'))
    else:
        print(f'  {n:16s} (没有诊断)')
print('  (方法 (*T).M:' + ' / '.join(f'{v[0]} {v[1] or ""}{v[2] or ""}' for k, v in rows.items() if k.endswith('M')) + ')')

print('== 二:调用点:caller 里哪些调用被内联了(-m 的 inlining call to)')
start = int(re.search(r'main\.go:(\d+):\d+: cannot inline caller', r['cout']).group(1))
calls = [re.search(r'inlining call to (\S+)', l).group(1) for l in r['cout'].split('\n') if 'inlining call to' in l and re.match(r'\./main\.go:(\d+)', l) and start <= int(re.match(r'\./main\.go:(\d+)', l).group(1)) < start + 5]
print('  caller 函数体(add、abs、callsMethod、sum、panics、withSwitch 六个调用)里被内联的调用:' + ', '.join(calls))
for l in r['cout'].split('\n'):
    if re.search(r'cannot inline caller|cannot inline main|function too complex', l) and ('caller' in l or 'main' in l): print('  ' + l.replace('./main.go', 'main.go')[:150])

print('== 三:预算 80 的边界:一个函数里连续做 k 次 x += i,最大还能内联的 k')
def can(k):
    body = '\n'.join(f'\tx += {i + 1}' for i in range(k))
    code = f'package main\n\nfunc f(x int) int {{\n{body}\n\treturn x\n}}\n\nfunc main() {{ println(f(1)) }}\n'
    rr = grun('inb', {'main.go': code}, gcflags='-m=2')
    m = re.search(r'can inline f with cost (\d+)', rr['cout'])
    m2 = re.search(r'cannot inline f: function too complex: cost (\d+) exceeds budget (\d+)', rr['cout'])
    return (True, int(m.group(1))) if m else (False, int(m2.group(1)) if m2 else None)
lo, hi = 1, 80
while hi - lo > 1:
    mid = (lo + hi) // 2
    if can(mid)[0]: lo = mid
    else: hi = mid
print(f'  最大的 k = {lo}:{can(lo)};k = {hi}:{can(hi)}')
for k in (1, 10, 20):
    print(f'  k = {k}:{can(k)}')
shutil.rmtree(GT / 'inb', ignore_errors=True)

print('== 四:内联对运行成本的影响(7 轮取中位数)与分配')
B = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
)

func addInl(a, b int) int { return a + b }

//go:noinline
func addNoInl(a, b int) int { return a + b }

type P struct{ x, y int }

func newPInl(x, y int) *P { return &P{x, y} }

//go:noinline
func newPNoInl(x, y int) *P { return &P{x, y} }

var sink int

func main() {
	bench("内联的 addInl(i, 1)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += addInl(i, 1) } })
	bench("//go:noinline 的 addNoInl(i, 1)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += addNoInl(i, 1) } })
	bench("内联的 newPInl(i, 1).x(指针不逃逸)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += newPInl(i, 1).x } })
	bench("//go:noinline 的 newPNoInl(i, 1).x(指针逃逸到堆)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += newPNoInl(i, 1).x } })
	fmt.Printf("  AllocsPerRun:newPInl %.0f 次;newPNoInl %.0f 次\n", testing.AllocsPerRun(1000, func() { sink += newPInl(1, 2).x }), testing.AllocsPerRun(1000, func() { sink += newPNoInl(1, 2).x }))
	_ = sort.Ints
}
''' + GBENCH
rb = grun('in4', {'main.go': B}, timeout=600); print(rb['out'] if rb['crc'] == 0 else rb['cout'])
print('  同一份代码加 -gcflags=-l(关闭内联):')
rb = grun('in4', {'main.go': B}, gcflags='-l', timeout=600); print(rb['out'] if rb['crc'] == 0 else rb['cout'])

print('== 五:标准库函数的内联(来自导出数据):')
STD = r'''
package main

import (
	"bytes"
	"math"
	"strings"
	"unicode/utf8"
)

func f(s string, b []byte) (int, bool, float64, int) {
	return strings.Index(s, "x"), strings.HasPrefix(s, "a") && bytes.Equal(b, b), math.Abs(-1.5), utf8.RuneLen('é')
}

func main() { println(f("abc", nil)) }
'''
rs = grun('in5', {'main.go': STD}, gcflags='-m')
for l in rs['cout'].split('\n'):
    if 'inlining call to' in l: print('  ' + re.sub(r'^\./main\.go:\d+:\d+: ', '', l))
