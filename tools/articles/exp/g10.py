import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g10')
SRC = r'''
package main

import (
	"fmt"
	"runtime"
	"runtime/debug"
	"sort"
	"time"
)

func heapMiB() float64 {
	runtime.GC()
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	return float64(ms.HeapAlloc) / (1 << 20)
}

func spikes(name string, m map[int]int, n int) {
	lat := make([]int64, n)
	for i := 0; i < n; i++ {
		t0 := time.Now()
		m[i] = i
		lat[i] = int64(time.Since(t0))
	}
	idx := make([]int, n)
	for i := range idx { idx[i] = i }
	sort.Slice(idx, func(a, b int) bool { return lat[idx[a]] > lat[idx[b]] })
	s := append([]int64(nil), lat...)
	sort.Slice(s, func(a, b int) bool { return s[a] < s[b] })
	fmt.Printf("  %s:p50 %d ns,p99 %d ns,p99.9 %d ns,最大 %d ns;最慢的 8 次插入发生在 len = ", name, s[n/2], s[n*99/100], s[n*999/1000], s[n-1])
	for _, i := range idx[:8] { fmt.Printf("%d(%d µs) ", i+1, lat[i]/1000) }
	fmt.Println()
}

func main() {
	const NEV = 3000
	m := map[int]int{}
	mal := make([]uint64, NEV+1)
	var ms runtime.MemStats
	for i := 1; i <= NEV; i++ {
		m[i] = i
		runtime.ReadMemStats(&ms)
		mal[i] = ms.Mallocs
	}
	var ev []string
	for i := 2; i <= NEV; i++ {
		if mal[i] != mal[i-1] { ev = append(ev, fmt.Sprintf("%d(+%d)", i, mal[i]-mal[i-1])) }
	}
	fmt.Printf("  逐个插入 map[int]int 的前 %d 个键(不给容量提示),Mallocs 增加的时刻(len(+新增分配次数)),共 %d 次:\n    %v\n", NEV, len(ev), ev)

	fmt.Println("== 三:单次插入的耗时分布:100 万个键,关掉 GC,逐个计时(time.Now 本身约 40 ns)")
	debug.SetGCPercent(-1)
	spikes("不给容量提示", map[int]int{}, 1_000_000)
	spikes("make(map[int]int, 1000000)", make(map[int]int, 1_000_000), 1_000_000)
	debug.SetGCPercent(100)

	fmt.Println("== 四:map 不会缩小:插入 100 万个键,再删掉全部键,堆有没有回来")
	base := heapMiB()
	mm := make(map[int]int)
	for i := 0; i < 1_000_000; i++ { mm[i] = i }
	full := heapMiB()
	for i := 0; i < 1_000_000; i++ { delete(mm, i) }
	deleted := heapMiB()
	fmt.Printf("  基线 %.2f MiB;插入 100 万个键后 %.2f MiB;delete 掉全部键后(len = %d)%.2f MiB\n", base, full, len(mm), deleted)
	clear(mm)
	cleared := heapMiB()
	fmt.Printf("  clear(m) 之后 %.2f MiB\n", cleared)
	mm = nil
	nilled := heapMiB()
	fmt.Printf("  m = nil 之后 %.2f MiB(整个 map 才被回收)\n", nilled)
}
'''
print('== 一:Go 1.27.1 的 map 是 Swiss Table:源码里的几个常量')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/'
import subprocess
def grep(pat, f):
    o = subprocess.run(['grep', '-n', pat, base + f], capture_output=True, text=True).stdout.strip().split('\n')[0]
    return '  ' + f + ':' + o.strip()
print(grep('^const maxTableCapacity', 'internal/runtime/maps/table.go'))
print(grep('maxAvgGroupLoad = ', 'internal/runtime/maps/group.go') if subprocess.run(['grep', '-c', 'maxAvgGroupLoad = ', base + 'internal/runtime/maps/group.go'], capture_output=True, text=True).stdout.strip() != '0' else grep('maxAvgGroupLoad', 'internal/runtime/maps/map.go'))
print(grep('MapGroupSlots = ', 'internal/abi/map.go') if subprocess.run(['grep', '-c', 'MapGroupSlots = ', base + 'internal/abi/map.go'], capture_output=True, text=True).stdout.strip() != '0' else grep('MapGroupSlots', 'internal/abi/map.go'))
print('  internal/goexperiment 里是否还有 noswissmap 开关:' + ('有' if subprocess.run(['grep', '-rli', 'swissmap', base + 'internal/goexperiment'], capture_output=True, text=True).stdout.strip() else '没有(只剩 Swiss Table 实现,旧的 hmap 增量搬迁实现已经移除)'))
print('== 二:扩容的真实时刻')
r = grun('mg1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
