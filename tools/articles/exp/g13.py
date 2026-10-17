import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g13')
SRC = r'''
package main

import (
	"fmt"
	"reflect"
	"sort"
	"testing"
	"unsafe"
)

type Bad struct {
	a bool
	b int64
	c bool
	d int32
	e bool
}

type Good struct {
	b int64
	d int32
	a bool
	c bool
	e bool
}

type ZeroTail struct {
	a int64
	z struct{}
}

type ZeroHead struct {
	z struct{}
	a int64
}

func layout(v any) {
	t := reflect.TypeOf(v)
	fmt.Printf("  %s:Sizeof = %d,Alignof = %d\n", t.Name(), t.Size(), t.Align())
	prev := uintptr(0)
	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)
		pad := ""
		if f.Offset > prev { pad = fmt.Sprintf("(前面填充 %d 字节)", f.Offset-prev) }
		fmt.Printf("    %-2s %-6s offset %2d size %d align %d %s\n", f.Name, f.Type, f.Offset, f.Type.Size(), f.Type.Align(), pad)
		prev = f.Offset + f.Type.Size()
	}
	if prev < t.Size() { fmt.Printf("    (末尾填充 %d 字节)\n", t.Size()-prev) }
}

var sink int32

func main() {
	layout(Bad{})
	layout(Good{})

	fmt.Println("== 二:常见类型的大小与对齐(arm64)")
	rows := []struct {
		name string
		sz   uintptr
		al   uintptr
	}{
		{"bool", unsafe.Sizeof(true), unsafe.Alignof(true)},
		{"int16", unsafe.Sizeof(int16(0)), unsafe.Alignof(int16(0))},
		{"int32", unsafe.Sizeof(int32(0)), unsafe.Alignof(int32(0))},
		{"int64", unsafe.Sizeof(int64(0)), unsafe.Alignof(int64(0))},
		{"float32", unsafe.Sizeof(float32(0)), unsafe.Alignof(float32(0))},
		{"complex128", unsafe.Sizeof(complex128(0)), unsafe.Alignof(complex128(0))},
		{"string", unsafe.Sizeof(""), unsafe.Alignof("")},
		{"[]int", unsafe.Sizeof([]int{}), unsafe.Alignof([]int{})},
		{"any", unsafe.Sizeof(any(0)), unsafe.Alignof(any(0))},
		{"map[int]int", unsafe.Sizeof(map[int]int{}), unsafe.Alignof(map[int]int{})},
		{"[3]byte", unsafe.Sizeof([3]byte{}), unsafe.Alignof([3]byte{})},
		{"struct{}", unsafe.Sizeof(struct{}{}), unsafe.Alignof(struct{}{})},
	}
	for _, r := range rows { fmt.Printf("  %-12s Sizeof %2d  Alignof %d\n", r.name, r.sz, r.al) }

	fmt.Println("== 三:零大小字段放在末尾会多占空间")
	layout(ZeroTail{})
	layout(ZeroHead{})

	fmt.Println("== 四:100 万个元素的切片:内存与遍历耗时(只读 d 字段求和,7 轮取中位数)")
	const N = 1_000_000
	bad := make([]Bad, N)
	good := make([]Good, N)
	fmt.Printf("  []Bad  %d 字节 × %d = %.1f MiB;[]Good %d 字节 × %d = %.1f MiB;省 %.1f%%\n", unsafe.Sizeof(Bad{}), N, float64(N*int(unsafe.Sizeof(Bad{})))/(1<<20), unsafe.Sizeof(Good{}), N, float64(N*int(unsafe.Sizeof(Good{})))/(1<<20), 100-float64(unsafe.Sizeof(Good{}))*100/float64(unsafe.Sizeof(Bad{})))
	bench("遍历 []Bad 求和 d", func(b *testing.B) { for i := 0; i < b.N; i++ { var s int32; for j := range bad { s += bad[j].d }; sink += s } })
	bench("遍历 []Good 求和 d", func(b *testing.B) { for i := 0; i < b.N; i++ { var s int32; for j := range good { s += good[j].d }; sink += s } })
	_ = sort.Ints
}
''' + GBENCH
print('== 一:字段顺序不同,结构体大小不同:同样的 5 个字段(Go 1.27.1,arm64)')
r = grun('sp1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 五:同一个结构体在不同 GOARCH 上的大小与偏移(用标准库 go/types 的 gc 规则计算,不运行 386 程序)')
TY = r'''
package main

import (
	"fmt"
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
)

const src = `package p
type Bad struct { a bool; b int64; c bool; d int32; e bool }
type Good struct { b int64; d int32; a bool; c bool; e bool }
`

func main() {
	fset := token.NewFileSet()
	f, _ := parser.ParseFile(fset, "p.go", src, 0)
	_ = ast.Inspect
	for _, arch := range []string{"amd64", "arm64", "386", "arm"} {
		conf := types.Config{Importer: importer.Default(), Sizes: types.SizesFor("gc", arch)}
		pkg, err := conf.Check("p", fset, []*ast.File{f}, nil)
		if err != nil { fmt.Println(err); return }
		for _, n := range []string{"Bad", "Good"} {
			st := pkg.Scope().Lookup(n).Type().Underlying().(*types.Struct)
			var fs []*types.Var
			for i := 0; i < st.NumFields(); i++ { fs = append(fs, st.Field(i)) }
			offs := conf.Sizes.Offsetsof(fs)
			fmt.Printf("  GOARCH=%-5s %-4s Sizeof = %2d,Alignof = %d,各字段偏移 %v\n", arch, n, conf.Sizes.Sizeof(st), conf.Sizes.Alignof(st), offs)
		}
	}
}
'''
r5 = grun('sp2', {'main.go': TY})
print(r5['out'] if r5['crc'] == 0 else r5['cout'])

print('== 六:fieldalignment(golang.org/x/tools v0.51.0 的分析器)对这两个结构体与一个更大的例子的报告')
FA = r'''
package p

type Bad struct {
	a bool
	b int64
	c bool
	d int32
	e bool
}

type Good struct {
	b int64
	d int32
	a bool
	c bool
	e bool
}

type Mixed struct {
	flag  bool
	name  string
	id    int32
	ptr   *int
	ok    bool
	count int64
}
'''
d = gdir('sp3'); write(d, {'p.go': FA}); mod(d)
rc, o = go(d, 'vet', '-vettool=' + str(GT / '_bin' / 'fieldalignment'), './...')
print(f'  go vet -vettool=fieldalignment:rc={rc}')
for l in o.split('\n'):
    if 'p.go' in l: print('  ' + l.replace('./p.go', 'p.go'))
