import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g94')
FILES = {
'b.go': '''
package lab

import "math/bits"

//go:noinline
func Slow(x uint64) int { n := 0; for i := 0; i < 64; i++ { if x&(1<<uint(i)) != 0 { n++ } }; return n }

// 可以被内联的小函数
func Pop(x uint64) int { return bits.OnesCount64(x) }

func Mul(a, b int) int { return a * b }
''',
'b_test.go': '''
package lab

import (
	"sort"
	"testing"
)

var sinkI int

func BenchmarkPop_NoSink(b *testing.B) {
	for i := 0; i < b.N; i++ {
		Pop(uint64(i)) // 结果没有被使用,函数又能内联
	}
}

func BenchmarkPop_Sink(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkI = Pop(uint64(i))
	}
}

func BenchmarkPop_Loop(b *testing.B) {
	for i := 0; b.Loop(); i++ {
		Pop(uint64(i)) // 同样没有使用结果,但用 b.Loop
	}
}

func BenchmarkMul_ConstArgs(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkI = Mul(123, 456) // 参数是常量,整个调用被折叠成常量
	}
}

func BenchmarkMul_VarArgs(b *testing.B) {
	x, y := 123, 456
	for i := 0; i < b.N; i++ {
		sinkI = Mul(x+i, y)
	}
}

func BenchmarkMul_ConstArgsLoop(b *testing.B) {
	for b.Loop() {
		Mul(123, 456)
	}
}

func BenchmarkSlow_NoSink(b *testing.B) {
	for i := 0; i < b.N; i++ {
		Slow(uint64(i)) // 标了 noinline,调用不会被消除
	}
}

func mk() []int {
	a := make([]int, 10000)
	for i := range a { a[i] = (i * 7919) % 10007 }
	return a
}

func BenchmarkSort_SameSlice(b *testing.B) {
	a := mk()
	for i := 0; i < b.N; i++ {
		sort.Ints(a) // 第一次之后排的都是已经排好的数据
	}
}

func BenchmarkSort_FreshCopy(b *testing.B) {
	orig := mk()
	a := make([]int, len(orig))
	for i := 0; i < b.N; i++ {
		b.StopTimer()
		copy(a, orig)
		b.StartTimer()
		sort.Ints(a)
	}
}

func BenchmarkSort_FreshCopyNoStop(b *testing.B) {
	orig := mk()
	a := make([]int, len(orig))
	for i := 0; i < b.N; i++ {
		copy(a, orig)
		sort.Ints(a)
	}
}
''',
}
d = gdir('bp1'); write(d, FILES); mod(d)
def bench(pat, count=1, benchtime='200ms'):
    rc, o = go(d, 'test', '-run', '^$', '-bench', pat, '-benchtime', benchtime, '-count', str(count), '-benchmem', timeout=300)
    rows = []
    for l in o.split('\n'):
        m = re.match(r'(Benchmark\S+?)(-\d+)?\s+(\d+)\s+([\d.]+) ns/op\s+(\d+) B/op\s+(\d+) allocs/op', l)
        if m: rows.append((m.group(1), int(m.group(3)), float(m.group(4)), int(m.group(5)), int(m.group(6))))
    return rc, o, rows
print('== 一:结果没被使用时,编译器能把整个调用删掉(Go 1.27.1,arm64 macOS;go test -bench,-benchtime=200ms)')
rc, o, rows = bench('Pop_|Slow_NoSink')
for n, it, ns, b_, a in rows: print(f'  {n:24s} {ns:9.3f} ns/op  {b_} B/op  {a} allocs/op(循环了 {it} 次)')
print('== 二:参数是常量,函数又能内联时,结果被折叠成常量')
rc, o, rows = bench('Mul_')
for n, it, ns, b_, a in rows: print(f'  {n:24s} {ns:9.3f} ns/op')
print('== 三:同一份数据反复排序,测的是“排好的数据”')
rc, o, rows = bench('Sort_', benchtime='300ms')
for n, it, ns, b_, a in rows: print(f'  {n:28s} {ns:12.0f} ns/op')
print('== 四:同一个基准重复运行的波动(BenchmarkSort_FreshCopyNoStop,-count=10)')
rc, o, rows = bench('Sort_FreshCopyNoStop', count=10, benchtime='200ms')
xs = [r[2] for r in rows]
print(f'  10 次的 ns/op:' + ' '.join(f'{x:.0f}' for x in xs))
print(f'  最小 {min(xs):.0f} / 中位 {statistics.median(xs):.0f} / 最大 {max(xs):.0f},最大/最小 = {max(xs)/min(xs):.2f}')
print('== 五:汇编里看循环体(go test -c 后 go tool objdump BenchmarkPop_NoSink)')
rc, o = go(d, 'test', '-c', '-o', 'lab.test'); assert rc == 0, o
r = subprocess.run([GO, 'tool', 'objdump', '-s', r'BenchmarkPop_NoSink$', str(d / 'lab.test')], capture_output=True, text=True, env=genv())
lines = [re.sub(r'\s+', ' ', l.split('\t', 1)[-1] if False else l).strip() for l in r.stdout.split('\n') if l.strip() and not l.startswith('TEXT')]
body = [re.sub(r'^\S+\s+\S+\s+', '', l) for l in lines]
print(f'  BenchmarkPop_NoSink 的机器指令共 {len(body)} 条,其中调用 Pop 或 OnesCount64 的 CALL 指令 {len([l for l in body if "CALL" in l and ("Pop" in l or "OnesCount" in l)])} 条;含 CNT/popcount 类指令 {len([l for l in body if "VCNT" in l or "CNT" in l])} 条')
print('  前 12 条:' + ' ; '.join(body[:12]))
r2 = subprocess.run([GO, 'tool', 'objdump', '-s', r'BenchmarkPop_Sink$', str(d / 'lab.test')], capture_output=True, text=True, env=genv())
body2 = [re.sub(r'^\S+\s+\S+\s+', '', l) for l in r2.stdout.split('\n') if l.strip() and not l.startswith('TEXT')]
print(f'  BenchmarkPop_Sink 的机器指令共 {len(body2)} 条;含 VCNT 的 {len([l for l in body2 if "VCNT" in l])} 条')
print('== 六:testing.B.Loop 的文档')
r, o = go(d, 'doc', 'testing.B.Loop')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('Within the body of a'))
print('  ' + ' '.join(x for x in ls[i:i + 5] if x))
