import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g4')
HEAD = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
)

type A struct{ n int }
type B struct{ n int }
type C struct{ n int }
type D struct{ n int }
type E struct{ n int }
type F struct{ n int }
type G struct{ n int }
type H struct{ n int }

func (A) M() int { return 1 }
func (B) M() int { return 2 }
func (C) M() int { return 3 }
func (D) M() int { return 4 }
func (E) M() int { return 5 }
func (F) M() int { return 6 }
func (G) M() int { return 7 }
func (H) M() int { return 8 }

type Mer interface{ M() int }
type Other interface{ Z() int }

var sink int
'''
SRC = HEAD + r'''
//go:noinline
func baseline(x any) int { return 1 }

//go:noinline
func assertConcrete(x any) int { return x.(A).n }

//go:noinline
func assertConcreteOK(x any) int {
	if v, ok := x.(A); ok {
		return v.n
	}
	return -1
}

//go:noinline
func assertIface(x any) int { return x.(Mer).M() }

//go:noinline
func assertIfaceOK(x any) int {
	if m, ok := x.(Mer); ok {
		return m.M()
	}
	return -1
}

//go:noinline
func assertIfaceMiss(x any) int {
	if m, ok := x.(Other); ok {
		return m.Z()
	}
	return -1
}

//go:noinline
func switch2(x any) int {
	switch v := x.(type) {
	case A:
		return v.n
	case B:
		return v.n + 1
	}
	return -1
}

//go:noinline
func switch8(x any) int {
	switch v := x.(type) {
	case A:
		return v.n
	case B:
		return v.n + 1
	case C:
		return v.n + 2
	case D:
		return v.n + 3
	case E:
		return v.n + 4
	case F:
		return v.n + 5
	case G:
		return v.n + 6
	case H:
		return v.n + 7
	}
	return -1
}

//go:noinline
func switchIface(x any) int {
	switch v := x.(type) {
	case Other:
		return v.Z()
	case Mer:
		return v.M()
	}
	return -1
}

func main() {
	a, h := any(A{5}), any(H{5})
	bench("基线:调用 //go:noinline 空函数(不断言)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += baseline(a) } })
	bench("x.(A) 命中", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += assertConcrete(a) } })
	bench("v, ok := x.(A) 命中", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += assertConcreteOK(a) } })
	bench("v, ok := x.(A) 未命中(装的是 H)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += assertConcreteOK(h) } })
	bench("x.(Mer) 命中(接口类型断言)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += assertIface(a) } })
	bench("m, ok := x.(Mer) 命中", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += assertIfaceOK(a) } })
	bench("m, ok := x.(Other) 未命中", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += assertIfaceMiss(a) } })
	bench("switch 2 个具体类型:命中第 1 个", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += switch2(a) } })
	bench("switch 8 个具体类型:命中第 1 个(A)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += switch8(a) } })
	bench("switch 8 个具体类型:命中第 8 个(H)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += switch8(h) } })
	bench("switch 2 个接口类型:命中第 2 个", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += switchIface(a) } })
	fmt.Println("  AllocsPerRun:断言命中", testing.AllocsPerRun(1000, func() { assertIfaceOK(a) }), "次,未命中", testing.AllocsPerRun(1000, func() { assertIfaceMiss(a) }), "次")
}
''' + GBENCH
print('== 一:断言与类型开关的耗时(每个函数都 //go:noinline,装在 any 里的值固定,7 轮取中位数;Go 1.27.1 arm64)')
r = grun('ta1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 二:汇编里的差别:具体类型断言只是比较类型字,接口类型断言要调用运行时(go build -gcflags=-S)')
r2 = grun('ta2', {'main.go': SRC}, gcflags='-S')
for fn in ('assertConcrete', 'assertConcreteOK', 'assertIfaceOK', 'switch2', 'switchIface'):
    ls = asm_fn(r2['cout'], fn, ('type:', 'CALL', 'CMP', 'CBNZ', 'CBZ', 'go:itab'))
    print(f'  main.{fn}:')
    for l in ls[:10]: print('    ' + l)

print('== 三:类型开关里 case 的顺序与数量:8 个具体类型,命中每一个的耗时(同一份 switch8)')
SRC3 = SRC.replace('func main() {', 'func main2() {') + r'''
func main() {
	vals := []any{A{}, B{}, C{}, D{}, E{}, F{}, G{}, H{}}
	for i, v := range vals {
		v := v
		bench(fmt.Sprintf("switch8 命中第 %d 个", i+1), func(b *testing.B) { for j := 0; j < b.N; j++ { sink += switch8(v) } })
	}
	bench("switch8 全部未命中(装 int)", func(b *testing.B) { var x any = 7; for j := 0; j < b.N; j++ { sink += switch8(x) } })
}
'''
r3 = grun('ta3', {'main.go': SRC3})
out = r3['out'] if r3['crc'] == 0 else r3['cout']
print('\n'.join(l for l in out.split('\n') if 'switch8' in l and '8 个具体类型' not in l))
