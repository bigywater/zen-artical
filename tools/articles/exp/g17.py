import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g17')
SRC = r'''
package main

import "fmt"

type A struct{ v int }
type B struct{ v int }
type MyInt int
type Celsius float64

//go:noinline
func Show[T any](x T) string { return fmt.Sprint(x) }

//go:noinline
func ShowInt(x int) string { return fmt.Sprint(x) }

//go:noinline
func Sum[T int | int32 | float64 | MyInt](xs []T) T {
	var s T
	for _, x := range xs { s += x }
	return s
}

func main() {
	fmt.Println(Show(1), Show(int32(2)), Show(MyInt(3)), Show(2.5), Show(Celsius(1.5)), Show("s"), Show(&A{1}), Show(&B{2}), Show([]int{1}), Show(map[string]int{"a": 1}))
	fmt.Println(ShowInt(5), Sum([]int{1, 2}), Sum([]int32{1}), Sum([]float64{1.5}), Sum([]MyInt{4}))
}
'''
print('== 一:一个泛型函数,实例化成哪些机器码?用 go tool nm 列出二进制里 main.Show 与 main.Sum 的符号(Go 1.27.1,arm64)')
r = grun('gi1', {'main.go': SRC})
print('  程序输出:' + r['out'].replace('\n', ' | '))
rc, o = go(r['d'], 'tool', 'nm', '-n', 'app')
syms = sorted({l.split()[-1] for l in o.split('\n') if re.search(r'main\.(Show|Sum)\[', l) and ' T ' in l})
for s_ in syms: print('    ' + s_)
print(f'  共 {len(syms)} 个函数符号。注意:*A、*B 共用同一个符号(指针的 GC shape 相同);int 与 MyInt 共用 go.shape.int;float64 与 Celsius 共用 go.shape.float64')
dict_syms = sorted({l.split()[-1] for l in o.split('\n') if 'main..dict.' in l})
print(f'  另有字典符号 {len(dict_syms)} 个(每个“真实类型实参的组合”一个):')
for s_ in dict_syms: print('    ' + s_)

print('== 二:调用点怎么传字典:go build -gcflags=-S 看 main.main 里对 Show 的调用')
r2 = grun('gi2', {'main.go': SRC}, gcflags='-S')
ls = asm_fn(r2['cout'], 'main', ('main..dict.Show', 'CALL\tmain.Show', 'CALL main.Show'))
for l in ls[:14]: print('    ' + l)
print('  函数头(STEXT 行里的 args= 是参数占用的字节数)——泛型实例化 Show[go.shape.int] 与同样函数体的非泛型 ShowInt(x int) 对比:')
for fn in ('Show[go.shape.int]', 'ShowInt'):
    for l in asm_fn(r2['cout'], fn, 'HEADER'): print('    ' + re.sub(r'\s+', ' ', l.replace(str(GT), '<gtmp>'))[:170])

print('== 三:调用成本:泛型求和与手写具体类型求和(1000 个元素,7 轮取中位数)')
B = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
)

type MyInt int

type Valer interface{ Val() int }
type Foo struct{ v int }

func (f Foo) Val() int   { return f.v }
func (f *Foo) PVal() int { return f.v }

type PFoo struct{ v int }

func (f *PFoo) Val() int { return f.v }

//go:noinline
func SumGeneric[T int | float64](xs []T) T {
	var s T
	for _, x := range xs { s += x }
	return s
}

//go:noinline
func SumInt(xs []int) int {
	s := 0
	for _, x := range xs { s += x }
	return s
}

//go:noinline
func TotalGeneric[T Valer](xs []T) int {
	s := 0
	for _, x := range xs { s += x.Val() }
	return s
}

//go:noinline
func TotalIface(xs []Valer) int {
	s := 0
	for _, x := range xs { s += x.Val() }
	return s
}

//go:noinline
func TotalDirect(xs []Foo) int {
	s := 0
	for _, x := range xs { s += x.Val() }
	return s
}

var sink int

func main() {
	ints := make([]int, 1000)
	foos := make([]Foo, 1000)
	pfoos := make([]*PFoo, 1000)
	ifs := make([]Valer, 1000)
	for i := range ints { ints[i] = i; foos[i] = Foo{i}; pfoos[i] = &PFoo{i}; ifs[i] = Foo{i} }
	bench("SumInt([]int) 具体类型", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumInt(ints) } })
	bench("SumGeneric[int]([]int)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += SumGeneric(ints) } })
	bench("TotalDirect([]Foo) 直接调用方法", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += TotalDirect(foos) } })
	bench("TotalGeneric[Foo] 约束里的方法", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += TotalGeneric(foos) } })
	bench("TotalGeneric[*PFoo] 指针类型实参", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += TotalGeneric(pfoos) } })
	bench("TotalIface([]Valer) 接口切片", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += TotalIface(ifs) } })
	_ = fmt.Sprint
	_ = sort.Ints
}
''' + GBENCH
r3 = grun('gi3', {'main.go': B}); print(r3['out'] if r3['crc'] == 0 else r3['cout'])

print('== 四:二进制体积随实例化数量的变化:同一个泛型函数,实例化 1、4、16 种不同 GC shape 的类型,与 16 个指向不同结构体的指针类型')
def build_prog(kinds):
    decl = []; calls = []
    for i, k in enumerate(kinds):
        if k == 'ptr':
            decl.append(f'type S{i} struct{{ a, b int }}'); calls.append(f'Work(&S{i}{{}})')
        else:
            decl.append(f'type S{i} struct{{ a [{i + 1}]int32 }}'); calls.append(f'Work(S{i}{{}})')
    return 'package main\n\nimport "fmt"\n\n' + '\n'.join(decl) + '\n\n//go:noinline\nfunc Work[T any](x T) string { return fmt.Sprintf("%v-%T", x, x) }\n\nfunc main() {\n\t' + '\n\t'.join(f'fmt.Println({c})' for c in calls) + '\n}\n'
def size_of(name, kinds):
    d = gdir(name); write(d, {'main.go': build_prog(kinds)}); mod(d)
    rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
    rc, nm = go(d, 'tool', 'nm', 'app')
    n = len([1 for l in nm.split('\n') if ' T main.Work[' in l])
    return os.path.getsize(d / 'app'), n
for label, kinds in [('1 种值类型', ['val']), ('4 种不同大小的值类型', ['val'] * 4), ('16 种不同大小的值类型', ['val'] * 16), ('16 种指针类型(指向不同结构体)', ['ptr'] * 16)]:
    sz, n = size_of('gis', kinds)
    print(f'  {label}:二进制 {sz} 字节,main.Work 的函数符号 {n} 个')
shutil.rmtree(GT / 'gis', ignore_errors=True)
