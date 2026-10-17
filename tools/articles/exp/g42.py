import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g42')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/'
print('== 一:size class 表(internal/runtime/gc/sizeclasses.go 开头的注释与常量,原样)')
o = subprocess.run(['sed', '-n', '6,16p', base + 'internal/runtime/gc/sizeclasses.go'], capture_output=True, text=True).stdout.rstrip()
for l in o.split('\n'): print('  ' + l)
print('  ……(共 68 个 class,最后几行)')
o = subprocess.run(['sed', '-n', '70,76p', base + 'internal/runtime/gc/sizeclasses.go'], capture_output=True, text=True).stdout.rstrip()
for l in o.split('\n'): print('  ' + l)
o = subprocess.run(['grep', '-n', '-E', 'MaxSmallSize +=|NumSizeClasses +=|TinySize +=|PageShift +=|PageSize +=', base + 'internal/runtime/gc/sizeclasses.go'], capture_output=True, text=True).stdout.rstrip()
for l in o.split('\n'): print('  ' + l.strip())
o = subprocess.run(['grep', '-n', 'MinSizeForMallocHeader\\|MallocHeaderSize +=', base + 'internal/runtime/gc/malloc.go', base + 'internal/runtime/gc/sizeclasses.go'], capture_output=True, text=True).stdout.rstrip()
for l in o.split('\n')[:3]: print('  ' + l.replace(base, ''))

SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sort"
	"strconv"
	"testing"
)

var sinkB [][]byte
var sinkP []*[16]*int
var sinkAny []any

type T24 struct{ a, b, c int64 }
type T12 struct{ a, b, c int32 }
type P8 struct{ p *int }
type S504 [63]*int
type S512 [64]*int
type S520 [65]*int

func heap() uint64 {
	var m runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&m)
	return m.HeapAlloc
}

func classOf(n int) (size int, count uint64) {
	var m0, m1 runtime.MemStats
	runtime.ReadMemStats(&m0)
	const N = 20000
	keep := make([][]byte, 0, N)
	for i := 0; i < N; i++ { keep = append(keep, make([]byte, n)) }
	runtime.ReadMemStats(&m1)
	sinkB = keep
	best := -1
	for i := range m1.BySize {
		d := m1.BySize[i].Mallocs - m0.BySize[i].Mallocs
		if d > count { count = d; best = i }
	}
	if best >= 0 { size = int(m1.BySize[best].Size) }
	return
}

