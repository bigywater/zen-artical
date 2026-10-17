import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g2')
SRC = r'''
package main

import (
	"bytes"
	"fmt"
	"io"
	"reflect"
	"runtime"
	"unsafe"
)

type eface struct{ typ, data unsafe.Pointer }
type iface struct {
	tab  *itab
	data unsafe.Pointer
}
type itab struct {
	inter, typ unsafe.Pointer
	hash       uint32
	_          [4]byte
	fun        [3]uintptr
}

type T struct{ A, B int }

func (t *T) Sum() int { return t.A + t.B }

type Summer interface{ Sum() int }

type F struct{}

func (F) Write(p []byte) (int, error) { return len(p), nil }
func (F) Read(p []byte) (int, error)  { return 0, io.EOF }
func (F) Close() error                { return nil }

type RWC interface {
	Write([]byte) (int, error)
	Read([]byte) (int, error)
	Close() error
}

func E(v any) eface       { return *(*eface)(unsafe.Pointer(&v)) }
func I(v Summer) iface    { return *(*iface)(unsafe.Pointer(&v)) }
func say(f string, a ...any) { fmt.Printf("  "+f+"\n", a...) }

func main() {
	var a any
	var r io.Reader
	var s Summer
	say("unsafe.Sizeof:any = %d,io.Reader = %d,Summer = %d,*T = %d,T = %d,string = %d,[]int = %d", unsafe.Sizeof(a), unsafe.Sizeof(r), unsafe.Sizeof(s), unsafe.Sizeof(&T{}), unsafe.Sizeof(T{}), unsafe.Sizeof(""), unsafe.Sizeof([]int{}))
	e := E(nil)
	say("零值 any(nil):两个字都是 nil?typ=%v data=%v", e.typ == nil, e.data == nil)

	fmt.Println("== 二:空接口 any 的两个字:类型指针 + 数据指针(用 unsafe 把 any 按 {typ, data} 读出来)")
	a1, a2, a3, a4 := E(42), E(1000), E(1000), E("hi")
	say("any(42) 与 any(1000):类型指针相同?%v;any(1000) 与 any(\"hi\"):%v", a1.typ == a2.typ, a2.typ == a4.typ)
	say("any(42):*(*int)(data) = %d;any(1000):*(*int)(data) = %d;两个 any(1000) 的 data 指针相同?%v(两个值各有自己的一份数据)", *(*int)(a1.data), *(*int)(a2.data), a2.data == a3.data)
	say("any(\"hi\"):data 指向字符串头(ptr,len):len = %d,内容 %q", len(*(*string)(a4.data)), *(*string)(a4.data))
	p := &T{1, 2}
	ep := E(p)
	say("any(&T):data 指针 == 原指针 p?%v(指针类型直接把指针放进 data 字,不再多一层)", ep.data == unsafe.Pointer(p))
	v := T{1, 2}
	var av any = v
	v.A = 100
	ev := *(*eface)(unsafe.Pointer(&av))
	say("var av any = v(T 值);之后 v.A = 100:v.A = %d,接口里的拷贝 %+v;data 指针 == &v?%v;类型字等于 *T 的类型字?%v", v.A, *(*T)(ev.data), ev.data == unsafe.Pointer(&v), ev.typ == ep.typ)

	fmt.Println("== 三:带方法的接口 iface:第一个字是 itab 指针,itab 里记着(接口类型, 动态类型, 方法地址)")
	s1, s2 := I(&T{1, 2}), I(&T{3, 4})
	say("两个 Summer 都装着 *T:itab 指针相同?%v;itab.typ 等于 any(&T) 的类型字?%v", s1.tab == s2.tab, s1.tab.typ == ep.typ)
	fn := runtime.FuncForPC(s1.tab.fun[0])
	say("itab.fun[0] 指向的函数名:%s", fn.Name())
	rm := reflect.TypeOf(&T{}).Method(0).Func.Pointer()
	say("reflect 取到的 (*T).Sum 地址 == itab.fun[0]?%v", rm == s1.tab.fun[0])
	var rw1 io.Reader = &bytes.Buffer{}
	var rw2 io.ReadWriter = &bytes.Buffer{}
	t1 := (*iface)(unsafe.Pointer(&rw1)).tab
	t2 := (*iface)(unsafe.Pointer(&rw2)).tab
	say("同一个动态类型 *bytes.Buffer,装进 io.Reader 与 io.ReadWriter:itab 指针相同?%v;itab.typ 相同?%v;itab.inter 相同?%v", t1 == t2, t1.typ == t2.typ, t1.inter == t2.inter)
	var rwc RWC = F{}
	tr := (*iface)(unsafe.Pointer(&rwc)).tab
	for i := 0; i < 3; i++ { say("RWC 的 itab.fun[%d] → %s", i, runtime.FuncForPC(tr.fun[i]).Name()) }
}
'''
print('== 一:接口值有多大:两个机器字(Go 1.27.1,arm64)')
r = grun('if1', {'main.go': SRC})  # 源码里的 fmt.Println("== ...") 打印的是第二、三节的标题,运行输出原样打印
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 四:itab 是什么时候造出来的:源码里能静态确定的转换,编译器直接引用链接时生成的 go:itab 符号;运行时才知道类型的断言要走 runtime')
P4 = r'''
package main

import (
	"fmt"
	"testing"
)

type T struct{ A, B int }

func (t *T) Sum() int { return t.A + t.B }

type Summer interface{ Sum() int }

//go:noinline
func static(t *T) Summer { return t }

//go:noinline
func dynamic(x any) Summer { return x.(Summer) }

func main() {
	x := any(&T{3, 4})
	fmt.Println(static(&T{1, 2}).Sum(), dynamic(x).Sum())
	fmt.Printf("  dynamic(x) 稳态每次调用的分配次数:%.0f\n", testing.AllocsPerRun(1000, func() { dynamic(x) }))
}
'''
r = grun('if4', {'main.go': P4}, gcflags='-S')
blocks = re.split(r'\n(?=main\.\w+ STEXT)', r['cout'])
for fn in ('static', 'dynamic'):
    b = [x for x in blocks if x.startswith(f'main.{fn} STEXT')][0]
    ls = [re.sub(r'^\s*0x[0-9a-f]+ \d+ \(', '(', l).replace('<gtmp>/if4/', '') for l in b.split('\n') if not l.strip().startswith('rel ') and 'morestack' not in l and (('go:itab' in l) or 'CALL' in l)]
    print(f'  main.{fn} 的汇编里与接口有关的指令(go build -gcflags=-S):')
    for l in ls: print('    ' + l.strip()[:150])
