import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g11')
SRC = r'''
package main

import (
	"encoding/json"
	"fmt"
	"maps"
	"slices"
	"sort"
	"strings"
)

func order(m map[int]int) []int {
	var ks []int
	for k := range m { ks = append(ks, k) }
	return ks
}

func isRotation(base, x []int) bool {
	n := len(base)
	if len(x) != n { return false }
	pos := -1
	for i, v := range base { if v == x[0] { pos = i } }
	for i := 0; i < n; i++ { if base[(pos+i)%n] != x[i] { return false } }
	return true
}

func main() {
	m := map[string]int{"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7, "h": 8, "i": 9, "j": 10}
	for i := 0; i < 5; i++ {
		var ks []string
		for k := range m { ks = append(ks, k) }
		fmt.Printf("  同一个进程里第 %d 次 for range:%s\n", i+1, strings.Join(ks, " "))
	}

	fmt.Println("== 二:第一个被遍历到的键的分布:每个 map 遍历 10000 次,统计第一个键")
	for _, n := range []int{8, 100} {
		mm := map[int]int{}
		for i := 0; i < n; i++ { mm[i] = i }
		cnt := map[int]int{}
		for it := 0; it < 10000; it++ {
			for k := range mm { cnt[k]++; break }
		}
		var cs []int
		for _, c := range cnt { cs = append(cs, c) }
		sort.Ints(cs)
		fmt.Printf("  %3d 个键:出现过的不同首键 %d 个(期望均匀时每个 %.0f 次),最少 %d 次、最多 %d 次\n", n, len(cnt), 10000/float64(n), cs[0], cs[len(cs)-1])
	}

	fmt.Println("== 三:顺序是任意排列,还是只是同一个环的旋转:每个 map 遍历 5000 次(键多的少遍历几次),数不同的完整顺序")
	for _, n := range []int{5, 8, 9, 20, 100, 1000, 2000, 20000} {
		mm := map[int]int{}
		for i := 0; i < n; i++ { mm[i] = i }
		base := order(mm)
		seen := map[string]bool{}
		allRot := true
		iters := 5000
		if n >= 1000 { iters = 3000 }
		for it := 0; it < iters; it++ {
			o := order(mm)
			seen[fmt.Sprint(o)] = true
			if !isRotation(base, o) { allRot = false }
		}
		fmt.Printf("  %5d 个键:%d 次遍历出现了 %d 种不同的完整顺序;全都是第一次顺序的旋转?%v\n", n, iters, len(seen), allRot)
	}

	fmt.Println("== 四:遍历中修改:删除还没遍历到的键,新增键,各重复 2000 次")
	delSeen, addSeen := 0, 0
	for it := 0; it < 2000; it++ {
		mm := map[int]int{1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
		var victim int
		seen := map[int]bool{}
		first := true
		for k := range mm {
			seen[k] = true
			if first {
				first = false
				for _, d := range []int{1, 2, 3, 4, 5} { if d != k { victim = d; delete(mm, d); break } }
			}
		}
		if seen[victim] { delSeen++ }
	}
	for it := 0; it < 2000; it++ {
		mm := map[int]int{1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
		added := false
		for k := range mm {
			if !added { added = true; mm[100] = 100 }
			if k == 100 { addSeen++ }
		}
	}
	fmt.Printf("  遍历时删除另一个还没遍历到的键:被遍历到 %d / 2000 次;遍历时新增键 100:被遍历到 %d / 2000 次\n", delSeen, addSeen)

	fmt.Println("== 五:需要确定顺序时:fmt 与 encoding/json 输出 map 时排序;自己遍历要先排序键")
	sm := map[string]int{"banana": 2, "apple": 1, "cherry": 3, "date": 4}
	fmt.Printf("  fmt.Println(m) → %v(按键排序)\n", sm)
	js, _ := json.Marshal(sm)
	fmt.Printf("  json.Marshal(m) → %s(按键排序)\n", js)
	fmt.Printf("  slices.Sorted(maps.Keys(m)) → %v\n", slices.Sorted(maps.Keys(sm)))
	var nilm map[string]int
	n := 0
	for range nilm { n++ }
	fmt.Printf("  for range nil map:%d 次循环,不会 panic\n", n)
}
'''
print('== 一:同一个进程里多次遍历同一个 map,顺序不同(Go 1.27.1)')
r = grun('mo1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/internal/runtime/maps/table.go'
o = subprocess.run(['sed', '-n', '750,762p', base], capture_output=True, text=True).stdout.rstrip()
print('== 六:随机数从哪里来:internal/runtime/maps/table.go 里迭代器初始化的片段(原样)')
print('\n'.join('  ' + l for l in o.split('\n')))
outs = []
for i in range(3):
    rr = subprocess.run([r['bin']], capture_output=True, text=True)
    outs.append(rr.stdout.split('\n')[0])
print('  再启动 3 个新进程,各自第 1 次遍历的顺序:')
for l in outs: print('    ' + l.strip())
