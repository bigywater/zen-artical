import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g23')
SRC = r'''
package main

import (
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"sort"
	"testing"
)

var ErrNotFound = errors.New("not found")

type MyErr struct{ Code int }

func (e *MyErr) Error() string { return fmt.Sprintf("myerr %d", e.Code) }

// 带 Is 方法:按 Code 匹配,而不是指针相等
type CodeErr struct{ Code int }

func (e CodeErr) Error() string        { return fmt.Sprintf("code %d", e.Code) }
func (e CodeErr) Is(target error) bool { t, ok := target.(CodeErr); return ok && t.Code == e.Code }

// 不可比较的错误类型(含切片)
type SliceErr struct{ Parts []string }

func (e SliceErr) Error() string { return fmt.Sprint(e.Parts) }

func chain(err error) string {
	s := ""
	for i := 0; err != nil; i++ {
		s += fmt.Sprintf("\n      [%d] %T:%v", i, err, err)
		err = errors.Unwrap(err)
	}
	return s
}

func main() {
	base := ErrNotFound
	w1 := fmt.Errorf("读取配置: %w", base)
	w2 := fmt.Errorf("启动服务: %w", w1)
	fmt.Printf("  w2 = %q;链:%s\n", w2.Error(), chain(w2))
	fmt.Printf("  w2 == ErrNotFound → %v;errors.Is(w2, ErrNotFound) → %v;errors.Unwrap(w2) == w1 → %v\n", w2 == base, errors.Is(w2, ErrNotFound), errors.Unwrap(w2) == w1)
	v := fmt.Errorf("读取配置: %v", base)
	fmt.Printf("  用 %%v 而不是 %%w:errors.Is(v, ErrNotFound) → %v;errors.Unwrap(v) → %v;类型 %T\n", errors.Is(v, ErrNotFound), errors.Unwrap(v), v)
	e := fmt.Errorf("同时包装两个: %w 与 %w", io.EOF, ErrNotFound)
	fmt.Printf("  一个 Errorf 里两个 %%w:类型 %T;errors.Unwrap → %v;Is(io.EOF) → %v;Is(ErrNotFound) → %v\n", e, errors.Unwrap(e), errors.Is(e, io.EOF), errors.Is(e, ErrNotFound))

	fmt.Println("== 二:errors.As:按类型查找并取出,以及自定义 Is")
	var target *MyErr
	err := fmt.Errorf("外层: %w", fmt.Errorf("中层: %w", &MyErr{Code: 42}))
	ok := errors.As(err, &target)
	fmt.Printf("  errors.As(err, &target *MyErr) → %v;target.Code = %d\n", ok, target.Code)
	var pe *fs.PathError
	_, oerr := os.Open("/no/such/file.txt")
	fmt.Printf("  os.Open 失败:errors.Is(err, fs.ErrNotExist) → %v;errors.As(err, &*fs.PathError) → %v,Op = %q,Path = %q\n", errors.Is(oerr, fs.ErrNotExist), errors.As(oerr, &pe), pe.Op, pe.Path)
	fmt.Printf("  自定义 Is:errors.Is(fmt.Errorf(\"x: %%w\", CodeErr{404}), CodeErr{404}) → %v;换成 CodeErr{500} → %v\n", errors.Is(fmt.Errorf("x: %w", CodeErr{404}), CodeErr{404}), errors.Is(fmt.Errorf("x: %w", CodeErr{404}), CodeErr{500}))
	se := SliceErr{[]string{"a"}}
	fmt.Printf("  不可比较的错误类型 SliceErr(含切片):errors.Is(se, se) → %v(没有 panic)\n", errors.Is(se, se))
	try := func(name string, f func()) {
		defer func() { fmt.Printf("  %s → panic:%v\n", name, recover()) }()
		f()
		fmt.Printf("  %s 正常\n", name)
	}
	try("errors.As(err, nil)", func() { errors.As(err, nil) })
	try("errors.As(err, target)(目标不是指针的指针)", func() { var m MyErr; errors.As(err, m) })
	try("errors.As(err, &str)(*string 没有实现 error)", func() { var s string; errors.As(err, &s) })
	if v, ok := errors.AsType[*MyErr](err); ok {
		fmt.Printf("  errors.AsType[*MyErr](err)(泛型版本)→ Code = %d\n", v.Code)
	}

	fmt.Println("== 三:成本:链长度对 errors.Is / errors.As 的影响,以及 Errorf 的分配(7 轮取中位数)")
	mk := func(n int) error {
		e := error(ErrNotFound)
		for i := 0; i < n; i++ { e = fmt.Errorf("层 %d: %w", i, e) }
		return e
	}
	for _, n := range []int{1, 10, 50} {
		ce := mk(n)
		var sink bool
		bench(fmt.Sprintf("errors.Is 链长 %d(命中最内层)", n), func(b *testing.B) { for i := 0; i < b.N; i++ { sink = errors.Is(ce, ErrNotFound) } })
		_ = sink
	}
	bench("errors.Is 链长 10(不命中)", func(b *testing.B) { ce := mk(10); for i := 0; i < b.N; i++ { _ = errors.Is(ce, io.EOF) } })
	fmt.Printf("  AllocsPerRun:fmt.Errorf(\"x: %%w\", base) %.0f 次;errors.New 的错误再 Is %.0f 次;fmt.Errorf(\"x: %%v\", base) %.0f 次\n", testing.AllocsPerRun(1000, func() { _ = fmt.Errorf("x: %w", base) }), testing.AllocsPerRun(1000, func() { _ = errors.Is(w2, ErrNotFound) }), testing.AllocsPerRun(1000, func() { _ = fmt.Errorf("x: %v", base) }))
	_ = sort.Ints
}
''' + GBENCH
print('== 一:%w 包装与 errors.Is / errors.Unwrap 沿链查找(Go 1.27.1)')
r = grun('ew1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
