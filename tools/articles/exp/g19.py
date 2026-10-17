import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g19')
SRC = r'''
package main

import (
	"fmt"
	"iter"
	"maps"
	"runtime"
	"slices"
	"strings"
)

func Count(n int) iter.Seq[int] {
	return func(yield func(int) bool) {
		defer fmt.Println("    [迭代器] 退出")
		for i := 0; i < n; i++ {
			if !yield(i) {
				fmt.Printf("    [迭代器] yield(%d) 返回了 false,停止\n", i)
				return
			}
		}
	}
}

func find(n, target int) (int, bool) {
	for v := range Count(n) {
		if v == target { return v * 10, true }
	}
	return 0, false
}

func frames() string {
	pc := make([]uintptr, 8)
	n := runtime.Callers(2, pc)
	fs := runtime.CallersFrames(pc[:n])
	var names []string
	for {
		f, more := fs.Next()
		names = append(names, f.Function)
		if !more { break }
	}
	return strings.Join(names, " ← ")
}

func main() {
	fmt.Println("  for v := range Count(3) 手写等价形式:Count(3)(func(v int) bool { ... return true })")
	for v := range Count(3) { fmt.Printf("    循环体 v = %d\n", v) }
	fmt.Println("  break 与 continue:")
	for v := range Count(5) {
		if v == 1 { continue }
		if v == 3 { break }
		fmt.Printf("    循环体 v = %d\n", v)
	}
	fmt.Println("  return 在循环体里:find(5, 2) 返回:")
	r, ok := find(5, 2)
	fmt.Printf("    %d %v\n", r, ok)
	fmt.Println("  defer 写在循环体里:要等到外层函数结束才执行")
	func() {
		for v := range Count(2) {
			defer fmt.Printf("    [defer] 来自循环体 v = %d\n", v)
		}
		fmt.Println("    循环结束,函数还没返回")
	}()

	fmt.Println("== 二:循环体里的调用栈:循环体是一个被迭代器调用的函数")
	for v := range Count(1) {
		_ = v
		fmt.Println("  ", frames())
	}

	fmt.Println("== 三:不守规矩的迭代器:yield 返回 false 之后继续调用,或循环结束后再调用")
	bad1 := func(yield func(int) bool) { yield(1); yield(2) }
	try := func(name string, f func()) {
		defer func() { fmt.Printf("  %s → panic:%v\n", name, recover()) }()
		f()
		fmt.Printf("  %s 正常结束\n", name)
	}
	try("break 之后迭代器继续 yield", func() { for v := range bad1 { _ = v; break } })
	var saved func(int) bool
	bad2 := func(yield func(int) bool) { saved = yield; yield(1) }
	try("循环结束后保存的 yield 再被调用", func() { for v := range bad2 { _ = v }; saved(2) })

	fmt.Println("== 四:标准库里的迭代器(Go 1.23+ 的 slices、maps,Go 1.24+ 的 strings)")
	xs := []string{"b", "c", "a"}
	m := map[string]int{"x": 1, "y": 2}
	fmt.Printf("  slices.Sorted(slices.Values(xs)) = %v;slices.Collect(maps.Keys(m)) 排序后 = %v\n", slices.Sorted(slices.Values(xs)), slices.Sorted(maps.Keys(m)))
	fmt.Printf("  slices.Collect(strings.SplitSeq(\"a,b,c\", \",\")) = %q\n", slices.Collect(strings.SplitSeq("a,b,c", ",")))
	var ls []string
	for l := range strings.Lines("one\ntwo\nthree") { ls = append(ls, strings.TrimRight(l, "\n")) }
	fmt.Printf("  strings.Lines 逐行 = %q\n", ls)
	for i, v := range slices.All([]string{"p", "q"}) { fmt.Printf("  slices.All → (%d, %q)\n", i, v) }
}
'''
print('== 一:range over func 的语义:循环体、break、continue、return、defer(Go 1.27.1)')
r = grun('rf1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 五:编译器怎么处理:循环体变成独立的函数(符号 main.main-range1),-m 输出与符号表')
rr = grun('rf2', {'main.go': SRC}, gcflags='-m')
ls = [l for l in rr['cout'].split('\n') if re.search(r'func literal|inlining call to Count|can inline Count|Count\.func|range', l)][:10]
for l in ls: print('  ' + l.replace('./main.go', 'main.go'))
rc, o = go(rr['d'], 'tool', 'nm', '-n', 'app')
syms = [l.split()[-1] for l in o.split('\n') if re.search(r' T main\.(main|find|Count)', l)]
print('  go tool nm 里 main 包的相关函数符号:')
for s_ in syms: print('    ' + s_)

print('== 六:性能:对 1000 个 int 求和,range-over-func 与切片循环(7 轮取中位数,迭代器所在函数 //go:noinline)')
B = r'''
package main

import (
	"fmt"
	"iter"
	"slices"
	"sort"
	"testing"
)

//go:noinline
func Values(xs []int) iter.Seq[int] {
	return func(yield func(int) bool) {
		for _, x := range xs { if !yield(x) { return } }
	}
}

func ValuesInl(xs []int) iter.Seq[int] {
	return func(yield func(int) bool) {
		for _, x := range xs { if !yield(x) { return } }
	}
}

func SumInl(xs []int) int { s := 0; for x := range ValuesInl(xs) { s += x }; return s }

//go:noinline
func SumSlice(xs []int) int { s := 0; for _, x := range xs { s += x }; return s }

//go:noinline
func SumSeq(seq iter.Seq[int]) int { s := 0; for x := range seq { s += x }; return s }

//go:noinline
func SumCallback(xs []int, f func(int)) { for _, x := range xs { f(x) } }

var sink int

func main() {
	xs := make([]int, 1000)
	for i := range xs { xs[i] = i }
	bench("for range 切片", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumSlice(xs) } })
	bench("for range Values(xs)(自写迭代器)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumSeq(Values(xs)) } })
	bench("for range slices.Values(xs)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumSeq(slices.Values(xs)) } })
	bench("迭代器与循环体都不加 //go:noinline", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumInl(xs) } })
	bench("回调函数 SumCallback(xs, f)", func(b *testing.B) { for i := 0; i < b.N; i++ { s := 0; SumCallback(xs, func(x int) { s += x }); sink += s } })
	fmt.Printf("  AllocsPerRun:SumSeq(Values(xs)) %.0f 次;SumInl(xs)(不加 noinline)%.0f 次;SumSlice %.0f 次\n", testing.AllocsPerRun(1000, func() { sink += SumSeq(Values(xs)) }), testing.AllocsPerRun(1000, func() { sink += SumInl(xs) }), testing.AllocsPerRun(1000, func() { sink += SumSlice(xs) }))
	_ = sort.Ints
}
''' + GBENCH
rb = grun('rf3', {'main.go': B}); print(rb['out'] if rb['crc'] == 0 else rb['cout'])
