import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g18')
def ce(name, code, n=3):
    r = grun(name, {'main.go': code})
    ls = [re.sub(r'^\./', '', l) for l in r['cout'].split('\n') if re.match(r'^(\./)?main\.go:\d+', l)]
    return r, ls[:n]
def show_ce(title, code, n=3, w=None):
    r, ls = ce('ge', code, n)
    print(f'  {title}:' + ('' if ls else ' 编译通过,运行输出:' + (r['out'].replace(chr(10), ' | ') if r['crc'] == 0 else '')))
    for l in ls: print('    ' + l)

print('== 一:comparable:哪些类型可以做实参,以及接口类型带来的运行时 panic(Go 1.27.1)')
BASE = '''package main

import "fmt"

func Index[T comparable](xs []T, x T) int {
	for i, v := range xs { if v == x { return i } }
	return -1
}

type P struct{ A, B int }
'''
show_ce('Index 用于 int / string / 结构体 / 数组 / 指针', BASE + '''
func main() {
	p := &P{}
	fmt.Println(Index([]int{1, 2, 3}, 3), Index([]string{"a", "b"}, "b"), Index([]P{{1, 2}, {3, 4}}, P{3, 4}), Index([][2]int{{1, 2}}, [2]int{1, 2}), Index([]*P{p}, p))
}
''')
show_ce('Index 用于 []int 的切片(切片不可比较)', BASE + '''
func main() { fmt.Println(Index([][]int{{1}}, []int{1})) }
''', 2)
show_ce('Index 用于 map[string]int', BASE + '''
func main() { fmt.Println(Index([]map[string]int{{}}, map[string]int{})) }
''', 2)
show_ce('Index 用于 func()', BASE + '''
func main() { fmt.Println(Index([]func(){}, func() {})) }
''', 2)
show_ce('含切片字段的结构体', BASE + '''
type Bad struct{ S []int }
func main() { fmt.Println(Index([]Bad{}, Bad{})) }
''', 2)
r = grun('ge2', {'main.go': BASE + '''
func main() {
	defer func() { fmt.Println("  接口类型实参 any:Index([]any{[]int{1}}, []int{1}) 运行时 panic:", recover()) }()
	fmt.Println(Index([]any{1, "x"}, "x"), "(any 作为实参:编译通过,比较 1 与 \\"x\\" 没问题)")
	fmt.Println(Index([]any{[]int{1}}, any([]int{1})))
}
'''})
print('  ' + (r['out'] if r['crc'] == 0 else r['cout']).replace('\n', '\n  '))

print('== 二:联合类型与 ~:自定义类型要不要加波浪号')
U = '''package main

import "fmt"

type MyInt int

type NumNoTilde interface{ int | float64 }
type NumTilde interface{ ~int | ~float64 }

func SumA[T NumNoTilde](xs []T) (s T) { for _, x := range xs { s += x }; return }
func SumB[T NumTilde](xs []T) (s T)   { for _, x := range xs { s += x }; return }
'''
show_ce('SumA[MyInt](约束没有 ~)', U + 'func main() { fmt.Println(SumA([]MyInt{1, 2})) }\n', 2)
show_ce('SumB[MyInt](约束有 ~int)', U + 'func main() { fmt.Println(SumB([]MyInt{1, 2}), SumB([]float64{1.5})) }\n', 2)

print('== 三:约束决定能用哪些操作符')
O = '''package main

import ("cmp"; "fmt")

var _ = cmp.Compare[int]
var _ = fmt.Sprint

func MaxAny[T any](a, b T) T { if a > b { return a }; return b }
'''
show_ce('T any 上用 >', O + 'func main() { fmt.Println(MaxAny(1, 2)) }\n', 2)
show_ce('T comparable 上用 <', '''package main

func Less[T comparable](a, b T) bool { return a < b }

func main() { _ = Less(1, 2) }
''', 2)
show_ce('cmp.Ordered 上用 <', '''package main

import ("cmp"; "fmt")

func Max[T cmp.Ordered](a, b T) T { if a > b { return a }; return b }

func main() { fmt.Println(Max(1, 2), Max("a", "b"), Max(1.5, 0.5)) }
''', 2)
print('  cmp.Ordered 的定义(标准库源码):')
src = subprocess.run(['sed', '-n', '/^type Ordered interface/,/^}/p', '/opt/homebrew/Cellar/go/1.27.1/libexec/src/cmp/cmp.go'], capture_output=True, text=True).stdout.rstrip()
for l in src.split('\n'): print('    ' + l)

