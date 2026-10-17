import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g1')
SRC = r'''
package main

import (
	"fmt"
	"io"
)

type Point struct{ X, Y int }

//go:noinline
func byValue() int { p := Point{1, 2}; return p.X + p.Y }

//go:noinline
func returnPtr() *Point { p := Point{1, 2}; return &p }

//go:noinline
func toInterface() { p := Point{1, 2}; fmt.Fprintln(io.Discard, p) }

//go:noinline
func smallMake() int { s := make([]int, 10); s[0] = 1; return s[0] }

//go:noinline
func varMake(n int) int { s := make([]int, n); s[0] = 1; return s[0] }

//go:noinline
func closure() func() int { x := 0; return func() int { x++; return x } }

//go:noinline
func make64k() int { s := make([]int, 8000); s[0] = 1; return s[0] }

//go:noinline
func make65k() int { s := make([]int, 8200); s[0] = 1; return s[0] }

//go:noinline
func arr8M() int { var a [1 << 20]int; a[0] = 1; return a[0] }

func main() {
	fmt.Println(byValue(), returnPtr().X, smallMake(), varMake(10), closure()(), make64k(), make65k(), arr8M())
	toInterface()
}
'''
print('== 一:九种写法在 go build -gcflags=-m 下的逃逸结论(Go 1.27.1,每个函数都标了 //go:noinline,免得内联影响判断)')
print('  源码(省略 main):'); print('\n'.join('    ' + l for l in numbered('\n'.join(SRC.split('\n')[:40])).split('\n')))
r = grun('esc1', {'main.go': SRC}, gcflags='-m')
d = gdiag(r['cout'], SRC, keep=('escapes to heap', 'moved to heap', 'does not escape'))
print('  编译器诊断(只列 11–38 行的函数体,省略 main 里的):'); print('\n'.join(l for l in d.split('\n') if int(re.search(r'main\.go:(\d+)', l).group(1)) < 37))
print(f'  运行 rc={r["rc"]},输出:{r["out"]}')

print('== 二:真实分配次数:testing.AllocsPerRun(1000 次调用的平均 mallocs)')
EXTRA = r'''
//go:noinline
func ifaceInt(n int) { fmt.Fprintln(io.Discard, n) }

//go:noinline
func ifacePoint(n int) { fmt.Fprintln(io.Discard, Point{n, 2}) }

//go:noinline
func staticN() int { n := 10; s := make([]int, n); s[0] = 1; return s[0] }

//go:noinline
func staticBig() int { n := 1000; s := make([]int, n); s[0] = 1; return s[0] }
'''
MEAS = SRC.replace('import (\n\t"fmt"\n\t"io"\n)', 'import (\n\t"fmt"\n\t"io"\n\t"testing"\n)').split('func main() {')[0] + EXTRA + r'''
func main() {
	run := func(name string, f func()) { fmt.Printf("  %-34s %4.0f 次/调用\n", name, testing.AllocsPerRun(1000, f)) }
	run("byValue", func() { byValue() })
	run("returnPtr", func() { returnPtr() })
	run("toInterface(常量 Point{1,2})", func() { toInterface() })
	run("ifacePoint(n=1000) Point{n,2}", func() { ifacePoint(1000) })
	run("ifaceInt(n=7)", func() { ifaceInt(7) })
	run("ifaceInt(n=255)", func() { ifaceInt(255) })
	run("ifaceInt(n=256)", func() { ifaceInt(256) })
	run("ifaceInt(n=1000)", func() { ifaceInt(1000) })
	run("smallMake  make(10)", func() { smallMake() })
	run("staticN  n:=10; make(n)", func() { staticN() })
	run("staticBig  n:=1000; make(n)", func() { staticBig() })
	run("closure(返回闭包)", func() { closure() })
	run("make64k  make(8000)", func() { make64k() })
	run("make65k  make(8200)", func() { make65k() })
	run("arr8M   [1<<20]int", func() { arr8M() })
	for _, n := range []int{1, 2, 4, 5, 8, 16, 64, 1000, 8192, 8193} {
		n := n
		run(fmt.Sprintf("varMake n=%d(%d 字节)", n, n*8), func() { varMake(n) })
	}
}
'''
r = grun('esc2', {'main.go': MEAS}); print(r['out'] if r['crc'] == 0 else r['cout'])
r = grun('esc2b', {'main.go': MEAS}, gcflags='-d=variablemakethreshold=1024')
print('  同一份代码加 -gcflags=-d=variablemakethreshold=1024(把变长 make 的栈缓冲从 32 字节调到 1024 字节),只看 varMake:')
print('\n'.join(l for l in r['out'].split('\n') if 'varMake' in l))
r = grun('esc2c', {'main.go': MEAS}, gcflags='-N')
print('  同一份代码加 -gcflags=-N(关闭优化),只看 varMake 与 smallMake:')
print('\n'.join(l for l in r['out'].split('\n') if 'varMake n=4(' in l or 'varMake n=1(' in l or 'smallMake' in l or 'staticN' in l))

