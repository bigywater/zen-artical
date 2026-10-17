import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g5')
SRC = r'''
package main

import (
	"fmt"
	"runtime"
	"strings"
	"testing"
	"unsafe"
)

var sinkB []byte
var sinkS string
var sinkN int

//go:noinline
func toBytesRead(s string) int { x := []byte(s); return int(x[len(x)/2]) }

//go:noinline
func toStringRead(b []byte) int { x := string(b); return int(x[len(x)/2]) }

type strHdr struct {
	ptr unsafe.Pointer
	len int
}

func main() {
	s := "hello, world"
	h := (*strHdr)(unsafe.Pointer(&s))
	fmt.Printf("  unsafe.Sizeof(string) = %d;len(s) = %d;头里的 len = %d;StringData(s) == 头里的 ptr?%v\n", unsafe.Sizeof(s), len(s), h.len, unsafe.StringData(s) == (*byte)(h.ptr))
	sub := s[7:10]
	fmt.Printf("  sub := s[7:10] = %q:StringData(sub) - StringData(s) = %d 字节(共用同一块内存);len(sub) = %d\n", sub, uintptr(unsafe.Pointer(unsafe.StringData(sub)))-uintptr(unsafe.Pointer(unsafe.StringData(s))), len(sub))
	cl := strings.Clone(sub)
	fmt.Printf("  strings.Clone(sub):StringData 与 sub 相同?%v(拷贝了一份)\n", unsafe.StringData(cl) == unsafe.StringData(sub))
	a, b := "same-literal", "same-literal"
	fmt.Printf("  两个相同的字符串字面量:StringData 相同?%v;运行时拼出来的同内容字符串:相同?%v\n", unsafe.StringData(a) == unsafe.StringData(b), unsafe.StringData(strings.Repeat("x", 5)) == unsafe.StringData(strings.Repeat("x", 5)))

	fmt.Println("== 二:string 与 []byte 互转:内容真的拷贝了吗(改一边看另一边)")
	bs := []byte("abc")
	s2 := string(bs)
	bs[0] = 'X'
	fmt.Printf("  b := []byte(\"abc\");s := string(b);改 b[0] = 'X' 之后:b = %q,s = %q(s 不变:string(b) 拷贝了)\n", bs, s2)
	s3 := "abc"
	b3 := []byte(s3)
	b3[0] = 'Y'
	fmt.Printf("  s := \"abc\";b := []byte(s);改 b[0] = 'Y' 之后:s = %q,b = %q(s 不变:[]byte(s) 拷贝了)\n", s3, b3)
	b4 := []byte("abc")
	s4 := unsafe.String(&b4[0], len(b4))
	b4[0] = 'Z'
	fmt.Printf("  unsafe.String(&b[0], len(b)) 不拷贝:改 b[0] = 'Z' 之后 s = %q(跟着变了;只在你保证之后不再改 b 时才能用)\n", s4)
	b5 := unsafe.Slice(unsafe.StringData(s3), len(s3))
	fmt.Printf("  unsafe.Slice(unsafe.StringData(s), len(s)) 得到 %d 字节的 []byte,cap = %d(指向字符串自己的内存;下面单独试写入)\n", len(b5), cap(b5))

	fmt.Println("== 三:什么时候真的分配:testing.AllocsPerRun,字符串 100 字节(超过 32 字节)与 10 字节(不超过)")
	long := strings.Repeat("a", 100)
	short := strings.Repeat("a", 10)
	lb := []byte(long)
	sb := []byte(short)
	m := map[string]int{long: 1, short: 2}
	row := func(name string, f func()) { fmt.Printf("  %-52s %2.0f 次\n", name, testing.AllocsPerRun(1000, f)) }
	row("b := []byte(long)  结果逃逸(赋给全局)", func() { sinkB = []byte(long) })
	row("b := []byte(long)  不逃逸,只读 len(b)", func() { x := []byte(long); sinkN += len(x) })
	row("b := []byte(long)  不逃逸,读 b[50]", func() { x := []byte(long); sinkN += int(x[50]) })
	row("b := []byte(short) 不逃逸,读 b[5]", func() { x := []byte(short); sinkN += int(x[5]) })
	row("s := string(lb)    结果逃逸(赋给全局)", func() { sinkS = string(lb) })
	row("s := string(lb100) 不逃逸,读 s[50]", func() { x := string(lb); sinkN += int(x[50]) })
	row("s := string(sb10)  不逃逸,读 s[5]", func() { x := string(sb); sinkN += int(x[5]) })
	row("m[string(lb)]      用 []byte 当 map 的键查找", func() { sinkN += m[string(lb)] })
	row("string(lb) == long 比较", func() { if string(lb) == long { sinkN++ } })
	row("for range []byte(long) 只遍历", func() { for _, c := range []byte(long) { sinkN += int(c) } })
	row("\"x\" + string(lb)   拼接(结果赋给全局)", func() { sinkS = "x" + string(lb) })
	row("strings.Clone(long)", func() { sinkS = strings.Clone(long) })
	for _, n := range []int{10, 32, 33, 100, 1000} {
		st := strings.Repeat("a", n)
		bt := []byte(st)
		fmt.Printf("  经函数参数(不会被当成常量),不逃逸:[]byte(s) 与 string(b) 各 %4d 字节:%.0f 次 / %.0f 次\n", n, testing.AllocsPerRun(1000, func() { sinkN += toBytesRead(st) }), testing.AllocsPerRun(1000, func() { sinkN += toStringRead(bt) }))
	}

	fmt.Println("== 四:子串会拖住整块内存:切 10 MiB 字符串的前 5 个字节,GC 之后看堆")
	heap := func() float64 {
		runtime.GC()
		var ms runtime.MemStats
		runtime.ReadMemStats(&ms)
		return float64(ms.HeapAlloc) / (1 << 20)
	}
	base := heap()
	big := strings.Repeat("0123456789", 1<<20)
	keep := big[:5]
	big = ""
	withBig := heap()
	fmt.Printf("  基线 HeapAlloc %.2f MiB;分配 10 MiB 字符串后只留 big[:5]:HeapAlloc %.2f MiB(len(keep) = %d,但 10 MiB 仍被 keep 引用)\n", base, withBig, len(keep))
	keep = strings.Clone(keep)
	after := heap()
	fmt.Printf("  keep = strings.Clone(keep) 之后再 GC:HeapAlloc %.2f MiB(大块可以回收)\n", after)
	runtime.KeepAlive(keep)
}
'''
print('== 一:字符串的内部结构:一个 {指针, 长度} 头(Go 1.27.1,arm64;用 unsafe 读)')
r = grun('st1', {'main.go': SRC})
CR = r"""
package main

import "unsafe"

func main() {
	s := "abc"
	b := unsafe.Slice(unsafe.StringData(s), len(s))
	b[0] = 'Z'
	println("没有崩溃:", string(b))
}
"""
rc = grun('st2', {'main.go': CR})
crash = f'  往 unsafe.Slice(StringData("abc")) 里写 b[0]:rc={rc["rc"]};' + ' / '.join(re.sub(r'0x[0-9a-f]+', '0x…', l.strip()) for l in rc['out'].split('\n')[:3] if l.strip())
head, _, rest = r['out'].partition('\n== 三')
print(head); print(crash); print('== 三' + rest)
ZC = r"""
package main

import (
	"fmt"
	"strings"
	"testing"
)

var sinkN int

//go:noinline
func toBytesRead(s string) int { x := []byte(s); return int(x[len(x)/2]) }

//go:noinline
func toBytesWrite(s string) int { x := []byte(s); x[0] = 1; return int(x[len(x)/2]) }

func main() {
	for _, n := range []int{10, 32, 33, 1000} {
		st := strings.Repeat("a", n)
		fmt.Printf("  %4d 字节:只读版本 %.0f 次,写入版本(x[0] = 1)%.0f 次\n", n, testing.AllocsPerRun(1000, func() { sinkN += toBytesRead(st) }), testing.AllocsPerRun(1000, func() { sinkN += toBytesWrite(st) }))
	}
}
"""
print('== 五:[]byte(s) 为什么有时不拷贝:编译器发现结果从不被修改,就直接复用字符串的内存(-gcflags=-m 里叫 zero-copy)')
for label, fl in [('默认', '-m'), ('-gcflags=-m -d=zerocopy=0(关掉这项优化)', '-m -d=zerocopy=0')]:
    rz = grun('st3', {'main.go': ZC}, gcflags=fl)
    print(f'  {label}:')
    for l in gdiag(rz['cout'], ZC, keep=('zero-copy', 'does not escape', 'escapes')).split('\n'):
        if l and int(re.search(r'main\.go:(\d+)', l).group(1)) < 15: print('  ' + l)
    print('  ' + (rz['out'] if rz['crc'] == 0 else rz['cout']).replace('\n', '\n  '))
