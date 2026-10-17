import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g24')
SRC = r'''
package main

import (
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"sort"
	"strings"
	"testing"
)

var ErrA = errors.New("A 出错")
var ErrB = errors.New("B 出错")

type CodeErr struct{ Code int }

func (e *CodeErr) Error() string { return fmt.Sprintf("code %d", e.Code) }

func main() {
	j := errors.Join(ErrA, ErrB)
	fmt.Printf("  errors.Join(ErrA, ErrB):类型 %T\n", j)
	fmt.Printf("  Error() = %q(用换行连接)\n", j.Error())
	fmt.Printf("  errors.Is(j, ErrA) = %v;errors.Is(j, ErrB) = %v;errors.Is(j, io.EOF) = %v\n", errors.Is(j, ErrA), errors.Is(j, ErrB), errors.Is(j, io.EOF))
	fmt.Printf("  errors.Unwrap(j) = %v(Join 的 Unwrap 返回 []error,errors.Unwrap 只处理单个)\n", errors.Unwrap(j))
	if u, ok := j.(interface{ Unwrap() []error }); ok { fmt.Printf("  j.(interface{ Unwrap() []error }) 返回 %d 个错误\n", len(u.Unwrap())) }
	fmt.Printf("  errors.Join(nil, nil) == nil → %v;errors.Join(nil, ErrA, nil).Error() = %q\n", errors.Join(nil, nil) == nil, errors.Join(nil, ErrA, nil).Error())
	one := errors.Join(ErrA)
	fmt.Printf("  errors.Join(ErrA) 只有一个错误:仍然是 %T,== ErrA → %v;Is → %v\n", one, one == ErrA, errors.Is(one, ErrA))
	fmt.Printf("  %%v = %q;%%q = %q;%%+v = %q\n", fmt.Sprintf("%v", j), fmt.Sprintf("%q", j), fmt.Sprintf("%+v", j))

	fmt.Println("== 二:errors.As 在 Join 里找到哪一个:按顺序深度优先,第一个匹配")
	j2 := errors.Join(&CodeErr{1}, fmt.Errorf("包装: %w", &CodeErr{2}), &CodeErr{3})
	var ce *CodeErr
	fmt.Printf("  Join(&CodeErr{1}, 包装的 &CodeErr{2}, &CodeErr{3}):errors.As → %v,取到 Code = %d\n", errors.As(j2, &ce), ce.Code)
	j3 := errors.Join(fmt.Errorf("包装: %w", &CodeErr{2}), &CodeErr{3})
	errors.As(j3, &ce)
	fmt.Printf("  Join(包装的 &CodeErr{2}, &CodeErr{3}):取到 Code = %d(深度优先:先走完第一个分支)\n", ce.Code)
	nested := errors.Join(errors.Join(ErrA, io.EOF), ErrB)
	fmt.Printf("  嵌套 Join(Join(ErrA, io.EOF), ErrB):Is(io.EOF) = %v;Error() = %q\n", errors.Is(nested, io.EOF), nested.Error())
	m := fmt.Errorf("多个原因: %w; %w", ErrA, ErrB)
	fmt.Printf("  对比 fmt.Errorf(\"%%w; %%w\"):类型 %T;Error() = %q;Is(ErrA) = %v;Is(ErrB) = %v\n", m, m.Error(), errors.Is(m, ErrA), errors.Is(m, ErrB))

	fmt.Println("== 三:典型用法:循环里收集错误;文件清理里合并关闭错误")
	var errs []error
	for i, name := range []string{"/no/a.txt", "/etc/hosts", "/no/b.txt"} {
		f, err := os.Open(name)
		if err != nil { errs = append(errs, fmt.Errorf("第 %d 个文件: %w", i, err)); continue }
		f.Close()
	}
	all := errors.Join(errs...)
	fmt.Printf("  收集到 %d 个错误,Join 之后:\n", len(errs))
	for _, l := range strings.Split(all.Error(), "\n") { fmt.Printf("    %s\n", l) }
	fmt.Printf("  errors.Is(all, fs.ErrNotExist) = %v\n", errors.Is(all, fs.ErrNotExist))
	fmt.Printf("  errors.Join() 没有参数:== nil → %v;errors.Join(errs[:0]...) == nil → %v\n", errors.Join() == nil, errors.Join(errs[:0]...) == nil)

	fmt.Println("== 四:成本")
	for _, n := range []int{2, 10} {
		es := make([]error, n)
		for i := range es { es[i] = ErrA }
		fmt.Printf("  errors.Join %d 个错误:AllocsPerRun %.0f 次;Error() 的 AllocsPerRun %.0f 次\n", n, testing.AllocsPerRun(1000, func() { _ = errors.Join(es...) }), testing.AllocsPerRun(1000, func() { _ = errors.Join(es...).Error() }))
	}
	jj := errors.Join(ErrA, ErrB)
	bench("errors.Is(Join(ErrA, ErrB), ErrB)", func(b *testing.B) { for i := 0; i < b.N; i++ { _ = errors.Is(jj, ErrB) } })
	bench("errors.Join(ErrA, ErrB)", func(b *testing.B) { for i := 0; i < b.N; i++ { _ = errors.Join(ErrA, ErrB) } })
	_ = sort.Ints
}
''' + GBENCH
print('== 一:errors.Join 的基本行为(Go 1.27.1)')
r = grun('ej1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