print('== 三:栈上放得下的大小上限:二分法反复编译,看 -m 什么时候开始说 moved to heap / escapes to heap')
def probe(tmpl, lo, hi, key):
    def esc(n):
        code = 'package main\n\n//go:noinline\nfunc f() byte {\n\t' + tmpl.replace('N', str(n)) + '\n}\n\nfunc main() { f() }\n'
        rr = grun('probe', {'main.go': code}, gcflags='-m'); return key in rr['cout']
    assert not esc(lo) and esc(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if esc(mid): hi = mid
        else: lo = mid
    return lo, hi
for label, tmpl, key in [('var a [N]byte(显式声明的局部数组)', 'var a [N]byte; a[0] = 1; return a[0]', 'moved to heap'),
                         ('make([]byte, N)(常量长度)', 's := make([]byte, N); s[0] = 1; return s[0]', 'escapes to heap'),
                         ('new([N]byte)', 'p := new([N]byte); p[0] = 1; return p[0]', 'escapes to heap'),
                         ('&[N]byte{}(取地址的复合字面量)', 'p := &[N]byte{}; p[0] = 1; return p[0]', 'escapes to heap')]:
    lo, hi = probe(tmpl, 1024, 4 * 1024 * 1024, key)
    print(f'  {label}:{lo} 字节仍在栈上,{hi} 字节被放到堆上(= {lo // 1024} KiB + {lo % 1024} 字节为界)')

print('== 四:-gcflags="-m -m" 的 flow 链:编译器为什么说它逃逸')
r = grun('esc3', {'main.go': SRC}, gcflags='-m -m')
L = r['cout'].split('\n')
def chain(prefix):
    out = []
    for l in L:
        if l.startswith(prefix) and ('flow:' in l or 'from ' in l or 'moved to heap' in l or 'escapes to heap in' in l): out.append('    ' + l.replace('./main.go', 'main.go'))
    return '\n'.join(out)
for what, pre in [('returnPtr(第 14 行 p)', './main.go:14:27'), ('toInterface(第 17 行 p)', './main.go:17:65'), ('closure(第 26 行 x)', './main.go:26:29'), ('make65k(第 32 行)', './main.go:32:31')]:
    print(f'  {what}:'); print(chain(pre))

print('== 五:逃逸不是变量的固有属性:同一个 newPoint,内联与不内联结论相反')
INL = r'''
package main

import (
	"fmt"
	"testing"
)

type Point struct{ X, Y int }

func newPoint() *Point { return &Point{1, 2} }

//go:noinline
func sum() int { p := newPoint(); return p.X + p.Y }

func main() {
	fmt.Printf("  sum() 每次调用的分配次数:%.0f\n", testing.AllocsPerRun(1000, func() { sum() }))
}
'''
for label, fl in [('默认(newPoint 被内联进 sum)', None), ('-gcflags=-l(关闭内联)', '-l')]:
    r = grun('inl', {'main.go': INL}, gcflags=('-m ' + fl) if fl else '-m')
    print(f'  {label}:')
    for l in gdiag(r['cout'], INL, keep=('inlining call to newPoint', 'escapes to heap', 'moved to heap', 'does not escape', 'can inline newPoint', 'cannot inline')).split('\n'):
        if int(re.search(r'main\.go:(\d+)', l).group(1)) < 15: print('  ' + l)
    print('  ' + r['out'] if r['crc'] == 0 else r['cout'])

print('== 六:逃逸的代价:同样 500 万次,值留在栈上与逃到堆上,运行时统计的差别')
GC = r'''
package main

import (
	"fmt"
	"runtime"
	"sort"
	"time"
)

type Point struct{ X, Y int }

//go:noinline
func byValue() int { p := Point{1, 2}; return p.X + p.Y }

//go:noinline
func returnPtr() *Point { p := Point{1, 2}; return &p }

var sink int

func main() {
	const N = 5_000_000
	for _, c := range []struct {
		name string
		f    func()
	}{{"byValue(栈)", func() { sink += byValue() }}, {"returnPtr(堆)", func() { sink += returnPtr().X }}} {
		var ts []float64
		var m0, m1 runtime.MemStats
		var gcs, mallocs, bytes uint64
		for rep := 0; rep < 5; rep++ {
			runtime.GC()
			runtime.ReadMemStats(&m0)
			t0 := time.Now()
			for i := 0; i < N; i++ { c.f() }
			ts = append(ts, float64(time.Since(t0).Microseconds())/1000)
			runtime.ReadMemStats(&m1)
			gcs, mallocs, bytes = uint64(m1.NumGC-m0.NumGC), m1.Mallocs-m0.Mallocs, m1.TotalAlloc-m0.TotalAlloc
		}
		sort.Float64s(ts)
		fmt.Printf("  %-14s 500 万次:耗时中位 %.1f ms(最小 %.1f / 最大 %.1f);Mallocs +%d,TotalAlloc +%d 字节,GC 次数 +%d\n", c.name, ts[2], ts[0], ts[4], mallocs, bytes, gcs)
	}
}
'''
r = grun('gc1', {'main.go': GC}); print(r['out'] if r['crc'] == 0 else r['cout'])
shutil.rmtree(GT / 'probe', ignore_errors=True)
