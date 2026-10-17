import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g36')
SRC = r'''
package main

import "fmt"

func rangeLoop(s []int) int {
	t := 0
	for i := range s { t += s[i] }
	return t
}

func rangeValue(s []int) int {
	t := 0
	for _, v := range s { t += v }
	return t
}

func lenLoop(s []int) int {
	t := 0
	for i := 0; i < len(s); i++ { t += s[i] }
	return t
}

func unknownN(s []int, n int) int {
	t := 0
	for i := 0; i < n; i++ { t += s[i] }
	return t
}

func hintBefore(s []int, n int) int {
	t := 0
	if n > 0 { _ = s[n-1] }
	for i := 0; i < n; i++ { t += s[i] }
	return t
}

func hintUnguarded(s []int, n int) int {
	_ = s[n-1]
	t := 0
	for i := 0; i < n; i++ { t += s[i] }
	return t
}

func clampN(s []int, n int) int {
	if n > len(s) { n = len(s) }
	t := 0
	for i := 0; i < n; i++ { t += s[i] }
	return t
}

func resliceFirst(s []int, n int) int {
	s = s[:n]
	t := 0
	for i := 0; i < len(s); i++ { t += s[i] }
	return t
}

func fourConst(s []int) int { return s[0] + s[1] + s[2] + s[3] }

func fourConstHint(s []int) int {
	_ = s[3]
	return s[0] + s[1] + s[2] + s[3]
}

func maskIndex(a *[8]int, i int) int { return a[i&7] }

func modIndex(a *[8]int, i int) int { return a[i%8] }

func uintIndex(s []int, i int) int {
	if uint(i) < uint(len(s)) { return s[i] }
	return 0
}

func twoIdx(s []int) int {
	t := 0
	for i := 0; i < len(s)-1; i++ { t += s[i] * s[i+1] }
	return t
}

func reverse(s []int) {
	for i, j := 0, len(s)-1; i < j; i, j = i+1, j-1 { s[i], s[j] = s[j], s[i] }
}

func backwards(s []int) int {
	t := 0
	for i := len(s) - 1; i >= 0; i-- { t += s[i] }
	return t
}

func sliceExpr(s []int, i, j int) []int { return s[i:j] }

func fromData(s []int, idx []int) int {
	t := 0
	for _, k := range idx { t += s[k] }
	return t
}

func main() {
	var a [8]int
	fmt.Println(hintUnguarded(nil, 0), clampN(nil, 0), resliceFirst(nil, 0), rangeLoop(nil), rangeValue(nil), lenLoop(nil), unknownN(nil, 0), hintBefore(nil, 0), fourConst([]int{1, 2, 3, 4}), fourConstHint([]int{1, 2, 3, 4}), maskIndex(&a, 3), modIndex(&a, 3), uintIndex(nil, 0), twoIdx(nil), backwards(nil), len(sliceExpr(nil, 0, 0)), fromData(nil, nil))
	reverse(nil)
}
'''
SRC = re.sub(r'(?m)^func (?!main)', '//go:noinline\nfunc ', SRC)  # 每个被测函数都不内联,免得内联后被调用点的常量消掉检查
SRC = re.sub(r'(?m)^func (?!main)', '//go:noinline\nfunc ', SRC)  # 每个被测函数都不内联,免得内联后被调用点的常量消掉检查
funcs = [(i + 1, re.match(r'func (\w+)', l).group(1)) for i, l in enumerate(SRC.split('\n')) if re.match(r'func (\w+)', l)]
print('== 一:每个函数的汇编里还剩几处边界检查的失败出口(CALL runtime.panicBounds,go build -gcflags=-S;Go 1.27.1,arm64)')
r2 = grun('bc2', {'main.go': SRC}, gcflags='-S')
for st, fn in funcs:
    if fn == 'main': continue
    ls = [l for l in asm_fn(r2['cout'], fn, ('runtime.panicBounds', 'runtime.panicIndex', 'runtime.panicSlice')) if 'CALL' in l]
    names = [f'{len(ls)} 处 CALL runtime.panicBounds'] if ls else []
    print(f'  {fn:14s} ' + (', '.join(names) if names else '(没有 panic 调用点)'))

print('== 二:边界检查的成本:对 1000 个 int 求和(7 轮取中位数);-gcflags=-B 关闭所有边界检查作为对照')
B = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
)

//go:noinline
func sumRange(s []int) int {
	t := 0
	for i := range s { t += s[i] }
	return t
}

//go:noinline
func sumUnknownN(s []int, n int) int {
	t := 0
	for i := 0; i < n; i++ { t += s[i] }
	return t
}

//go:noinline
func sumHint(s []int, n int) int {
	t := 0
	if n > 0 { _ = s[n-1] }
	for i := 0; i < n; i++ { t += s[i] }
	return t
}

//go:noinline
func sumIdx(s []int, idx []int) int {
	t := 0
	for _, k := range idx { t += s[k] }
	return t
}

var sink int

func main() {
	s := make([]int, 1000)
	idx := make([]int, 1000)
	for i := range s { s[i] = i; idx[i] = (i * 7) % 1000 }
	bench("range 遍历(没有检查)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumRange(s) } })
	bench("i < n,n 来自参数(每次迭代检查)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumUnknownN(s, 1000) } })
	bench("先 _ = s[n-1] 再循环", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumHint(s, 1000) } })
	bench("下标来自另一个切片(无法消除)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumIdx(s, idx) } })
	_ = fmt.Sprint
	_ = sort.Ints
}
''' + GBENCH
for label, fl in [('默认编译', None), ('-gcflags=-B(关闭边界检查)', '-B')]:
    rb = grun('bc3', {'main.go': B}, gcflags=fl, timeout=600)
    print(f'  {label}:')
    print('  ' + (rb['out'] if rb['crc'] == 0 else rb['cout']).replace('\n', '\n  '))
print('== 三:越界时的行为(默认编译,运行时 panic)')
PAN = 'package main\n\nfunc get(s []int, i int) int { return s[i] }\n\nfunc main() {\n\tdefer func() { println(recover().(error).Error()) }()\n\tprintln(get([]int{1, 2, 3}, 5))\n}\n'
rp = grun('bc4', {'main.go': PAN}); print('    ' + rp['out'].replace('\n', ' | '))
