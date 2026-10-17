import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g56')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/pprof"
	"strconv"
	"testing"
)

var keepY, keepZ [][]byte
var sink []byte

//go:noinline
func garbageX() { for i := 0; i < 100_000; i++ { sink = make([]byte, 1024) } }  // 约 100 MB,全部成为垃圾

//go:noinline
func retainY() { for i := 0; i < 50; i++ { keepY = append(keepY, make([]byte, 1<<20)) } } // 50 MB 保留

//go:noinline
func retainZ() { for i := 0; i < 160_000; i++ { keepZ = append(keepZ, make([]byte, 64)) } } // 约 10 MB(小对象)保留

func write(path string) {
	f, _ := os.Create(path)
	pprof.Lookup("heap").WriteTo(f, 0)
	f.Close()
}

func main() {
	mode := os.Args[1]
	if len(os.Args) > 3 { r, _ := strconv.Atoi(os.Args[3]); runtime.MemProfileRate = r }
	switch mode {
	case "basic":
		garbageX(); retainY(); retainZ()
		runtime.GC()
		write(os.Args[2])
	case "lag":
		runtime.GC()
		retainY() // 在最近一次 GC 之后才分配
		write(os.Args[2] + ".nogc")
		runtime.GC()
		write(os.Args[2])
	case "rate":
		retainZ()
		runtime.GC()
		write(os.Args[2])
	case "cost":
		for _, r := range []int{0, 512 * 1024, 4096, 1} {
			runtime.MemProfileRate = r
			res := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sink = make([]byte, 64) } })
			fmt.Printf("  MemProfileRate=%-7d 分配 64 字节:%d ns/次\n", r, res.NsPerOp())
		}
	}
}
'''
d = gdir('hp1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(mode, prof, rate=None):
    a = [str(d / 'app'), mode, str(d / prof)] + ([str(rate)] if rate is not None else [])
    p = subprocess.run(a, capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr).rstrip()
def pp(prof, idx, n=6):
    r = subprocess.run([GO, 'tool', 'pprof', f'-sample_index={idx}', '-top', f'-nodecount={n}', '-unit=mb', str(d / 'app'), str(d / prof)], capture_output=True, text=True, env=genv())
    return [l for l in (r.stdout + r.stderr).split('\n') if l.strip() and not re.match(r'(Time|File|Build ID):', l)]
def flat(prof, idx, fn):
    r = subprocess.run([GO, 'tool', 'pprof', f'-sample_index={idx}', '-top', '-nodecount=20', '-unit=kb', str(d / 'app'), str(d / prof)], capture_output=True, text=True, env=genv())
    for l in r.stdout.split('\n'):
        m = re.match(r'\s*(\S+?)(kB|MB|B)\s+\S+%\s+\S+%\s+\S+\s+\S+%\s+main\.' + fn + r'\b', l)
        if m: return float(m.group(1)) * {'kB': 1, 'MB': 1024, 'B': 1/1024}[m.group(2)]
    return 0.0
print('== 一:同一个 heap profile 的 inuse_space 与 alloc_space(Go 1.27.1,arm64 macOS;MemProfileRate 默认 512 KiB)')
print('  程序:garbageX 分配约 100 MB 的 1 KiB 切片但全部丢弃;retainY 分配并保留 50 个 1 MiB;retainZ 保留 16 万个 64 字节对象(约 10 MB);最后 runtime.GC() 再写 profile')
run('basic', 'basic.prof')
for idx in ('inuse_space', 'alloc_space'):
    print(f'  -sample_index={idx}:')
    for l in pp('basic.prof', idx): print('    ' + l)
print('== 二:heap profile 是“最近一次 GC 时”的快照')
run('lag', 'lag.prof')
print('  retainY 在最近一次 GC 之后才分配 50 MiB:')
print(f"    不再 GC 直接写 profile:retainY 的 inuse_space = {flat('lag.prof.nogc', 'inuse_space', 'retainY'):.0f} kB")
print(f"    runtime.GC() 之后再写:retainY 的 inuse_space = {flat('lag.prof', 'inuse_space', 'retainY'):.0f} kB")
print('== 三:采样率对小对象估计精度的影响(retainZ 的统计里还包括 keepZ 切片自身的底层数组,[]byte 头每个 24 字节;MemProfileRate=1 时每次分配都被记录,可当作基准;每个采样率各运行 6 次)')
for rate in (1, 4096, 524288, 16777216):
    vals = []
    for i in range(6):
        run('rate', 'rate.prof', rate)
        vals.append(flat('rate.prof', 'inuse_space', 'retainZ'))
    print(f'  MemProfileRate={rate:>9d}:retainZ 估计 最小 {min(vals):7.0f} kB / 中位 {statistics.median(vals):7.0f} kB / 最大 {max(vals):7.0f} kB')
print('== 四:采样率对分配速度的影响(testing.Benchmark,分配 64 字节)')
print(run('cost', 'cost.prof'))
print('== 五:文档与源码的原文')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/runtime/'
def sed(f, a, b, label=None):
    o = subprocess.run(['sed', '-n', f'{a},{b}p', base + f], capture_output=True, text=True).stdout.rstrip()
    print(f'  {label or f}:{a}-{b}')
    for l in o.split('\n'): print('    ' + l)
p = base + 'pprof/pprof.go'
n = int(subprocess.run(['grep', '-n', 'The heap profile reports statistics as of the most recently completed', p], capture_output=True, text=True).stdout.split(':')[0])
o = subprocess.run(['sed', '-n', f'{n},{n + 5}p', p], capture_output=True, text=True).stdout.rstrip()
print(f'  pprof/pprof.go:{n}-{n + 5}')
for l in o.split('\n'): print('    ' + l)
n = int(subprocess.run(['grep', '-n', '^// MemProfileRate controls', base + 'mprof.go'], capture_output=True, text=True).stdout.split(':')[0])
sed('mprof.go', n, n + 14)
