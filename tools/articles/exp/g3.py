import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g3')
SRC = r'''
package main

import (
	"fmt"
	"reflect"
	"unsafe"
)

type MyErr struct{ Code int }

func (e *MyErr) Error() string { return fmt.Sprintf("myerr %d", e.Code) }

// 返回具体指针类型再赋给 error:fail=false 时返回的是 nil 指针
func buggy(fail bool) error {
	var e *MyErr
	if fail {
		e = &MyErr{Code: 7}
	}
	return e
}

func fixed(fail bool) error {
	if fail {
		return &MyErr{Code: 7}
	}
	return nil
}

type words struct{ tab, data unsafe.Pointer }

func w(err error) words { return *(*words)(unsafe.Pointer(&err)) }

func main() {
	e1, e2 := buggy(false), fixed(false)
	fmt.Printf("  buggy(false):err == nil → %v;%%T = %T;%%v = %v\n", e1 == nil, e1, e1)
	fmt.Printf("  fixed(false):err == nil → %v;%%T = %T;%%v = %v\n", e2 == nil, e2, e2)
	a, b := w(e1), w(e2)
	fmt.Printf("  buggy 的两个字:tab == nil?%v,data == nil?%v;fixed 的两个字:tab == nil?%v,data == nil?%v\n", a.tab == nil, a.data == nil, b.tab == nil, b.data == nil)
	fmt.Println("== 二:几种“nil”放进接口以后,和 nil 比较的结果(接口值 == nil 只在 类型字与数据字 都为空 时为真)")
	var p *MyErr
	var e error
	var any1 any
	var any2 any = p
	var e3 error = p
	fmt.Printf("  var p *MyErr:p == nil → %v\n", p == nil)
	fmt.Printf("  var e error:e == nil → %v\n", e == nil)
	fmt.Printf("  var any1 any:any1 == nil → %v\n", any1 == nil)
	fmt.Printf("  var any2 any = p(nil 的 *MyErr):any2 == nil → %v;any2 == (*MyErr)(nil) → %v;any2 == any(nil) → %v\n", any2 == nil, any2 == (*MyErr)(nil), any2 == any(nil))
	fmt.Printf("  var e3 error = p:e3 == nil → %v;e3 == (*MyErr)(nil) → %v\n", e3 == nil, e3 == error((*MyErr)(nil)))
	fmt.Println("== 三:把 nil 指针装进接口之后调用方法:取决于方法有没有解引用接收者")
	try := func(name string, f func()) {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("  %-34s panic:%v\n", name, r)
			}
		}()
		f()
	}
	try("e1.Error()(指针接收者,解引用 e.Code)", func() { fmt.Println("  返回:", e1.Error()) })
	try("N.Error()(方法里先判断 n == nil)", func() { var n *NilSafe; var err error = n; fmt.Println("  返回:", err.Error()) })
	try("err.(*MyErr) 断言", func() { v, ok := e1.(*MyErr); fmt.Printf("  断言 ok = %v,v == nil → %v\n", ok, v == nil) })
	fmt.Println("== 四:判断“接口里装的是不是 nil 指针”:reflect 与类型断言")
	isNil := func(v any) bool {
		if v == nil {
			return true
		}
		rv := reflect.ValueOf(v)
		switch rv.Kind() {
		case reflect.Pointer, reflect.Map, reflect.Slice, reflect.Func, reflect.Chan, reflect.Interface:
			return rv.IsNil()
		}
		return false
	}
	fmt.Printf("  isNil(buggy(false)) → %v;isNil(fixed(false)) → %v;isNil(&MyErr{}) → %v;isNil(0) → %v\n", isNil(e1), isNil(e2), isNil(&MyErr{}), isNil(0))
	try("reflect.ValueOf(0).IsNil()", func() { fmt.Println(reflect.ValueOf(0).IsNil()) })
	var m map[string]int
	var s []int
	var f func()
	fmt.Printf("  nil map / nil slice / nil func 装进 any:== nil → %v / %v / %v;isNil → %v / %v / %v\n", any(m) == nil, any(s) == nil, any(f) == nil, isNil(m), isNil(s), isNil(f))
}

type NilSafe struct{}

func (n *NilSafe) Error() string {
	if n == nil {
		return "<nil NilSafe>"
	}
	return "NilSafe"
}
'''
print('== 一:经典陷阱:函数返回 error,内部用具体指针类型变量,没有错误时返回的是 nil 指针(Go 1.27.1)')
print('  源码(省略 main 与辅助):'); print('\n'.join('    ' + l for l in numbered('\n'.join(SRC.split('\n')[:30])).split('\n')))
r = grun('ni1', {'main.go': SRC})
rc, o = go(r['d'], 'vet', '.')
head, _, rest = r['out'].partition('\n== 二')
print(head); print(f'  go vet 对这份代码:rc={rc},输出:{o or "(无任何警告)"}')
print('== 二' + rest)
