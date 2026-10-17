import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g15')
SRC = r'''
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"reflect"
	"sort"
	"strings"
)

type Animal struct{ Name string }

func (a Animal) Speak() string  { return a.Name + " 发出声音" }
func (a *Animal) Rename(n string) { a.Name = n }
func (a Animal) Intro() string  { return "我是 " + a.Name + ",我的声音:" + a.Speak() }

type Dog struct {
	Animal
	Breed string
}

func (d Dog) Speak() string { return d.Name + " 汪汪" }

type Cat struct {
	*Animal
	Lives int
}

func names(t reflect.Type) string {
	var ns []string
	for i := 0; i < t.NumMethod(); i++ { ns = append(ns, t.Method(i).Name) }
	sort.Strings(ns)
	return strings.Join(ns, ",")
}

// 装饰器:嵌入一个 io.Writer,只改写 Write
type countWriter struct {
	io.Writer
	n int
}

func (c *countWriter) Write(p []byte) (int, error) { c.n += len(p); return c.Writer.Write(p) }

type Inner struct {
	ID   int    `json:"id"`
	Note string `json:"note"`
}
type Outer struct {
	Inner
	Name string `json:"name"`
	Note string `json:"outer_note"`
}

func main() {
	d := Dog{Animal{"旺财"}, "柴犬"}
	fmt.Printf("  d.Name = %q(提升的字段);d.Animal.Name = %q;d.Rename(\"小黄\") 之后 d.Name = ", d.Name, d.Animal.Name)
	d.Rename("小黄")
	fmt.Printf("%q\n", d.Name)
	fmt.Printf("  Dog 自己定义了 Speak:d.Speak() = %q;d.Animal.Speak() = %q\n", d.Speak(), d.Animal.Speak())
	fmt.Printf("  d.Intro()(Animal 的方法,里面调用 a.Speak()):%q ——不会调用 Dog 的 Speak(没有虚函数分派)\n", d.Intro())

	fmt.Println("== 二:方法集:嵌入 T 与嵌入 *T")
	fmt.Printf("  Animal 的方法集:%s;*Animal 的方法集:%s\n", names(reflect.TypeOf(Animal{})), names(reflect.TypeOf(&Animal{})))
	fmt.Printf("  Dog(嵌入 Animal)的方法集:%s;*Dog 的方法集:%s\n", names(reflect.TypeOf(Dog{})), names(reflect.TypeOf(&Dog{})))
	fmt.Printf("  Cat(嵌入 *Animal)的方法集:%s;*Cat 的方法集:%s\n", names(reflect.TypeOf(Cat{})), names(reflect.TypeOf(&Cat{})))

	fmt.Println("== 三:装饰器:嵌入接口,只改写一个方法;嵌入的接口是 nil 时调用会 panic")
	var buf bytes.Buffer
	cw := &countWriter{Writer: &buf}
	fmt.Fprintf(cw, "hello, %s", "world")
	fmt.Fprint(cw, "!")
	fmt.Printf("  经 countWriter 写了 %q,统计 n = %d,底层缓冲区内容 %q\n", "hello, world!", cw.n, buf.String())
	func() {
		defer func() { fmt.Printf("  nil 的嵌入接口:cw2.Write 调用 → panic:%v\n", recover()) }()
		cw2 := &countWriter{}
		cw2.Write([]byte("x"))
	}()

	fmt.Println("== 四:encoding/json 会把嵌入结构体的字段展开;同名字段取层级浅的")
	o := Outer{Inner{7, "内层备注"}, "名称", "外层备注"}
	js, _ := json.Marshal(o)
	fmt.Printf("  json.Marshal(Outer{Inner{7, ...}, ...}) = %s\n", js)
	t := reflect.TypeOf(o)
	f1, _ := t.FieldByName("Note")
	fmt.Printf("  Outer.Note 解析到的字段:index %v(外层的 Note);Outer.ID 解析到:index %v(提升自 Inner)\n", f1.Index, func() []int { f, _ := t.FieldByName("ID"); return f.Index }())
	fmt.Printf("  reflect 报告 Outer 有 %d 个顶层字段(%s),其中 Inner 的 Anonymous = %v\n", t.NumField(), func() string { var s []string; for i := 0; i < t.NumField(); i++ { s = append(s, t.Field(i).Name) }; return strings.Join(s, "、") }(), t.Field(0).Anonymous)
}
'''
print('== 一:方法与字段的提升、遮蔽,以及“不是虚函数”(Go 1.27.1)')
r = grun('em1', {'main.go': SRC})
CE = r'''
package main

type A struct{ X int }
type B struct{ X int }
type C struct {
	A
	B
}

type Incer interface{ Inc() }
type P struct{ n int }

func (p *P) Inc() { p.n++ }

type Q struct{ P }

func main() {
	c := C{}
	_ = c.X
	var i Incer = Q{}
	_ = i
}
'''
rc = grun('em2', {'main.go': CE})
print(r['out'] if r['crc'] == 0 else r['cout'])
print('== 五:编译器的报错:同深度的同名字段有歧义;嵌入 P 的 Q(值)没有 *P 的方法')
for l in rc['cout'].split('\n'):
    if l.startswith('./main.go'): print('  ' + l.replace('./main.go', 'main.go'))
