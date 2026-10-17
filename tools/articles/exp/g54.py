import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g54')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/metrics"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"
)

var sink [][]byte

func main() {
	switch os.Args[1] {
	case "list":
		ds := metrics.All()
		kinds := map[string]int{}
		groups := map[string]int{}
		cum := 0
		for _, d := range ds {
			kinds[map[metrics.ValueKind]string{metrics.KindUint64: "uint64", metrics.KindFloat64: "float64", metrics.KindFloat64Histogram: "直方图"}[d.Kind]]++
			p := strings.Split(strings.TrimPrefix(d.Name, "/"), "/")[0]
			groups[p]++
			if d.Cumulative { cum++ }
		}
		fmt.Printf("  metrics.All() 共 %d 个指标;累计型(Cumulative)%d 个;按取值类型:uint64 %d / float64 %d / 直方图 %d\n", len(ds), cum, kinds["uint64"], kinds["float64"], kinds["直方图"])
		var gs []string
		for g, n := range groups { gs = append(gs, fmt.Sprintf("/%s/…:%d", g, n)) }
		sort.Strings(gs)
		fmt.Printf("  按第一段路径分组:%s\n", strings.Join(gs, "  "))
		for _, d := range ds {
			if strings.HasPrefix(d.Name, "/sched/") || d.Name == "/gc/heap/live:bytes" || d.Name == "/memory/classes/total:bytes" {
				k := map[metrics.ValueKind]string{metrics.KindUint64: "uint64", metrics.KindFloat64: "float64", metrics.KindFloat64Histogram: "直方图"}[d.Kind]
				fmt.Printf("    %-44s %-7s 累计=%v\n", d.Name, k, d.Cumulative)
			}
		}
	case "bad":
		s := []metrics.Sample{{Name: "/no/such/metric:bytes"}, {Name: "/gc/cycles/total:gc-cycles"}}
		metrics.Read(s)
		fmt.Printf("  读不存在的指标名:Kind=%v(KindBad=%v);同一次 Read 里存在的指标 Kind=%v 值=%d\n", s[0].Value.Kind(), metrics.KindBad, s[1].Value.Kind(), s[1].Value.Uint64())
	case "agree":
		runtime.GC()
		names := []string{"/gc/heap/allocs:bytes", "/gc/cycles/total:gc-cycles", "/sched/goroutines:goroutines", "/memory/classes/total:bytes", "/gc/heap/allocs:objects"}
		s := make([]metrics.Sample, len(names))
		for i, n := range names { s[i].Name = n }
		var m0, m1 runtime.MemStats
		runtime.ReadMemStats(&m0); metrics.Read(s)
		a0, o0 := s[0].Value.Uint64(), s[4].Value.Uint64()
		for i := 0; i < 100; i++ { sink = append(sink, make([]byte, 1<<20)) }
		var wg sync.WaitGroup
		for i := 0; i < 50; i++ { wg.Add(1); go func() { defer wg.Done(); time.Sleep(200 * time.Millisecond) }() }
		time.Sleep(20 * time.Millisecond)
		runtime.GC()
		runtime.ReadMemStats(&m1); metrics.Read(s)
		fmt.Printf("  分配 100 个 1MiB 切片并 GC 一次之后:\n")
		fmt.Printf("    /gc/heap/allocs:bytes 增加 %d  ←→  MemStats.TotalAlloc 增加 %d\n", s[0].Value.Uint64()-a0, m1.TotalAlloc-m0.TotalAlloc)
		fmt.Printf("    /gc/heap/allocs:objects 增加 %d  ←→  MemStats.Mallocs 增加 %d\n", s[4].Value.Uint64()-o0, m1.Mallocs-m0.Mallocs)
		fmt.Printf("    /gc/cycles/total:gc-cycles = %d  ←→  MemStats.NumGC = %d\n", s[1].Value.Uint64(), m1.NumGC)
		fmt.Printf("    /sched/goroutines:goroutines = %d  ←→  runtime.NumGoroutine() = %d\n", s[2].Value.Uint64(), runtime.NumGoroutine())
		fmt.Printf("    /memory/classes/total:bytes = %d  ←→  MemStats.Sys = %d\n", s[3].Value.Uint64(), m1.Sys)
		wg.Wait()
	case "cost":
		one := []metrics.Sample{{Name: "/gc/heap/allocs:bytes"}}
		all := metrics.All()
		many := make([]metrics.Sample, len(all))
		for i, d := range all { many[i].Name = d.Name }
		var ms runtime.MemStats
		time1 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { metrics.Read(one) } })
		timeAll := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { metrics.Read(many) } })
		timeMS := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { runtime.ReadMemStats(&ms) } })
		fmt.Printf("  metrics.Read(1 个指标,复用切片):%d ns/次,%d 次分配\n", time1.NsPerOp(), time1.AllocsPerOp())
		fmt.Printf("  metrics.Read(全部 %d 个指标,复用切片):%d ns/次,%d 次分配\n", len(many), timeAll.NsPerOp(), timeAll.AllocsPerOp())
		fmt.Printf("  runtime.ReadMemStats:%d ns/次,%d 次分配\n", timeMS.NsPerOp(), timeMS.AllocsPerOp())
	case "hist":
		runtime.GOMAXPROCS(1)
		var wg sync.WaitGroup
		for i := 0; i < 200; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); x := 0; for j := 0; j < 3_000_000; j++ { x += j }; _ = x }()
		}
		wg.Wait()
		s := []metrics.Sample{{Name: "/sched/latencies:seconds"}}
		metrics.Read(s)
		h := s[0].Value.Float64Histogram()
		var tot uint64
		for _, c := range h.Counts { tot += c }
		fmt.Printf("  GOMAXPROCS=1,200 个各自计算约 3 毫秒的 goroutine 同时就绪:/sched/latencies:seconds 直方图共 %d 个桶、记录 %d 次调度等待\n", len(h.Counts), tot)
		var acc uint64
		pr := map[string]bool{}
		for i, c := range h.Counts {
			acc += c
			for _, q := range []struct{ n string; f float64 }{{"p50", .5}, {"p90", .9}, {"p99", .99}, {"最大", 1}} {
				if !pr[q.n] && float64(acc) >= q.f*float64(tot) {
					pr[q.n] = true
					fmt.Printf("    %s:落在桶 [%.6g s, %.6g s)\n", q.n, h.Buckets[i], h.Buckets[i+1])
				}
			}
		}
	}
}
'''
d = gdir('mt1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(mode, tmo=300):
    p = subprocess.run([str(d / 'app'), mode], capture_output=True, text=True, timeout=tmo)
    return (p.stdout + p.stderr).rstrip()
print('== 一:有哪些指标(Go 1.27.1,arm64 macOS)')
print(run('list'))
print('== 二:读不存在的指标名')
print(run('bad'))
print('== 三:与 runtime.MemStats / NumGoroutine 对账')
print(run('agree'))
print('== 四:读一次指标要多少钱')
print(run('cost'))
print('== 五:直方图指标:只有一个 P 时调度等待的分布')
print(run('hist'))
print('== 六:文档里的几句话(go doc runtime/metrics)')
r, o = go(gdir('doc1'), 'doc', 'runtime/metrics')
ls = o.split('\n')
for k in ('Thus, users of this API are encouraged', 'the "kind" for a given metric is guaranteed not to change', 'never produce the', '/sched/latencies:seconds'):
    i = next((i for i, l in enumerate(ls) if k in l), None)
    if i is None: print('  (没找到)', k); continue
    for l in ls[max(0, i - 1 if k.startswith('/') else i):i + 3]: print('  ' + l.strip())
    print('  ---')
print('  源码对照:')
for f, pat in (('debug.go', 'return int(gcount(false))'), ('metrics.go', 'a.gTotal = uint64(gcount(true))')):
    p = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/' + f
    n = subprocess.run(['grep', '-n', pat, p], capture_output=True, text=True).stdout.split(':')[0]
    print(f'    runtime/{f}:{n}: ' + pat)
