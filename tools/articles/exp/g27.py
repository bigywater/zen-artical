import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g27')
SRC = r'''
package main

import (
	"bytes"
	"fmt"
	"math"
	"runtime"
	"unsafe"
)

var sinkHeap *[8]int

type Rec struct {
	A int8
	B int64
	C int16
}

//go:noinline
func grow(n int) int {
	var pad [512]byte
	pad[0] = byte(n)
	if n == 0 { return int(pad[0]) }
	return grow(n-1) + int(pad[0])
}

//go:noinline
func stackDemo() {
	x := 42
	oldAddr := uintptr(unsafe.Pointer(&x))
	p := unsafe.Pointer(&x)
	grow(2000) // 递归增长 goroutine 栈,运行时会把整个栈拷贝到新位置
	fmt.Printf("  局部变量 x 的地址:增长前(用 uintptr 保存)0x%x;增长后(取 &x)0x%x;不相等?%v(栈被搬走了,x 跟着搬)\n", oldAddr&0xffff, uintptr(unsafe.Pointer(&x))&0xffff, oldAddr != uintptr(unsafe.Pointer(&x)))
	fmt.Printf("  用增长前保存的 unsafe.Pointer p 读 x:%d(运行时在拷贝栈时把 p 也改写了);p == &x?%v\n", *(*int)(p), p == unsafe.Pointer(&x))
}

func main() {
	f := 1.5
	bits := *(*uint64)(unsafe.Pointer(&f))
	fmt.Printf("  模式 1:*(*uint64)(unsafe.Pointer(&f)) = 0x%x;math.Float64bits(f) = 0x%x;相等?%v\n", bits, math.Float64bits(f), bits == math.Float64bits(f))

	arr := [4]int32{10, 20, 30, 40}
	p2 := (*int32)(unsafe.Add(unsafe.Pointer(&arr[0]), 8))
	p3 := (*int32)(unsafe.Pointer(uintptr(unsafe.Pointer(&arr[0])) + unsafe.Sizeof(arr[0])*3))
	fmt.Printf("  模式 3:unsafe.Add(&arr[0], 8) → %d;uintptr(&arr[0]) + 3*Sizeof → %d(都在一个表达式里完成,合法)\n", *p2, *p3)

	var r Rec
	fmt.Printf("  unsafe.Offsetof:A = %d、B = %d、C = %d;Sizeof(Rec) = %d;Alignof(Rec) = %d\n", unsafe.Offsetof(r.A), unsafe.Offsetof(r.B), unsafe.Offsetof(r.C), unsafe.Sizeof(r), unsafe.Alignof(r))
	r.C = 7
	pc := (*int16)(unsafe.Add(unsafe.Pointer(&r), unsafe.Offsetof(r.C)))
	fmt.Printf("  用 Offsetof 访问字段:*pc = %d(r.C = 7)\n", *pc)

	bs := []byte("hello")
	s := unsafe.String(&bs[0], len(bs))
	sl := unsafe.Slice(unsafe.StringData(s), len(s))
	fmt.Printf("  unsafe.String / unsafe.Slice / unsafe.StringData:s = %q,sl 长度 %d\n", s, len(sl))

	fmt.Println("== 二:uintptr 不是引用:goroutine 栈会被搬动,堆对象(当前实现)不会")
	stackDemo()
	h := new([8]int)
	sinkHeap = h // 赋给全局变量,h 指向的对象逃逸到堆上
	addr := uintptr(unsafe.Pointer(h))
	for i := 0; i < 3; i++ { runtime.GC() }
	fmt.Printf("  堆上对象(逃逸到堆):3 次 GC 之后地址不变?%v(当前实现的 GC 不移动堆对象,但语言规范不保证)\n", addr == uintptr(unsafe.Pointer(h)))
	y := 7
	yAddr := uintptr(unsafe.Pointer(&y))
	for i := 0; i < 3; i++ { runtime.GC() }
	fmt.Printf("  栈上的局部变量(不逃逸):3 次 GC 之后地址不变?%v\n", yAddr == uintptr(unsafe.Pointer(&y)))

	fmt.Println("== 三:窥探未导出字段(依赖标准库内部布局,脆弱):bytes.Buffer 的第一个字段是底层 []byte")
	var buf bytes.Buffer
	buf.WriteString("peek")
	inner := *(*[]byte)(unsafe.Pointer(&buf))
	fmt.Printf("  *(*[]byte)(unsafe.Pointer(&buf)) = %q(长度 %d,容量 %d);buf.Len() = %d,buf.Cap() = %d\n", inner, len(inner), cap(inner), buf.Len(), buf.Cap())
	_ = runtime.GOOS
}
'''
print('== 一:合法的几种用法(Go 1.27.1,arm64)')
r = grun('up1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 四:go vet 的 unsafeptr 检查与 checkptr 运行时检查')
CASES = {
 'uintptr 存进变量再转回指针(两条语句,且先做了加法)': r"""
package main

import (
	"fmt"
	"unsafe"
)

var sink any

func main() {
	b := make([]byte, 16)
	sink = b
	u := uintptr(unsafe.Pointer(&b[0]))
	u += 8
	p := (*byte)(unsafe.Pointer(u))
	fmt.Println(*p)
}
""",
 '未对齐的转换:b 在堆上,从 b[1] 起转成 *[1]*int(元素含指针)': r"""
package main

import (
	"fmt"
	"unsafe"
)

var sink any

func main() {
	b := make([]byte, 16)
	sink = b
	q := (*[1]*int)(unsafe.Pointer(&b[1]))
	fmt.Println(q[0])
}
""",
 '同样的未对齐转换,但目标是 *int64(元素不含指针)': r"""
package main

import (
	"fmt"
	"unsafe"
)

var sink any

func main() {
	b := make([]byte, 16)
	sink = b
	q := (*int64)(unsafe.Pointer(&b[1]))
	fmt.Println(*q)
}
""",
 'unsafe.Add 越过堆上 16 字节切片末尾 100 字节': r"""
package main

import (
	"fmt"
	"unsafe"
)

var sink any

func main() {
	b := make([]byte, 16)
	sink = b
	p := (*byte)(unsafe.Add(unsafe.Pointer(&b[0]), 100))
	fmt.Println(*p)
}
""",
 '把堆上的 *[4]byte 转成 *[8]byte(越过原对象)': r"""
package main

import (
	"fmt"
	"unsafe"
)

var sink any

func main() {
	a := new([4]byte)
	sink = a
	q := (*[8]byte)(unsafe.Pointer(a))
	fmt.Println(q[7])
}
""",
}
for title, code in CASES.items():
    dd = gdir('upc'); write(dd, {'main.go': code}); mod(dd)
    rc, o = go(dd, 'vet', '.')
    vetl = [l.replace('./main.go', 'main.go') for l in o.split('\n') if 'main.go' in l]
    res = []
    for label, args in [('默认', []), ('checkptr', ['-gcflags=all=-d=checkptr=1'])]:
        go(dd, 'build', '-o', 'app', *args)
        pr_ = subprocess.run([str(dd / 'app')], capture_output=True, text=True)
        first = [re.sub(r'0x[0-9a-f]+', '0x…', l) for l in (pr_.stdout + pr_.stderr).split('\n') if l.strip()][:1]
        res.append(f'{label}:退出码 {pr_.returncode},{first[0] if first else ""}')
    print(f'  {title}:')
    print('    go vet:' + (vetl[0] if vetl else '无警告'))
    print('    ' + ';'.join(res))
shutil.rmtree(GT / 'upc', ignore_errors=True)
