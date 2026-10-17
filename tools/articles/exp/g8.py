import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g8')
SRC = r'''
package main

import (
	"fmt"
	"slices"
	"unsafe"
)

func addr(s []int) uintptr { return uintptr(unsafe.Pointer(unsafe.SliceData(s))) }

func appendInside(s []int) { s = append(s, 9) }

func fill(s []int) { s[0] = -1 }

func main() {
	a := []int{1, 2, 3, 4, 5}
	b := a[1:3]
	fmt.Printf("  a = %v(len %d cap %d);b := a[1:3] = %v(len %d cap %d);b 的数据地址 - a 的数据地址 = %d 字节\n", a, len(a), cap(a), b, len(b), cap(b), addr(b)-addr(a))
	b[0] = 99
	fmt.Printf("  b[0] = 99 之后:a = %v(改到了 a)\n", a)
	b = append(b, 100)
	fmt.Printf("  b = append(b, 100)(容量够,原地写):b = %v,a = %v(a[3] 被悄悄改成 100);b 仍与 a 共用数组?%v\n", b, a, addr(b) == addr(a)+8)
	b = append(b, 200, 300, 400)
	fmt.Printf("  再追加 3 个(超过 cap %d,换了新数组):b = %v;共用数组?%v;a 仍是 %v\n", 4, b, addr(b) == addr(a)+8, a)

	fmt.Println("== 二:切断共享:三下标切片限制容量,copy / slices.Clone 真正拷贝")
	a = []int{1, 2, 3, 4, 5}
	c := a[1:3:3]
	c2 := append(c, 100)
	fmt.Printf("  c := a[1:3:3] = %v(len %d cap %d);c2 := append(c, 100) → c2 = %v,a 仍是 %v;c2 的数据地址 == c 的数据地址?%v\n", c, len(c), cap(c), c2, a, addr(c2) == addr(c))
	d := slices.Clone(a[1:3])
	d[0] = -7
	fmt.Printf("  d := slices.Clone(a[1:3]):d[0] = -7 之后 d = %v,a = %v;d 的 cap = %d\n", d, a, cap(d))
	e := make([]int, 2)
	n := copy(e, a[1:3])
	e[1] = -8
	fmt.Printf("  e := make([]int, 2); copy(e, a[1:3]) 拷贝了 %d 个:e[1] = -8 之后 e = %v,a = %v\n", n, e, a)

	fmt.Println("== 三:函数参数:切片头是按值传递的,元素是共享的")
	x := make([]int, 3, 10)
	for i := range x { x[i] = i + 1 }
	fill(x)
	fmt.Printf("  fill(x) 里写 s[0] = -1:调用者的 x = %v(元素被改)\n", x)
	appendInside(x)
	fmt.Printf("  appendInside(x) 里 s = append(s, 9)(cap 10,容量够):调用者的 x = %v(len 仍是 %d);但 x[:4] = %v(底层数组第 4 个位置已经被写成 9)\n", x, len(x), x[:4])
	y := make([]int, 3, 3)
	appendInside(y)
	fmt.Printf("  同样的调用,y 的 cap 只有 3(要换数组):y[:3] = %v,y 的 cap 仍为 %d,数组没有被写\n", y, cap(y))

	fmt.Println("== 四:经典错误:复用缓冲区,把子切片存起来")
	buf := make([]byte, 8)
	var saved, savedOK [][]byte
	for i, w := range []string{"alpha", "beta", "gamma"} {
		n := copy(buf, w)
		saved = append(saved, buf[:n])
		savedOK = append(savedOK, slices.Clone(buf[:n]))
		_ = i
	}
	fmt.Printf("  读了 alpha、beta、gamma 三个词,每次都读进同一个 buf:\n")
	for i := range saved {
		fmt.Printf("    saved[%d] = %q(直接存 buf[:n]);savedOK[%d] = %q(存 slices.Clone)\n", i, saved[i], i, savedOK[i])
	}
	fmt.Printf("  saved[0] 与 saved[2] 的数据地址相同?%v\n", unsafe.SliceData(saved[0]) == unsafe.SliceData(saved[2]))
}
'''
print('== 一:子切片共享底层数组;append 在容量够时原地写,不够时换新数组(Go 1.27.1,arm64)')
r = grun('al1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
