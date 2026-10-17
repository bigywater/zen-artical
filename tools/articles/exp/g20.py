import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g20')
SRC = r'''
package main

import (
	"fmt"
	"iter"
	"runtime"
	"slices"
	"strings"
)

func Count(n int) iter.Seq[int] {
	return func(yield func(int) bool) {
		defer fmt.Println("    [迭代器] 清理(defer)")
		for i := 0; i < n; i++ {
			fmt.Printf("    [迭代器] 准备 yield(%d)\n", i)
			if !yield(i) {
				fmt.Printf("    [迭代器] yield(%d) 返回 false\n", i)
				return
			}
		}
		fmt.Println("    [迭代器] 自然结束")
	}
}

func merge(a, b iter.Seq[int]) []int {
	na, sa := iter.Pull(a)
	nb, sb := iter.Pull(b)
	defer sa()
	defer sb()
	va, oka := na()
	vb, okb := nb()
	var out []int
	for oka || okb {
		if oka && (!okb || va <= vb) { out = append(out, va); va, oka = na() } else { out = append(out, vb); vb, okb = nb() }
	}
	return out
}

func main() {
	next, stop := iter.Pull(Count(2))
	fmt.Println("  next 与 stop 的交互(迭代器每一步都会打印):")
	for i := 0; i < 4; i++ {
		v, ok := next()
		fmt.Printf("  第 %d 次 next() → (%d, %v)\n", i+1, v, ok)
	}
	stop()
	stop()
	fmt.Println("  stop() 连续调用两次:没有问题")

	next2, stop2 := iter.Pull(Count(5))
	v, ok := next2()
	fmt.Printf("  只取了一个值 (%d, %v) 就提前 stop():\n", v, ok)
	stop2()
	v, ok = next2()
	fmt.Printf("  stop 之后再 next() → (%d, %v)\n", v, ok)

	fmt.Printf("  用 Pull 合并两个有序序列:%v\n", merge(slices.Values([]int{1, 4, 9}), slices.Values([]int{2, 3, 10, 11})))

	fmt.Println("== 二:迭代器里 panic:会从 next() 的调用处抛出")
	func() {
		defer func() { fmt.Printf("  recover 收到:%v\n", recover()) }()
		n, s := iter.Pull(func(yield func(int) bool) { yield(1); panic("迭代器自己出错了") })
		defer s()
		n()
		n()
	}()

	fmt.Println("== 三:Pull 的底层是一个 goroutine(runtime.newcoro):不 stop、也不取完,就泄漏")
	before := runtime.NumGoroutine()
	var stops []func()
	for i := 0; i < 1000; i++ {
		n, s := iter.Pull(slices.Values([]int{1, 2, 3}))
		n()
		stops = append(stops, s)
	}
	fmt.Printf("  创建 1000 个 Pull 并各取 1 个值、都不 stop:NumGoroutine %d → %d\n", before, runtime.NumGoroutine())
	for _, s := range stops { s() }
	runtime.Gosched()
	fmt.Printf("  全部 stop() 之后:NumGoroutine = %d\n", runtime.NumGoroutine())
	var ms runtime.MemStats
	heap := func() float64 { runtime.GC(); runtime.ReadMemStats(&ms); return float64(ms.HeapAlloc) / (1 << 20) }
	h0 := heap()
	for i := 0; i < 10000; i++ {
		n, _ := iter.Pull(slices.Values([]int{1, 2, 3}))
		n()
	}
	h1 := heap()
	fmt.Printf("  再创建 10000 个 Pull(各取 1 个、不 stop、丢弃引用):GC 之后堆 %.2f → %.2f MiB;NumGoroutine = %d\n", h0, h1, runtime.NumGoroutine())
	_ = strings.Repeat
}
'''
print('== 一:Pull 的用法与语义:next 取下一个,stop 提前结束(Go 1.27.1)')
r = grun('pl1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 四:成本:对 1000 个 int 求和,range(推)与 Pull(拉),以及单次创建 Pull 的成本(7 轮取中位数)')
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
func SumRange(seq iter.Seq[int]) int { s := 0; for x := range seq { s += x }; return s }

//go:noinline
func SumPull(seq iter.Seq[int]) int {
	next, stop := iter.Pull(seq)
	defer stop()
	s := 0
	for {
		v, ok := next()
		if !ok { return s }
		s += v
	}
}

var sink int

func main() {
	xs := make([]int, 1000)
	for i := range xs { xs[i] = i }
	seq := slices.Values(xs)
	bench("for range seq(推式,1000 个元素)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumRange(seq) } })
	bench("iter.Pull + next()(拉式,1000 个元素)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumPull(seq) } })
	one := slices.Values([]int{1})
	bench("只创建并取 1 个元素的 Pull(创建 + 1 次 next + stop)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumPull(one) } })
	fmt.Printf("  AllocsPerRun:SumRange %.0f 次;SumPull(1000 个元素)%.0f 次\n", testing.AllocsPerRun(100, func() { sink += SumRange(seq) }), testing.AllocsPerRun(100, func() { sink += SumPull(seq) }))
	_ = sort.Ints
}
''' + GBENCH
rb = grun('pl2', {'main.go': B}); print(rb['out'] if rb['crc'] == 0 else rb['cout'])
print('== 五:源码里的线索(iter/iter.go 与 runtime/coro.go 摘录)')
for f, pat in [('iter/iter.go', 'newcoro'), ('iter/iter.go', 'coroswitch')]:
    o = subprocess.run(['grep', '-n', '-m', '2', pat, '/opt/homebrew/Cellar/go/1.27.1/libexec/src/' + f], capture_output=True, text=True).stdout.strip()
    for l in o.split('\n'): print('  ' + f + ':' + l)
o = subprocess.run(['sed', '-n', '11,22p', '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/coro.go'], capture_output=True, text=True).stdout.rstrip()
print('  runtime/coro.go 开头的注释:')
for l in o.split('\n'): print('    ' + l)
