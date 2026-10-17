import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g43')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"runtime/metrics"
	"strconv"
	"sync"
	"time"
	"unsafe"
)

func stackBytes() uint64 {
	s := []metrics.Sample{{Name: "/memory/classes/heap/stacks:bytes"}}
	metrics.Read(s)
	return s[0].Value.Uint64()
}

//go:noinline
func rec(p unsafe.Pointer, depth, max int, last *uintptr, events *[]string, prevDepth *int) int {
	var pad [64]byte
	pad[depth&63] = byte(depth)
	cur := uintptr(p)
	if *last != 0 && cur != *last {
		*events = append(*events, fmt.Sprintf("深度 %d(距上次搬动 %d 层):地址差 %+d 字节", depth, depth-*prevDepth, int64(cur)-int64(*last)))
		*prevDepth = depth
	}
	*last = cur
	if depth >= max { return int(pad[0]) }
	return rec(p, depth+1, max, last, events, prevDepth) + int(pad[1])
}

//go:noinline
func plain(n int) int {
	var pad [64]byte
	pad[n&63] = byte(n)
	if n == 0 { return int(pad[0]) }
	return plain(n-1) + int(pad[1])
}

func main() {
	mode := os.Args[1]
	switch mode {
	case "perg":
		const N = 100_000
		for _, depth := range []int{0, 20, 200} {
			var wg sync.WaitGroup
			ready := make(chan struct{})
			release := make(chan struct{})
			b0 := stackBytes()
			for i := 0; i < N; i++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					plain(depth)
					ready <- struct{}{}
					<-release
				}()
			}
			for i := 0; i < N; i++ { <-ready }
			b1 := stackBytes()
			fmt.Printf("  每个 goroutine 先递归 %3d 层再阻塞:%d 个 goroutine 的栈内存增加 %.1f MiB → 每个约 %.0f 字节\n", depth, N, float64(b1-b0)/(1<<20), float64(b1-b0)/N)
			close(release)
			wg.Wait()
			runtime.GC(); runtime.GC(); runtime.GC()
		}
	case "growth":
		max, _ := strconv.Atoi(os.Args[2])
		var x int
		p := unsafe.Pointer(&x)
		var last uintptr
		var events []string
		pd := 0
		t0 := time.Now()
		rec(p, 0, max, &last, &events, &pd)
		el := time.Since(t0)
		fmt.Printf("  递归 %d 层:共搬动栈 %d 次,耗时 %.2f ms;前几次搬动:\n", max, len(events), float64(el.Microseconds())/1000)
		for i, e := range events {
			if i < 8 || i >= len(events)-2 { fmt.Println("    " + e) } else if i == 8 { fmt.Println("    ……") }
		}
	case "shrink":
		runtime.GC()
		b0 := stackBytes()
		plain(200_000)
		b1 := stackBytes()
		fmt.Printf("  递归 20 万层之前栈内存 %.1f MiB;递归之后(函数已返回)%.1f MiB\n", float64(b0)/(1<<20), float64(b1)/(1<<20))
		for i := 1; i <= 8; i++ {
			runtime.GC()
			fmt.Printf("    第 %d 次 runtime.GC() 之后:%.2f MiB\n", i, float64(stackBytes())/(1<<20))
		}
	case "cost":
		for rep := 0; rep < 3; rep++ {
			t0 := time.Now()
			plain(100_000)
			t1 := time.Since(t0)
			t0 = time.Now()
			plain(100_000)
			t2 := time.Since(t0)
			fmt.Printf("  第 %d 轮:第一次递归 10 万层 %.2f ms;紧接着第二次 %.2f ms\n", rep+1, float64(t1.Microseconds())/1000, float64(t2.Microseconds())/1000)
			runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC(); runtime.GC()
		}
		var wg sync.WaitGroup
		for _, depth := range []int{10, 100} {
			t0 := time.Now()
			const N = 200_000
			for i := 0; i < N; i++ {
				wg.Add(1)
				go func() { defer wg.Done(); plain(depth) }()
				if i%1000 == 999 { wg.Wait() }
			}
			wg.Wait()
			fmt.Printf("  创建 %d 个 goroutine,每个递归 %d 层后退出:每个 %.0f ns\n", N, depth, float64(time.Since(t0).Nanoseconds())/N)
		}
	case "overflow":
		if len(os.Args) > 2 { n, _ := strconv.Atoi(os.Args[2]); debug.SetMaxStack(n) }
		old := debug.SetMaxStack(0)
		debug.SetMaxStack(old)
		fmt.Println("  max stack =", old)
		plain(1 << 40)
	}
}
'''
d = gdir('sg1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a, tmo=300):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=tmo)
    return p
print('== 一:一个 goroutine 的栈多大:10 万个 goroutine 阻塞在 channel 上,看栈内存的增量(runtime/metrics /memory/classes/heap/stacks:bytes)')
print(run('perg').stdout.rstrip())
print('== 二:栈增长的过程:递归时每一层持有一个指向最底层变量的 unsafe.Pointer,运行时拷贝栈时会改写它,地址一变就说明栈被搬走了')
rc, o = go(d, 'build', '-gcflags=-S', '-o', 'app_s')
hdr = [l for l in o.split('\n') if l.startswith('main.rec STEXT')]
print('  main.rec 的函数头(go build -gcflags=-S):' + re.sub(r'\s+', ' ', hdr[0])[:140] if hdr else '  (没有取到函数头)')
for dep in (100, 5_000, 200_000):
    print(run('growth', dep).stdout.rstrip())
print('== 三:栈会收缩:一次深递归之后函数已返回,栈内存要等 GC 才逐步收回')
print(run('shrink').stdout.rstrip())
print('== 四:栈增长的成本')
print(run('cost').stdout.rstrip())
print('== 五:栈的上限:无限递归会怎样(64 位默认 1 GB;debug.SetMaxStack 可调)')
for args in ((), (1 << 20,)):
    p = run('overflow', *args, tmo=120)
    lines = [re.sub(r'0x[0-9a-f]+', '0x…', l.strip()) for l in (p.stdout + p.stderr).split('\n') if l.strip() and not l.startswith(('\t', 'main.', 'goroutine', 'created'))]
    print(f'  {"默认" if not args else "SetMaxStack(1 MiB)"}:退出码 {p.returncode};' + ' / '.join(lines[:4])[:330])

print('== 六:函数序言里的栈检查与 //go:nosplit(汇编,以及用 nosplit 链撑爆链接器的限制)')
asm = [l.strip() for l in o.split('\n') if False]
r = grun('sg2', {'main.go': 'package main\n\n//go:noinline\nfunc f(n int) int { var b [128]byte; b[n&127] = 1; if n == 0 { return 0 }; return f(n-1) + int(b[1]) }\n\nfunc main() { println(f(3)) }\n'}, gcflags='-S')
blk = [x for x in re.split(r'\n(?=main\.\S+ STEXT)', r['cout']) if x.startswith('main.f STEXT')][0]
pro = [re.sub(r'^\s*0x[0-9a-f]+ \d+ \(', '(', l).replace(str(GT) + '/', '').strip()[:110] for l in blk.split('\n') if (re.search(r'\b(CMP|BLS|BHI|SUB)\b', l) and 'rel ' not in l) or ('morestack' in l and not l.strip().startswith('rel '))]
for l in pro[:8]: print('    ' + l)
print('  函数头:' + re.sub(r'\s+', ' ', [l for l in r['cout'].split('\n') if l.startswith('main.f STEXT')][0])[:120])
NS = ''.join(f'//go:nosplit\nfunc n{i}() int {{ var b [64]byte; b[0] = byte({i}); return int(b[0]) + n{i + 1}() }}\n\n' for i in range(40)) + '//go:nosplit\nfunc n40() int { var b [64]byte; return int(b[0]) }\n\nfunc main() { println(n0()) }\n'
dn = gdir('sg3'); write(dn, {'main.go': 'package main\n\n' + NS}); mod(dn)
rc, o2 = go(dn, 'build', '-o', 'app')
print(f'  40 个依次调用、每个有 64 字节局部数组的 //go:nosplit 函数:go build rc={rc}')
for l in o2.split('\n')[:5]: print('    ' + l.replace('./main.go', 'main.go')[:150])
