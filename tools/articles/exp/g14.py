import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g14')
SRC = r'''
package main

import (
	"fmt"
	"reflect"
	"sort"
	"strings"
)

type Counter struct{ n int }

func (c Counter) Value() int { return c.n }
func (c *Counter) Inc()      { c.n++ }
func (c Counter) IncLost()   { c.n++ }

func names(t reflect.Type) string {
	var ns []string
	for i := 0; i < t.NumMethod(); i++ { ns = append(ns, t.Method(i).Name) }
	sort.Strings(ns)
	return strings.Join(ns, ",")
}

func main() {
	fmt.Printf("  Counter 的方法集(reflect):%s;*Counter 的方法集:%s\n", names(reflect.TypeOf(Counter{})), names(reflect.TypeOf(&Counter{})))
	c := Counter{}
	c.Inc()
	c.IncLost()
	c.Inc()
	fmt.Printf("  c.Inc() 两次、c.IncLost() 一次之后 c.n = %d(值接收者的修改作用在副本上,丢了)\n", c.n)

	fmt.Println("== 三:方法值在绑定时拷贝接收者")
	c2 := Counter{n: 1}
	fv := c2.Value
	fp := c2.Inc
	c2.n = 50
	fp()
	fmt.Printf("  fv := c2.Value(值接收者,绑定时拷贝了 c2);之后 c2.n = 50:fv() = %d;fp := c2.Inc(指针接收者,绑定的是 &c2);fp() 之后 c2.n = %d\n", fv(), c2.n)
	me := Counter.Value
	pe := (*Counter).Inc
	cc := Counter{n: 7}
	pe(&cc)
	fmt.Printf("  方法表达式:Counter.Value 的类型是 %T;(*Counter).Inc 的类型是 %T;pe(&cc) 之后 me(cc) = %d\n", me, pe, me(cc))

	fmt.Println("== 四:nil 接收者:值接收者的方法通过 nil 指针调用会 panic,指针接收者的方法可以收到 nil")
	var np *Counter
	try := func(name string, f func()) {
		defer func() {
			if r := recover(); r != nil { fmt.Printf("  %-26s panic:%v\n", name, r) }
		}()
		f()
	}
	try("np.Value()(值接收者)", func() { fmt.Println("  返回", np.Value()) })
	try("np.IncNilSafe()(指针接收者)", func() { np.IncNilSafe(); fmt.Println("  正常返回,np == nil 时被方法自己处理了") })
}

func (c *Counter) IncNilSafe() {
	if c == nil { return }
	c.n++
}
'''
print('== 一:方法集:值 T 与指针 *T 能调用的方法不同(Go 1.27.1)')
print('  源码(省略 main 与辅助):'); print('\n'.join('    ' + l for l in numbered('type Counter struct{ n int }\n\nfunc (c Counter) Value() int { return c.n }\nfunc (c *Counter) Inc()      { c.n++ }\nfunc (c Counter) IncLost()   { c.n++ }').split('\n')))
r = grun('ms1', {'main.go': SRC})
CE = r'''
package main

type I interface{ Inc() }
type V interface{ Value() int }
type Counter struct{ n int }

func (c Counter) Value() int { return c.n }
func (c *Counter) Inc()      { c.n++ }

func get() Counter { return Counter{} }

func main() {
	var v1 V = Counter{}
	var v2 V = &Counter{}
	var i1 I = &Counter{}
	var i2 I = Counter{}
	m := map[string]Counter{"a": {}}
	m["a"].Inc()
	get().Inc()
	_, _, _, _ = v1, v2, i1, i2
}
'''
rc = grun('ms2', {'main.go': CE})
head, _, rest = r['out'].partition('\n== 三')
print(head)
print('== 二:编译器的报错:哪些赋值与调用不被允许')
for l in rc['cout'].split('\n'):
    if l.startswith('./main.go'): print('  ' + l.replace('./main.go', 'main.go'))
print('== 三' + rest)