func main() {
	mode := os.Args[1]
	switch mode {
	case "class":
		for _, n := range []int{1, 8, 9, 16, 17, 25, 33, 49, 65, 100, 200, 600, 1030, 5000, 16000} {
			sz, c := classOf(n)
			fmt.Printf("  请求 %5d 字节 → 落在 %5d 字节的 class(该 class 在这段时间多出 %d 次分配);浪费 %d 字节(%.1f%%)\n", n, sz, c, sz-n, float64(sz-n)*100/float64(sz))
		}
	case "tiny":
		const N = 1_000_000
		// 先量 []any 自己的开销(每个槽 16 字节),后面扣掉
		h0 := heap()
		over := make([]any, N)
		h1 := heap()
		overhead := float64(h1-h0) / N
		runtime.KeepAlive(over)
		fmt.Printf("  []any 自己每个槽占 %.1f 字节(下面的数字已经扣掉)\n", overhead)
		meas := func(label string, mk func() any) {
			h0 := heap()
			keep := make([]any, 0, N)
			for i := 0; i < N; i++ { keep = append(keep, mk()) }
			h1 := heap()
			sinkAny = keep
			fmt.Printf("  %-34s 每个对象占堆约 %.1f 字节\n", label, float64(h1-h0)/N-overhead)
			sinkAny = nil
		}
		meas("new(byte)(1 字节,不含指针)", func() any { return new(byte) })
		meas("new(int32)(4 字节,不含指针)", func() any { return new(int32) })
		meas("new(int64)(8 字节,不含指针)", func() any { return new(int64) })
		meas("new([9]byte)(9 字节,不含指针)", func() any { return new([9]byte) })
		meas("new([12]byte)(12 字节,不含指针)", func() any { return new([12]byte) })
		meas("new(P8)(8 字节,含指针)", func() any { return new(P8) })
		meas("new([16]byte)(16 字节,不含指针)", func() any { return new([16]byte) })
		meas("new([17]byte)(17 字节,不含指针)", func() any { return new([17]byte) })
		meas("new(T24)(24 字节,不含指针)", func() any { return new(T24) })
	case "header":
		const N = 200_000
		h0 := heap()
		over := make([]any, N)
		h1 := heap()
		overhead := float64(h1-h0) / N
		runtime.KeepAlive(over)
		fmt.Printf("  []any 自己每个槽占 %.1f 字节(下面的数字已经扣掉)\n", overhead)
		for _, c := range []struct {
			name string
			mk   func() any
		}{{"[64]*int(512 字节,含指针)", func() any { return new(S512) }}, {"[65]*int(520 字节,含指针)", func() any { return new(S520) }}, {"[72]*int(576 字节,含指针)", func() any { return new([72]*int) }}, {"[72]int(576 字节,不含指针)", func() any { return new([72]int) }}, {"[128]*int(1024 字节,含指针)", func() any { return new([128]*int) }}, {"[128]int(1024 字节,不含指针)", func() any { return new([128]int) }}} {
			h0 := heap()
			keep := make([]any, 0, N)
			for i := 0; i < N; i++ { keep = append(keep, c.mk()) }
			h1 := heap()
			sinkAny = keep
			fmt.Printf("  %-30s 每个对象占堆约 %.1f 字节\n", c.name, float64(h1-h0)/N-overhead)
			sinkAny = nil
		}
	case "large":
		const N = 2000
		for _, n := range []int{32768, 32769, 33000, 40960, 40961, 65536, 100000} {
			h0 := heap()
			keep := make([][]byte, 0, N)
			for i := 0; i < N; i++ { keep = append(keep, make([]byte, n)) }
			h1 := heap()
			sinkB = keep
			per := float64(h1-h0)/N - 24 // 扣掉每个切片头 24 字节
			fmt.Printf("  make([]byte, %6d):每个占堆约 %.0f 字节(= %.2f 个 8 KiB 页)\n", n, per, per/8192)
			sinkB = nil
		}
	case "bench":
		for _, n := range []int{8, 16, 32, 64, 128, 512, 1024, 4096, 16384, 32768, 65536, 262144} {
			n := n
			var xs []float64
			var bytes int64
			for r := 0; r < 5; r++ {
				br := testing.Benchmark(func(b *testing.B) {
					b.ReportAllocs()
					for i := 0; i < b.N; i++ { sinkB = append(sinkB[:0], make([]byte, n)) }
				})
				xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N)); bytes = br.AllocedBytesPerOp()
			}
			sort.Float64s(xs)
			fmt.Printf("  make([]byte, %6d):中位 %8.1f ns/次(最小 %.1f / 最大 %.1f);分配 %s 字节/次\n", n, xs[2], xs[0], xs[4], strconv.FormatInt(bytes, 10))
		}
	}
}
'''
d = gdir('ha1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m, tmo=300):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=tmo)
    return p.stdout.rstrip() or p.stderr[:300]
print('== 二:请求的大小落在哪个 size class(用 MemStats.BySize 在分配前后的差,每个大小分配 2 万个并保留;BySize 只统计到 16 KiB 以下的 class)')
print(run('class'))
print('== 三:tiny 分配器:小于 16 字节且不含指针的对象会被合并进同一个 16 字节块')
print(run('tiny'))
print('== 四:含指针的对象大于 512 字节要多 8 字节的 malloc header')
print(run('header'))
print('== 五:大于 32 KiB 的对象直接从页堆分配,按 8 KiB 页取整')
print(run('large'))
print('== 六:分配成本随大小的变化(每次分配一个 n 字节的切片并丢弃,5 轮取中位数)')
print(run('bench', 600))
print('  ToolTags 里与分配器有关的:' + ' '.join(t for t in go(d, 'list', '-f', '{{context.ToolTags}}')[1].strip('[]').split() if 'malloc' in t))
rc, o = go(d, 'build', '-o', 'app2', env=dict(GOEXPERIMENT='nosizespecializedmalloc')); assert rc == 0, o
p2 = subprocess.run([str(d / 'app2'), 'bench'], capture_output=True, text=True, timeout=600)
print('  同一份代码,GOEXPERIMENT=nosizespecializedmalloc 构建(只列 8 到 1024 字节):')
for l in p2.stdout.split('\n')[:7]: print(l)

print('== 七:分配成本随 size class 并不单调:相邻几个大小(每次分配后直接放进全局变量,5 轮取中位数)')
NM = r"""
package main

import (
	"fmt"
	"sort"
	"testing"
)

var sink2 []byte

func main() {
	for _, n := range []int{64, 80, 96, 112, 120, 128, 144, 192, 256} {
		n := n
		var xs []float64
		for r := 0; r < 5; r++ {
			br := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sink2 = make([]byte, n) } })
			xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N))
		}
		sort.Float64s(xs)
		fmt.Printf("  make([]byte, %3d):中位 %.1f ns/次(最小 %.1f / 最大 %.1f)\n", n, xs[2], xs[0], xs[4])
	}
}
"""
rn = grun('ha2', {'main.go': NM}, timeout=600)
print(rn['out'] if rn['crc'] == 0 else rn['cout'])
