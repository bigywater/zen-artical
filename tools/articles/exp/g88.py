import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g88')
SRC = r'''
package main

import (
	"cmp"
	"fmt"
	"math/rand/v2"
	"os"
	"slices"
	"sort"
	"time"
)

const N = 1_000_000

func gen(kind string) []int {
	a := make([]int, N)
	r := rand.New(rand.NewPCG(1, 2))
	switch kind {
	case "随机": for i := range a { a[i] = r.IntN(1 << 30) }
	case "已排序": for i := range a { a[i] = i }
	case "逆序": for i := range a { a[i] = N - i }
	case "全部相等": for i := range a { a[i] = 7 }
	case "只有 10 种取值": for i := range a { a[i] = r.IntN(10) }
	case "管风琴形(先升后降)": for i := range a { if i < N/2 { a[i] = i } else { a[i] = N - i } }
	case "已排序但末尾 1% 乱序": for i := range a { a[i] = i }; for i := N - N/100; i < N; i++ { a[i] = r.IntN(N) }
	}
	return a
}

func timeSort(kind string, f func([]int)) float64 {
	var best float64 = 1e18
	for k := 0; k < 5; k++ {
		a := gen(kind)
		t0 := time.Now()
		f(a)
		d := float64(time.Since(t0).Microseconds()) / 1000
		if d < best { best = d }
		if !slices.IsSorted(a) { panic("not sorted") }
	}
	return best
}

type rec struct{ key, seq int }

func main() {
	switch os.Args[1] {
	case "shapes":
		kinds := []string{"随机", "已排序", "逆序", "全部相等", "只有 10 种取值", "管风琴形(先升后降)", "已排序但末尾 1% 乱序"}
		fmt.Printf("  %-22s %12s %12s %12s %14s\n", "输入形状(100 万个 int)", "slices.Sort", "sort.Ints", "sort.Slice", "SliceStable")
		for _, k := range kinds {
			t1 := timeSort(k, func(a []int) { slices.Sort(a) })
			t2 := timeSort(k, func(a []int) { sort.Ints(a) })
			t3 := timeSort(k, func(a []int) { sort.Slice(a, func(i, j int) bool { return a[i] < a[j] }) })
			t4 := timeSort(k, func(a []int) { sort.SliceStable(a, func(i, j int) bool { return a[i] < a[j] }) })
			fmt.Printf("  %-22s %9.1f ms %9.1f ms %9.1f ms %11.1f ms\n", k, t1, t2, t3, t4)
		}
	case "stable":
		mk := func() []rec {
			r := rand.New(rand.NewPCG(3, 4))
			a := make([]rec, 100000)
			for i := range a { a[i] = rec{key: r.IntN(100), seq: i} }
			return a
		}
		bad := func(a []rec) int { n := 0; for i := 1; i < len(a); i++ { if a[i].key == a[i-1].key && a[i].seq < a[i-1].seq { n++ } }; return n }
		a := mk(); sort.Slice(a, func(i, j int) bool { return a[i].key < a[j].key })
		fmt.Printf("  10 万条记录,100 种键:sort.Slice(不稳定)之后,键相等的相邻记录里原始顺序颠倒的有 %d 对\n", bad(a))
		b := mk(); sort.SliceStable(b, func(i, j int) bool { return b[i].key < b[j].key })
		fmt.Printf("  sort.SliceStable 之后:%d 对\n", bad(b))
		c := mk(); slices.SortFunc(c, func(x, y rec) int { return cmp.Compare(x.key, y.key) })
		fmt.Printf("  slices.SortFunc(不稳定)之后:%d 对\n", bad(c))
		d := mk(); slices.SortStableFunc(d, func(x, y rec) int { return cmp.Compare(x.key, y.key) })
		fmt.Printf("  slices.SortStableFunc 之后:%d 对\n", bad(d))
	}
}
'''
d = gdir('ps1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=900)
    return tidy(p.stdout + p.stderr)
print('== 一:不同输入形状下的排序耗时(Go 1.27.1,arm64 macOS;每格 5 次取最小)')
print(run('shapes'))
print('== 二:稳定性')
print(run('stable'))
print('== 三:源码里的说明')
z = open(GOROOT + '/src/sort/zsortfunc.go').read().split('\n')
i = next(i for i, l in enumerate(z) if l.startswith('func pdqsort_func'))
for l in (z[i - 1], z[i]): print('  ' + l.strip())
seen = set()
for l in z[i:i + 40]:
    t = l.strip()
    if t in ('const maxInsertion = 12', 'if length <= maxInsertion {') or t.startswith('heapSort_func(data, a, b)'):
        if t not in seen: seen.add(t); print('  ' + t)
zz = open(GOROOT + '/src/slices/zsortordered.go').read().split('\n')
j = next(j for j, l in enumerate(zz) if 'pattern-defeating quicksort' in l)
print('  slices/zsortordered.go:' + zz[j].lstrip('/ '))
r, o = go(gdir('doc1'), 'doc', 'sort.Slice')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:9] if l.strip()))
