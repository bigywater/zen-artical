import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g28')
SRC = r'''
package main

import (
	"fmt"
	"reflect"
	"sort"
	"testing"
)

type T struct {
	A, B, C, D int
	Name       string
	Tags       []int
}

func (t *T) Add(x, y int) int { return t.A + x + y }
func (t T) Value() int        { return t.A }

//go:noinline
func add(x, y int) int { return x + y }

var sink int
var sinkS string

func main() {
	t := &T{A: 1, B: 2, C: 3, D: 4, Name: "n", Tags: []int{1, 2, 3}}
	rv := reflect.ValueOf(t).Elem()
	rt := rv.Type()
	idxD := 3

	fmt.Println("  --- 读字段 ---")
	bench("直接读 t.D", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += t.D } })
	bench("reflect Field(3).Int()(预先取好 Value)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(rv.Field(idxD).Int()) } })
	bench("reflect ValueOf(t).Elem().Field(3).Int()", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(reflect.ValueOf(t).Elem().Field(idxD).Int()) } })
	bench("reflect FieldByName(\"D\").Int()", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(rv.FieldByName("D").Int()) } })
	bench("Type.FieldByName(\"D\")(只查字段信息)", func(b *testing.B) { for i := 0; i < b.N; i++ { f, _ := rt.FieldByName("D"); sink += f.Index[0] } })
	fmt.Println("  --- 写字段 ---")
	bench("直接写 t.D = i", func(b *testing.B) { for i := 0; i < b.N; i++ { t.D = i } })
	bench("reflect Field(3).SetInt(i)", func(b *testing.B) { for i := 0; i < b.N; i++ { rv.Field(idxD).SetInt(int64(i)) } })
	fmt.Println("  --- 调用 ---")
	bench("直接调用 add(1, 2)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += add(1, 2) } })
	fn := reflect.ValueOf(add)
	args := []reflect.Value{reflect.ValueOf(1), reflect.ValueOf(2)}
	bench("reflect Value.Call(fn, [1 2])(预先准备 args)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(fn.Call(args)[0].Int()) } })
	bench("直接调用 t.Add(1, 2)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += t.Add(1, 2) } })
	m := reflect.ValueOf(t).MethodByName("Add")
	bench("reflect Method 预先取好 + Call", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(m.Call(args)[0].Int()) } })
	bench("reflect MethodByName(\"Add\") 每次都查 + Call", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += int(reflect.ValueOf(t).MethodByName("Add").Call(args)[0].Int()) } })
	fmt.Println("  --- 类型判断 ---")
	var x any = t
	bench("类型断言 x.(*T)", func(b *testing.B) { for i := 0; i < b.N; i++ { if _, ok := x.(*T); ok { sink++ } } })
	bench("reflect.TypeOf(x).Kind() == Pointer", func(b *testing.B) { for i := 0; i < b.N; i++ { if reflect.TypeOf(x).Kind() == reflect.Pointer { sink++ } } })
	fmt.Println("  --- 比较 ---")
	a1 := T{1, 2, 3, 4, "n", []int{1, 2, 3}}
	a2 := T{1, 2, 3, 4, "n", []int{1, 2, 3}}
	bench("手写比较(字段逐个 ==,切片用循环)", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			eq := a1.A == a2.A && a1.B == a2.B && a1.C == a2.C && a1.D == a2.D && a1.Name == a2.Name && len(a1.Tags) == len(a2.Tags)
			for j := range a1.Tags { eq = eq && a1.Tags[j] == a2.Tags[j] }
			if eq { sink++ }
		}
	})
	bench("reflect.DeepEqual(a1, a2)", func(b *testing.B) { for i := 0; i < b.N; i++ { if reflect.DeepEqual(a1, a2) { sink++ } } })
	fmt.Println("  --- 创建 ---")
	bench("new(T)", func(b *testing.B) { for i := 0; i < b.N; i++ { p := new(T); sink += p.A } })
	bench("reflect.New(rt).Interface().(*T)", func(b *testing.B) { for i := 0; i < b.N; i++ { p := reflect.New(rt).Interface().(*T); sink += p.A } })

	row := func(name string, f func()) { fmt.Printf("  %-46s %2.0f 次\n", name, testing.AllocsPerRun(1000, f)) }
	fmt.Println("  --- 分配次数(AllocsPerRun)---")
	row("reflect Field(3).Int()", func() { sink += int(rv.Field(idxD).Int()) })
	row("reflect FieldByName(\"D\").Int()", func() { sink += int(rv.FieldByName("D").Int()) })
	row("fn.Call(args)(函数,2 个参数)", func() { sink += int(fn.Call(args)[0].Int()) })
	row("m.Call(args)(方法)", func() { sink += int(m.Call(args)[0].Int()) })
	row("reflect.MethodByName 每次查找 + Call", func() { sink += int(reflect.ValueOf(t).MethodByName("Add").Call(args)[0].Int()) })
	row("reflect.DeepEqual(a1, a2)", func() { if reflect.DeepEqual(a1, a2) { sink++ } })
	row("reflect.TypeOf(x).Kind()", func() { if reflect.TypeOf(x).Kind() == reflect.Pointer { sink++ } })
	row("reflect.New(rt)", func() { p := reflect.New(rt).Interface().(*T); sink += p.A })
	_ = sort.Ints
	_ = sinkS
}
''' + GBENCH
r = grun('rc1', {'main.go': SRC}, timeout=900)
NUM = '一二三四五六七八'
k = 0
if r['crc'] != 0: print(r['cout'])
for l in (r['out'] if r['crc'] == 0 else '').split('\n'):
    m = re.match(r'\s*--- (.*?)\s*---', l)
    if m:
        title = m.group(1)
        extra = {'读字段': '(Go 1.27.1,arm64;7 轮取中位数;函数与方法定义在同一个文件里)', '分配次数(AllocsPerRun)': '(testing.AllocsPerRun,1000 次)'}.get(title, '')
        print(f'== {NUM[k]}:{title}{extra}'); k += 1
    else: print(l)
