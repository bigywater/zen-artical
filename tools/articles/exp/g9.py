import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g9')
SRC = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
	"unsafe"
)

var sink int

type Pair struct {
	Name string
	Pos  [2]int
}

func modify(a [3]int)     { a[0] = 100 }
func modifyPtr(a *[3]int) { a[0] = 100 }

//go:noinline
func sumVal(a [4096]int) int {
	s := 0
	for i := range a { s += a[i] }
	return s
}

//go:noinline
func sumPtr(a *[4096]int) int {
	s := 0
	for i := range a { s += a[i] }
	return s
}

//go:noinline
func sumSlice(a []int) int {
	s := 0
	for i := range a { s += a[i] }
	return s
}

func main() {
	a := [3]int{1, 2, 3}
	b := a
	b[0] = 99
	fmt.Printf("  a := [3]int{1,2,3}; b := a; b[0] = 99:a = %v,b = %v(赋值拷贝了整个数组)\n", a, b)
	a = [3]int{1, 2, 3}
	modify(a)
	fmt.Printf("  modify(a) 里写 a[0] = 100:调用者的 a = %v(传参拷贝了一份)\n", a)
	modifyPtr(&a)
	fmt.Printf("  modifyPtr(&a) 里写 a[0] = 100:调用者的 a = %v(传的是指针)\n", a)
	fmt.Printf("  unsafe.Sizeof:[3]int = %d,[0]int = %d,[4096]int = %d,Pair{string, [2]int} = %d\n", unsafe.Sizeof(a), unsafe.Sizeof([0]int{}), unsafe.Sizeof([4096]int{}), unsafe.Sizeof(Pair{}))
	p1 := Pair{"p", [2]int{1, 2}}
	p2 := p1
	p2.Pos[0] = 50
	fmt.Printf("  结构体里的数组也是值:p2 := p1; p2.Pos[0] = 50:p1.Pos = %v,p2.Pos = %v;p1 == p2?%v\n", p1.Pos, p2.Pos, p1 == p2)
	x := [...]int{5: 1, 2, 3: 7}
	fmt.Printf("  [...]int{5: 1, 2, 3: 7} = %v(len %d,下标键可以乱序,后面的元素接着前一个下标)\n", x, len(x))

	fmt.Println("== 二:range 数组会先拷贝整个数组;range 切片或数组指针则看得到循环中的修改")
	arr := [3]int{1, 2, 3}
	fmt.Print("  for i, v := range arr(循环里 arr[2] = 100):")
	for i, v := range arr {
		arr[2] = 100
		fmt.Printf(" [%d]=%d", i, v)
	}
	fmt.Printf(";循环后 arr = %v\n", arr)
	arr = [3]int{1, 2, 3}
	fmt.Print("  for i, v := range arr[:](循环里 arr[2] = 100):")
	for i, v := range arr[:] {
		arr[2] = 100
		fmt.Printf(" [%d]=%d", i, v)
	}
	fmt.Println()
	arr = [3]int{1, 2, 3}
	fmt.Print("  for i, v := range &arr(循环里 arr[2] = 100):")
	for i, v := range &arr {
		arr[2] = 100
		fmt.Printf(" [%d]=%d", i, v)
	}
	fmt.Println()
	arr = [3]int{1, 2, 3}
	fmt.Print("  for i := range arr(只要下标,不拷贝):")
	for i := range arr {
		arr[2] = 100
		fmt.Printf(" [%d]=%d", i, arr[i])
	}
	fmt.Println()

	fmt.Println("== 三:比较与映射的键:数组可以 ==,可以做 map 的键;长度不同就是不同的类型")
	k1, k2 := [2]int{1, 2}, [2]int{1, 2}
	m := map[[2]int]string{{1, 2}: "a", {3, 4}: "b"}
	fmt.Printf("  [2]int{1,2} == [2]int{1,2} → %v;map[[2]int]string 里查 {1,2} → %q,查 {9,9} → %q;%T 与 %T 是不同类型\n", k1 == k2, m[k1], m[[2]int{9, 9}], [2]int{}, [3]int{})

	fmt.Println("== 四:传大数组的成本:[4096]int(32 KiB)按值、按指针、按切片传给 //go:noinline 的求和函数,7 轮取中位数")
	var big [4096]int
	for i := range big { big[i] = i }
	bench("sumVal(big)    按值传 32 KiB", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumVal(big) } })
	bench("sumPtr(&big)   传指针", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumPtr(&big) } })
	bench("sumSlice(big[:]) 传切片", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += sumSlice(big[:]) } })
	_ = sort.Ints
}
''' + GBENCH
print('== 一:数组是值:赋值、传参、结构体里的数组都会拷贝(Go 1.27.1,arm64)')
r = grun('ar1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
CE = r'''
package main

func main() {
	a := [3]int{1, 2, 3}
	b := [4]int{1, 2, 3, 4}
	println(a == b)
	s1, s2 := []int{1}, []int{1}
	println(s1 == s2)
	_ = map[[]int]int{}
}
'''
rc = grun('ar2', {'main.go': CE})
print('== 五:编译器对不合法比较的报错(长度不同的数组、切片与切片、切片做 map 键)')
for l in rc['cout'].split('\n'):
    if l.startswith('./main.go'): print('  ' + l.replace('./main.go', 'main.go'))
