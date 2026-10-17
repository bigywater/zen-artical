import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g64')
SRC = r'''
package main

import (
	"fmt"
	"math/rand/v2"
	"os"
	"runtime"
	"sort"
	"strconv"
	"sync"
	"time"
)

const total = 8_000_000
const keys = 10_000

type store interface {
	Load(k int) (int, bool)
	Store(k, v int)
}

type syncMap struct{ m sync.Map }

func (s *syncMap) Load(k int) (int, bool) { v, ok := s.m.Load(k); if !ok { return 0, false }; return v.(int), true }
func (s *syncMap) Store(k, v int)         { s.m.Store(k, v) }

type rwMap struct { mu sync.RWMutex; m map[int]int }

func (s *rwMap) Load(k int) (int, bool) { s.mu.RLock(); v, ok := s.m[k]; s.mu.RUnlock(); return v, ok }
func (s *rwMap) Store(k, v int)         { s.mu.Lock(); s.m[k] = v; s.mu.Unlock() }

type muMap struct { mu sync.Mutex; m map[int]int }

func (s *muMap) Load(k int) (int, bool) { s.mu.Lock(); v, ok := s.m[k]; s.mu.Unlock(); return v, ok }
func (s *muMap) Store(k, v int)         { s.mu.Lock(); s.m[k] = v; s.mu.Unlock() }

func newStore(kind string) store {
	switch kind {
	case "sync.Map": return &syncMap{}
	case "RWMutex+map": return &rwMap{m: map[int]int{}}
	}
	return &muMap{m: map[int]int{}}
}

var sink int

// writePct:写占的百分比;disjoint:每个 goroutine 只读写自己的键区间
func bench(kind string, g int, writePct int, disjoint bool) float64 {
	s := newStore(kind)
	for k := 0; k < keys; k++ { s.Store(k, k) }
	var wg sync.WaitGroup
	start := make(chan struct{})
	n := total / g
	for id := 0; id < g; id++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := rand.New(rand.NewPCG(uint64(id), 7))
			lo, span := 0, keys
			if disjoint { span = keys / g; lo = id * span }
			<-start
			x := 0
			for i := 0; i < n; i++ {
				k := lo + int(r.Uint32N(uint32(span)))
				if int(r.Uint32N(100)) < writePct { s.Store(k, i) } else { v, _ := s.Load(k); x += v }
			}
			sink += x
		}()
	}
	t0 := time.Now()
	close(start)
	wg.Wait()
	return float64(time.Since(t0).Nanoseconds()) / total
}

func med3(f func() float64) float64 {
	xs := []float64{f(), f(), f()}
	sort.Float64s(xs)
	return xs[1]
}

func heap() float64 { runtime.GC(); runtime.GC(); var m runtime.MemStats; runtime.ReadMemStats(&m); return float64(m.HeapAlloc) / 1e6 }

func main() {
	runtime.GOMAXPROCS(8)
	switch os.Args[1] {
	case "bench":
		g, _ := strconv.Atoi(os.Args[2])
		wp, _ := strconv.Atoi(os.Args[3])
		dis := os.Args[4] == "disjoint"
		for _, kind := range []string{"sync.Map", "RWMutex+map", "Mutex+map"} {
			fmt.Printf("%.1f ", med3(func() float64 { return bench(kind, g, wp, dis) }))
		}
		fmt.Println()
	case "mem":
		const N = 1_000_000
		h0 := heap()
		m := map[int]int{}
		for i := 0; i < N; i++ { m[i] = i }
		h1 := heap()
		var sm sync.Map
		for i := 0; i < N; i++ { sm.Store(i, i) }
		h2 := heap()
		fmt.Printf("  100 万个 int→int:普通 map 占堆 %.1f MB;sync.Map 占堆 %.1f MB(%.1f 倍)\n", h1-h0, h2-h1, (h2-h1)/(h1-h0))
		runtime.KeepAlive(m); runtime.KeepAlive(&sm)
	}
}
'''
d = gdir('sm2'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=600)
    return [float(x) for x in p.stdout.split()] if a[0] == 'bench' else (p.stdout + p.stderr).rstrip()
print('== 一:一万个键,每次操作随机选一个键读或写;800 万次操作分给 G 个 goroutine(墙钟 ÷ 800 万,每格 3 次中位数;Go 1.27.1,arm64 macOS,GOMAXPROCS=8)')
print('  单位 ns/次;顺序:sync.Map / RWMutex+map / Mutex+map')
for desc, wp, dis in (('只读(0% 写,共享键)', 0, 'shared'), ('99% 读 1% 写(共享键)', 1, 'shared'), ('50% 读 50% 写(共享键)', 50, 'shared'), ('50% 读 50% 写(每个 goroutine 只碰自己的键区间)', 50, 'disjoint')):
    for g in (1, 8):
        r = run('bench', g, wp, dis)
        print(f'  {desc:34s} G={g}: {r[0]:7.1f} / {r[1]:7.1f} / {r[2]:7.1f}')
print('== 二:内存')
print(run('mem'))
print('== 三:sync.Map 的文档与实现')
r, o = go(gdir('doc1'), 'doc', 'sync.Map')
ls = [l.strip() for l in o.split('\n')]
for i, l in enumerate(ls):
    if l.startswith('Map is like a Go map') or 'The Map type is specialized' in l or 'optimized for two common use cases' in l:
        print('  ' + ' '.join(ls[i:i + 4]))
src = open(GOROOT + '/src/sync/map.go').read()
print('  src/sync/map.go 里 Map 结构体的核心字段:' + re.search(r'\tm isync\.HashTrieMap\[any, any\]', src).group(0).strip())
h = open(GOROOT + '/src/internal/sync/hashtriemap.go').read()
m = re.search(r'// HashTrieMap is an implementation of a concurrent hash-trie\..*?used elsewhere as well\.', h, re.S)
print('  internal/sync/hashtriemap.go:' + ' '.join(x.strip('/ ') for x in m.group(0).split('\n')))