print('== 四:类型推断的边界')
I = '''package main

import ("fmt"; "strconv")

var _ = strconv.Itoa
var _ = fmt.Sprint

func Max[T int | float64](a, b T) T { if a > b { return a }; return b }
func Zero[T any]() T { var z T; return z }
func Map[T, U any](xs []T, f func(T) U) []U { var r []U; for _, x := range xs { r = append(r, f(x)) }; return r }
type IDs []int
func First[S ~[]E, E any](s S) E { return s[0] }
'''
show_ce('Max(1, 2.5)(无类型常量混用)', I + 'func main() { fmt.Printf("  %T %v\\n", Max(1, 2.5), Max(1, 2.5)) }\n', 2)
show_ce('Max(x, 2.5),x 是 int 变量', I + 'func main() { x := 1; fmt.Println(Max(x, 2.5)) }\n', 2)
show_ce('Zero()(只能从返回值推断)', I + 'func main() { fmt.Println(Zero()) }\n', 2)
show_ce('Zero[int]() 显式实例化', I + 'func main() { fmt.Printf("  %v %q\\n", Zero[int](), Zero[string]()) }\n', 2)
show_ce('Map(xs, strconv.Itoa) 同时推断 T 与 U', I + 'func main() { fmt.Printf("  %T %v\\n", Map([]int{1, 2}, strconv.Itoa), Map([]int{1, 2}, strconv.Itoa)) }\n', 2)
show_ce('First(IDs{3, 4}) 用 ~[]E 约束保留具名切片类型', I + 'func main() { fmt.Printf("  %v\\n", First(IDs{3, 4})) }\n', 2)
show_ce('f := Max(不实例化就当值用)', I + 'func main() { f := Max; _ = f }\n', 2)

print('== 五:Go 1.27 新增:方法可以带自己的类型参数(泛型方法)。语言版本开关、用法与限制')
GM = '''package main

import "fmt"

type List[E any] []E

func (l List[E]) Apply[F any](f func(E) F) List[F] {
	r := make(List[F], len(l))
	for i, x := range l { r[i] = f(x) }
	return r
}

func main() {
	l := List[int]{1, 2, 3}
	fmt.Println(l.Apply(func(x int) string { return fmt.Sprint(x * 10) }))
	g := l.Apply[float64]
	fmt.Printf("  %T\\n", g)
}
'''
for v in ('1.26', '1.27'):
    d = gdir('gm' + v); write(d, {'main.go': GM}); mod(d, go=v)
    rc, o = go(d, 'build', '-o', 'app')
    if rc != 0:
        print(f'  go.mod 写 go {v}:编译失败')
        for l in o.split('\n'):
            if l.startswith('./main.go'): print('    ' + l.replace('./main.go', 'main.go'))
    else:
        out = subprocess.run([str(d / 'app')], capture_output=True, text=True).stdout.rstrip()
        print(f'  go.mod 写 go {v}:编译通过,运行输出:' + out.replace('\n', ' | '))
show_ce('Box[int] 有泛型方法 Map,能实现 interface{ Map(func(int) string) string } 吗', '''package main

type Box[T any] struct{ v T }

func (b Box[T]) Map[U any](f func(T) U) U { return f(b.v) }

type Mapper interface{ Map(func(int) string) string }

func main() {
	var m Mapper = Box[int]{1}
	_ = m
}
''', 2)
show_ce('接口方法声明类型参数', '''package main

type Mapper interface{ Map[U any](func(int) U) U }

func main() {}
''', 2)
show_ce('不实例化就把泛型方法当值', '''package main

type Box[T any] struct{ v T }

func (b Box[T]) Map[U any](f func(T) U) U { return f(b.v) }

func main() {
	b := Box[int]{1}
	f := b.Map
	_ = f
}
''', 2)
