import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g63')
SRC = r'''
package main

import (
	"bytes"
	"fmt"
	"os"
	"runtime"
	"sync"
	"testing"
)

type item struct{ id int }

var sinkB []byte

func main() {
	runtime.GOMAXPROCS(4)
	switch os.Args[1] {
	case "survive":
		for _, gcs := range []int{0, 1, 2, 3} {
			next := 0
			p := sync.Pool{New: func() any { next++; return &item{id: -next} }}
			held := make([]*item, 0, 100)
			for i := 1; i <= 100; i++ { held = append(held, &item{id: i}) }
			for _, it := range held { p.Put(it) }
			held = nil
			for i := 0; i < gcs; i++ { runtime.GC() }
			// 把池里能取到的都取出来:取到 id>0 的是原来放进去的,id<0 是 New 新造的
			old, fresh := 0, 0
			for i := 0; i < 100; i++ {
				it := p.Get().(*item)
				if it.id > 0 { old++ } else { fresh++ }
			}
			fmt.Printf("  放入 100 个对象,然后 runtime.GC() %d 次,再 Get 100 次:取到原来的 %d 个,New 新造 %d 个\n", gcs, old, fresh)
		}
	case "bench":
		var p = sync.Pool{New: func() any { return new(bytes.Buffer) }}
		work := func(b *bytes.Buffer) { b.Write(make([]byte, 0)); for i := 0; i < 64; i++ { b.WriteString("0123456789abcdef0123456789abcdef") } }
		r1 := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ { var buf bytes.Buffer; work(&buf); sinkB = buf.Bytes() }
		})
		r2 := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ { buf := p.Get().(*bytes.Buffer); buf.Reset(); work(buf); sinkB = buf.Bytes(); p.Put(buf) }
		})
		r3 := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			b.RunParallel(func(pb *testing.PB) { for pb.Next() { var buf bytes.Buffer; work(&buf); sinkB = buf.Bytes() } })
		})
		r4 := testing.Benchmark(func(b *testing.B) {
			b.ReportAllocs()
			b.RunParallel(func(pb *testing.PB) { for pb.Next() { buf := p.Get().(*bytes.Buffer); buf.Reset(); work(buf); sinkB = buf.Bytes(); p.Put(buf) } })
		})
		for _, r := range []struct{ n string; r testing.BenchmarkResult }{{"每次新建 bytes.Buffer(单 goroutine)", r1}, {"sync.Pool 复用(单 goroutine)", r2}, {"每次新建(4 个 P 并行)", r3}, {"sync.Pool 复用(4 个 P 并行)", r4}} {
			fmt.Printf("  %-34s %6d ns/次  %6d B/次  %d 次分配/次\n", r.n, r.r.NsPerOp(), r.r.AllocedBytesPerOp(), r.r.AllocsPerOp())
		}
	case "gccount":
		for _, usePool := range []bool{false, true} {
			var p = sync.Pool{New: func() any { b := make([]byte, 4096); return &b }}
			var m0, m1 runtime.MemStats
			runtime.GC(); runtime.ReadMemStats(&m0)
			for i := 0; i < 2_000_000; i++ {
				if usePool { b := p.Get().(*[]byte); (*b)[0] = 1; p.Put(b) } else { b := make([]byte, 4096); b[0] = 1; sinkB = b }
			}
			runtime.ReadMemStats(&m1)
			fmt.Printf("  200 万次借用 4 KiB 缓冲区,%s:GC %d 次,累计分配 %.0f MB\n", map[bool]string{true: "用 sync.Pool", false: "每次 make"}[usePool], m1.NumGC-m0.NumGC, float64(m1.TotalAlloc-m0.TotalAlloc)/1e6)
		}
	case "boxing":
		var p sync.Pool
		s := make([]byte, 16)
		fmt.Printf("  Put([]byte)(把切片本身放进去):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { p.Put(s) }))
		fmt.Printf("  Put(&s)(放指针):每次 %.0f 次分配\n", testing.AllocsPerRun(1000, func() { p.Put(&s) }))
	}
}
'''
d = gdir('pl1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return (p.stdout + p.stderr).rstrip()
print('== 一:池里的对象能活过几次 GC?(Go 1.27.1,arm64 macOS,GOMAXPROCS=4)')
print(run('survive'))
print('== 二:放进去的是什么也有成本:把切片本身放进池 vs 放指针')
print(run('boxing'))
print('== 三:复用 bytes.Buffer 值不值得(每次写约 2 KB)')
print(run('bench'))
print('== 四:对 GC 的影响:200 万次借用 4 KiB 缓冲区')
print(run('gccount'))
print('== 五:源码(sync/pool.go poolCleanup,每次 GC 开头 STW 时调用)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/sync/pool.go'
n = int(subprocess.run(['grep', '-n', '// Drop victim caches from all pools.', base], capture_output=True, text=True).stdout.split(':')[0])
for l in subprocess.run(['sed', '-n', f'{n - 1},{n + 14}p', base], capture_output=True, text=True).stdout.rstrip().split('\n'): print('  ' + l.replace('\t', '    '))
r, o = go(gdir('doc1'), 'doc', 'sync.Pool')
for l in o.split('\n'):
    if 'removed automatically at any time' in l or 'may be individually saved' in l: print('  文档:' + l.strip())