print('  ' + (r['out'] if r['crc'] == 0 else r['cout']).replace('\n', '\n  '))

print('== 五:通过接口调用比直接调用慢多少:testing.Benchmark,callee 都是 //go:noinline,每个变体 7 轮取中位数;最后两行对比“接口里全是同一种类型”与“4 种类型伪随机排列”(分支预测)')
BEN = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
)

type T struct{ A, B int }

//go:noinline
func (t *T) Sum() int { return t.A + t.B }

type Summer interface{ Sum() int }

type U struct{ A, B int }
type V struct{ A, B int }
type W struct{ A, B int }

//go:noinline
func (t *U) Sum() int { return t.A - t.B }

//go:noinline
func (t *V) Sum() int { return t.A * t.B }

//go:noinline
func (t *W) Sum() int { return t.A ^ t.B }

//go:noinline
func direct(t *T) int { return t.Sum() }

//go:noinline
func viaIface(s Summer) int { return s.Sum() }

var sink int

func bench(name string, f func(b *testing.B)) {
	var xs []float64
	for i := 0; i < 7; i++ { br := testing.Benchmark(f); xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)) }
	sort.Float64s(xs)
	fmt.Printf("  %-22s 中位 %.2f ns/op(最小 %.2f / 最大 %.2f)\n", name, xs[3], xs[0], xs[6])
}

func main() {
	t := &T{1, 2}
	var s Summer = t
	bench("直接调用 t.Sum()", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += direct(t) } })
	bench("经接口 s.Sum()", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += viaIface(s) } })
	const N = 4096
	same, mixed := make([]Summer, N), make([]Summer, N)
	x := uint32(2463534242)
	for i := range same {
		same[i] = &T{1, 2}
		x ^= x << 13; x ^= x >> 17; x ^= x << 5
		switch x % 4 {
		case 0: mixed[i] = &T{1, 2}
		case 1: mixed[i] = &U{1, 2}
		case 2: mixed[i] = &V{1, 2}
		default: mixed[i] = &W{1, 2}
		}
	}
	bench("4096 个同类型,逐个调用", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += same[i%N].Sum() } })
	bench("4096 个 4 类型随机,逐个调用", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += mixed[i%N].Sum() } })
}
'''
r = grun('if2', {'main.go': BEN}); print(r['out'] if r['crc'] == 0 else r['cout'])
