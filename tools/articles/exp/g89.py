import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g89')
SRC = r'''
package main

import (
	"fmt"
	"math/rand"
	randv2 "math/rand/v2"
	"os"
	"runtime"
	"sort"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

var sinkI int
var sinkU uint64

func par(g int, total int, body func(n int)) float64 {
	var wg sync.WaitGroup
	n := total / g
	start := make(chan struct{})
	for i := 0; i < g; i++ { wg.Add(1); go func() { defer wg.Done(); <-start; body(n) }() }
	t0 := time.Now()
	close(start)
	wg.Wait()
	return float64(time.Since(t0).Nanoseconds()) / float64(total)
}

func med(f func() float64) float64 { xs := []float64{f(), f(), f()}; sort.Float64s(xs); return xs[1] }

func main() {
	runtime.GOMAXPROCS(8)
	switch os.Args[1] {
	case "global":
		const total = 16_000_000
		for _, g := range []int{1, 8} {
			v1 := med(func() float64 { return par(g, total, func(n int) { s := 0; for i := 0; i < n; i++ { s += rand.Intn(100) }; sinkI += s }) })
			v2 := med(func() float64 { return par(g, total, func(n int) { s := 0; for i := 0; i < n; i++ { s += randv2.IntN(100) }; sinkI += s }) })
			fmt.Printf("  G=%d 个 goroutine 共 1600 万次:math/rand 的 rand.Intn(100) %6.1f ns/次;math/rand/v2 的 rand.IntN(100) %6.1f ns/次\n", g, v1, v2)
		}
	case "seeded":
		const total = 16_000_000
		rand.Seed(42) // Go 1.24 起默认是空操作;GODEBUG=randseednop=0 才恢复旧行为
		for _, g := range []int{1, 8} {
			v1 := med(func() float64 { return par(g, total, func(n int) { s := 0; for i := 0; i < n; i++ { s += rand.Intn(100) }; sinkI += s }) })
			fmt.Printf("  调用 rand.Seed(42) 之后(GODEBUG=%q),G=%d:math/rand 的 rand.Intn(100) %6.1f ns/次\n", os.Getenv("GODEBUG"), g, v1)
		}
	case "gens":
		pcg := randv2.NewPCG(1, 2)
		cc := randv2.NewChaCha8([32]byte{1})
		r1 := rand.New(rand.NewSource(1))
		r2 := randv2.New(randv2.NewPCG(1, 2))
		r3 := randv2.New(randv2.NewChaCha8([32]byte{1}))
		b := func(f func()) int64 { return testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { f() } }).NsPerOp() }
		fmt.Printf("  Uint64:PCG %d ns;ChaCha8 %d ns\n", b(func() { sinkU += pcg.Uint64() }), b(func() { sinkU += cc.Uint64() }))
		fmt.Printf("  IntN(100)(各自独占一个 *Rand):v1 NewSource %d ns;v2 PCG %d ns;v2 ChaCha8 %d ns\n", b(func() { sinkI += r1.Intn(100) }), b(func() { sinkI += r2.IntN(100) }), b(func() { sinkI += r3.IntN(100) }))
		a1 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { sinkI += rand.New(rand.NewSource(int64(i))).Intn(2) } })
		a2 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { sinkI += randv2.New(randv2.NewPCG(uint64(i), 2)).IntN(2) } })
		a3 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { sinkI += randv2.New(randv2.NewChaCha8([32]byte{byte(i)})).IntN(2) } })
		fmt.Printf("  新建一个带种子的生成器并取一个数:v1 NewSource %d ns、%d B、%d 次分配;v2 PCG %d ns、%d B、%d 次分配;v2 ChaCha8 %d ns、%d B、%d 次分配\n", a1.NsPerOp(), a1.AllocedBytesPerOp(), a1.AllocsPerOp(), a2.NsPerOp(), a2.AllocedBytesPerOp(), a2.AllocsPerOp(), a3.NsPerOp(), a3.AllocedBytesPerOp(), a3.AllocsPerOp())
	case "seed":
		r := randv2.New(randv2.NewPCG(1, 2))
		fmt.Printf("  PCG(1,2) 的前 5 个 IntN(1000):%d %d %d %d %d\n", r.IntN(1000), r.IntN(1000), r.IntN(1000), r.IntN(1000), r.IntN(1000))
		r1 := rand.New(rand.NewSource(1))
		fmt.Printf("  v1 NewSource(1) 的前 5 个 Intn(1000):%d %d %d %d %d\n", r1.Intn(1000), r1.Intn(1000), r1.Intn(1000), r1.Intn(1000), r1.Intn(1000))
		fmt.Printf("  v2 顶层 rand.IntN(1000) 本进程的前 5 个:%d %d %d %d %d\n", randv2.IntN(1000), randv2.IntN(1000), randv2.IntN(1000), randv2.IntN(1000), randv2.IntN(1000))
	case "race":
		r := randv2.New(randv2.NewPCG(1, 2))
		var wg sync.WaitGroup
		var tot atomic.Int64
		for g := 0; g < 4; g++ { wg.Add(1); go func() { defer wg.Done(); s := 0; for i := 0; i < 1000; i++ { s += r.IntN(10) }; tot.Add(int64(s)) }() }
		wg.Wait()
		fmt.Println("  4 个 goroutine 共用一个 *rand.Rand:完成")
	case "toplevel":
		var wg sync.WaitGroup
		var tot atomic.Int64
		for g := 0; g < 4; g++ { wg.Add(1); go func() { defer wg.Done(); s := 0; for i := 0; i < 1000; i++ { s += randv2.IntN(10) }; tot.Add(int64(s)) }() }
		wg.Wait()
		fmt.Println("  4 个 goroutine 共用顶层函数 rand.IntN:完成")
	}
}
'''
d = gdir('rn1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
rc, o = go(d, 'build', '-race', '-o', 'app_race'); assert rc == 0, o
def run(m, race=False, env=None):
    e = dict(os.environ); e.update(env or {})
    p = subprocess.run([str(d / ('app_race' if race else 'app')), m], capture_output=True, text=True, timeout=600, env=e)
    return p.returncode, tidy(p.stdout + p.stderr)
print('== 一:顶层函数在多个 goroutine 下(Go 1.27.1,arm64 macOS,GOMAXPROCS=8;每格 3 次取中位数)')
print(run('global')[1])
print(run('seeded')[1])
print(run('seeded', env={'GODEBUG': 'randseednop=0'})[1])
print('== 二:生成器本身的速度与创建成本')
print(run('gens')[1])
print('== 三:种子与可重复性(同一个种子,两次运行结果一致吗)')
a = run('seed')[1]; b = run('seed')[1]
print(a)
print('  再运行一次同一个程序:')
print('\n'.join('  ' + l.strip() for l in b.split('\n') if '顶层' in l))
print('  前两行(固定种子)两次运行是否完全相同:' + str(a.split('\n')[:2] == b.split('\n')[:2]))
print('== 四:并发安全(-race 编译)')
rc, o = run('race', race=True); print(f'  共用一个 *Rand:退出码 {rc};出现 DATA RACE {o.count("WARNING: DATA RACE")} 次')
rc, o = run('toplevel', race=True); print(f'  共用顶层函数:退出码 {rc};出现 DATA RACE {o.count("WARNING: DATA RACE")} 次;{o.strip().splitlines()[-1].strip()}')
print('== 五:文档')
r, o = go(gdir('doc1'), 'doc', 'math/rand/v2')
ls = [l.strip() for l in o.split('\n')]
print('  ' + ' '.join(ls[3:8]))
print('  ' + ' '.join(x for x in ls[8:11]))
