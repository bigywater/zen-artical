import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g103')
SRC = r'''
package main

import (
	"fmt"
	"hash/crc32"
	"hash/fnv"
	"hash/maphash"
	"os"
	"strconv"
	"testing"
)

var sinkU uint64
var sinkU32 uint32

type key struct {
	A int
	B string
}

func main() {
	switch os.Args[1] {
	case "seed":
		s1 := maphash.MakeSeed()
		s2 := maphash.MakeSeed()
		fmt.Printf("SEED1 %016x\n", maphash.String(s1, "hello"))
		fmt.Printf("SEED1b %016x\n", maphash.String(s1, "hello"))
		fmt.Printf("SEED2 %016x\n", maphash.String(s2, "hello"))
		var h maphash.Hash
		h.SetSeed(s1)
		h.WriteString("he")
		h.WriteString("llo")
		fmt.Printf("INCR %016x\n", h.Sum64())
		fmt.Printf("CMP %016x\n", maphash.Comparable(s1, key{1, "x"}))
		fmt.Printf("CMP2 %016x\n", maphash.Comparable(s1, key{1, "x"}))
		fmt.Printf("CMP3 %016x\n", maphash.Comparable(s1, key{2, "x"}))
		fnvh := fnv.New64a()
		fnvh.Write([]byte("hello"))
		fmt.Printf("FNV %016x\n", fnvh.Sum64())
	case "dist":
		const B = 16
		const N = 160000
		seed := maphash.MakeSeed()
		var cm, cf [B]int
		for i := 0; i < N; i++ {
			k := "key" + strconv.Itoa(i)
			cm[maphash.String(seed, k)%B]++
			h := fnv.New64a(); h.Write([]byte(k)); cf[h.Sum64()%B]++
		}
		minmax := func(c [B]int) (int, int) { lo, hi := c[0], c[0]; for _, v := range c { if v < lo { lo = v }; if v > hi { hi = v } }; return lo, hi }
		a, b := minmax(cm); c, d := minmax(cf)
		fmt.Printf("DIST maphash 每个桶最少 %d、最多 %d;FNV-1a 每个桶最少 %d、最多 %d(理想值 %d)\n", a, b, c, d, N/B)
	case "speed":
		seed := maphash.MakeSeed()
		for _, n := range []int{16, 1024} {
			data := make([]byte, n)
			for i := range data { data[i] = byte(i) }
			s := string(data)
			r1 := testing.Benchmark(func(b *testing.B) { b.SetBytes(int64(n)); for i := 0; i < b.N; i++ { sinkU = maphash.String(seed, s) } })
			r2 := testing.Benchmark(func(b *testing.B) { b.SetBytes(int64(n)); for i := 0; i < b.N; i++ { h := fnv.New64a(); h.Write(data); sinkU = h.Sum64() } })
			tab := crc32.MakeTable(crc32.Castagnoli)
			r3 := testing.Benchmark(func(b *testing.B) { b.SetBytes(int64(n)); for i := 0; i < b.N; i++ { sinkU32 = crc32.Checksum(data, tab) } })
			mb := func(r testing.BenchmarkResult) float64 { return float64(n) / float64(r.NsPerOp()) * 1000 }
			fmt.Printf("SPEED %d 字节输入:maphash.String %d ns(%.0f MB/s);FNV-1a 64 %d ns(%.0f MB/s);CRC32-C %d ns(%.0f MB/s)\n", n, r1.NsPerOp(), mb(r1), r2.NsPerOp(), mb(r2), r3.NsPerOp(), mb(r3))
		}
	case "mapiter":
		// 两个键完全相同的 map,遍历顺序是否相同
		m1, m2 := map[int]int{}, map[int]int{}
		for i := 0; i < 8; i++ { m1[i] = i; m2[i] = i }
		var o1, o2 []int
		for k := range m1 { o1 = append(o1, k) }
		for k := range m2 { o2 = append(o2, k) }
		fmt.Printf("ITER %v | %v\n", o1, o2)
	}
}
'''
d = gdir('mh1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:同一个字符串 "hello",三个不同的进程里的哈希值(Go 1.27.1,arm64 macOS)')
outs = [dict(l.split(' ', 1) for l in run('seed').strip().split('\n')) for _ in range(3)]
for k, lab in (('SEED1', 'maphash.String(seed1, "hello")'), ('SEED1b', '同一个进程里再算一次'), ('SEED2', 'maphash.String(seed2, "hello")(同一进程里的另一个种子)'), ('INCR', 'maphash.Hash 分两段写入 "he" + "llo"(seed1)'), ('CMP', 'maphash.Comparable(seed1, key{1,"x"})'), ('CMP2', '同一个值再算一次'), ('CMP3', 'maphash.Comparable(seed1, key{2,"x"})(不同的值)'), ('FNV', 'FNV-1a 64 位 "hello"')):
    print(f'  {lab:56s} 进程 1:{outs[0][k]}  进程 2:{outs[1][k]}  进程 3:{outs[2][k]}')
print('== 二:分布(16 万个键 "key0".."key159999" 落进 16 个桶)')
print('  ' + run('dist').strip().replace('DIST ', ''))
print('== 三:速度')
print('\n'.join('  ' + l.replace('SPEED ', '') for l in run('speed').strip().split('\n')))
print('== 四:内置 map:两个键完全相同的 map,遍历的起点也不同(8 个键的小 map 里,顺序是一个环形轮转)')
for _ in range(2): print('  ' + run('mapiter').strip().replace('ITER ', '两个键完全相同的 map 的遍历顺序:'))
print('== 五:hash/maphash 文档')
r, o = go(gdir('doc1'), 'doc', 'hash/maphash')
t = ' '.join(l.strip() for l in o.split('\n'))
i = t.find('Package maphash')
j = t.find('for cryptographic use.)', i)
print('  ' + t[i:j + len('for cryptographic use.)')])
