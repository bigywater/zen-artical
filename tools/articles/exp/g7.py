import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g7')
SRC = r'''
package main

import (
	"fmt"
	"runtime"
	"sort"
	"strings"
	"testing"
	"time"
	"unsafe"
)

// 复制自 runtime/slice.go 的 nextslicecap(Go 1.27.1),用来和实测对比
func formula(newLen, oldCap int) int {
	newcap := oldCap
	doublecap := newcap + newcap
	if newLen > doublecap {
		return newLen
	}
	const threshold = 256
	if oldCap < threshold {
		return doublecap
	}
	for {
		newcap += (newcap + 3*threshold) >> 2
		if uint(newcap) >= uint(newLen) {
			break
		}
	}
	return newcap
}

type S24 struct{ a, b, c int }

func trace[T any](name string, n int, showAll bool) {
	var s []T
	old := 0
	var caps []string
	var diff []string
	for i := 0; i < n; i++ {
		s = append(s, *new(T))
		if cap(s) != old {
			f := formula(len(s), old)
			caps = append(caps, fmt.Sprint(cap(s)))
			if f != cap(s) {
				diff = append(diff, fmt.Sprintf("%d→%d(公式 %d)", old, cap(s), f))
			}
			old = cap(s)
		}
	}
	fmt.Printf("  %-8s 元素 %2d 字节,逐个 append %d 个,容量依次:%s\n", name, unsafe.Sizeof(*new(T)), n, strings.Join(caps, " "))
	if showAll {
		fmt.Printf("           其中与公式 nextslicecap 不同的(再向上取整到内存 size class):%s\n", strings.Join(diff, "、"))
	} else {
		fmt.Printf("           与公式不同的步骤 %d 个,例如:%s\n", len(diff), strings.Join(diff[:min(4, len(diff))], "、"))
	}
}

var sinkAny any
var sinkN int
var sinkSlice []int

func traceEsc[T any](name string, n int) {
	var s []T
	old := 0
	var caps []string
	for i := 0; i < n; i++ {
		s = append(s, *new(T))
		if cap(s) != old {
			caps = append(caps, fmt.Sprint(cap(s)))
			old = cap(s)
		}
	}
	sinkAny = s
	fmt.Printf("  %-8s 结果逃逸(赋给全局变量)时,容量依次:%s\n", name, strings.Join(caps, " "))
}

//go:noinline
func appendNoEsc(n int) int {
	var s []int
	for i := 0; i < n; i++ {
		s = append(s, i)
	}
	return len(s)
}

//go:noinline
func appendEsc(n int) []int {
	var s []int
	for i := 0; i < n; i++ {
		s = append(s, i)
	}
	return s
}

func main() {
	trace[int]("[]int", 2000, true)
	trace[byte]("[]byte", 600, false)
	trace[int32]("[]int32", 600, false)
	trace[string]("[]string", 600, false)
	trace[S24]("[]S24", 600, false)

	fmt.Println("== 二:第一次容量为什么是 4:append 的结果不逃逸时,编译器会用 32 字节的栈缓冲(ssagen/ssa.go);逃逸时从 1 开始")
	traceEsc[int]("[]int", 40)
	traceEsc[string]("[]string", 40)
	traceEsc[S24]("[]S24", 40)
	for _, n := range []int{1, 4, 5, 8, 9, 100} {
		fmt.Printf("  追加 %3d 个 int:结果不逃逸的函数 %.0f 次分配;结果逃逸(返回给调用者)的函数 %.0f 次分配\n", n, testing.AllocsPerRun(1000, func() { sinkN += appendNoEsc(n) }), testing.AllocsPerRun(1000, func() { sinkSlice = appendEsc(n) }))
	}
	fmt.Println("== 三:一次追加多个元素:需要的长度超过旧容量的 2 倍时,直接取需要的长度(再向上取整)")
	for _, c := range []struct {
		oldLen, oldCap, add int
	}{{0, 0, 1}, {0, 0, 5}, {0, 0, 3}, {4, 4, 1}, {4, 4, 4}, {4, 4, 5}, {4, 4, 9}, {4, 4, 20}, {300, 300, 1}, {300, 300, 400}} {
		s := make([]int, c.oldLen, c.oldCap)
		s = append(s, make([]int, c.add)...)
		fmt.Printf("  []int 旧 len=%d cap=%d,追加 %2d 个:新 cap = %d(公式未取整:%d)\n", c.oldLen, c.oldCap, c.add, cap(s), formula(c.oldLen+c.add, c.oldCap))
	}
	fmt.Println("== 四:从 nil 逐个 append 100 万个 int 与预分配容量的差别(5 轮取中位数)")
	const N = 1_000_000
	type res struct {
		ms         float64
		mallocs, b uint64
	}
	run := func(name string, f func() []int) {
		var rs []res
		for rep := 0; rep < 5; rep++ {
			runtime.GC()
			var m0, m1 runtime.MemStats
			runtime.ReadMemStats(&m0)
			t0 := time.Now()
			s := f()
			el := float64(time.Since(t0).Microseconds()) / 1000
			runtime.ReadMemStats(&m1)
			rs = append(rs, res{el, m1.Mallocs - m0.Mallocs, m1.TotalAlloc - m0.TotalAlloc})
			_ = s
		}
		sort.Slice(rs, func(i, j int) bool { return rs[i].ms < rs[j].ms })
		fmt.Printf("  %-34s 中位 %.2f ms(最小 %.2f / 最大 %.2f);Mallocs +%d;TotalAlloc +%.1f MiB\n", name, rs[2].ms, rs[0].ms, rs[4].ms, rs[2].mallocs, float64(rs[2].b)/(1<<20))
	}
	run("var s []int; 逐个 append", func() []int {
		var s []int
		for i := 0; i < N; i++ { s = append(s, i) }
		return s
	})
	run("make([]int, 0, N); 逐个 append", func() []int {
		s := make([]int, 0, N)
		for i := 0; i < N; i++ { s = append(s, i) }
		return s
	})
	run("make([]int, N); 按下标赋值", func() []int {
		s := make([]int, N)
		for i := 0; i < N; i++ { s[i] = i }
		return s
	})
	var s []int
	g := 0
	last := 0
	for i := 0; i < N; i++ {
		s = append(s, i)
		if cap(s) != last { g++; last = cap(s) }
	}
	fmt.Printf("  逐个 append 100 万个 int 一共扩容(换底层数组)%d 次,最终 cap = %d(比 N 多 %.1f%%)\n", g, cap(s), float64(cap(s)-N)*100/N)
}
'''
print('== 一:逐个 append 时容量怎么增长,和 runtime/slice.go 里 nextslicecap 的公式对照(Go 1.27.1,arm64)')
r = grun('ap1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
