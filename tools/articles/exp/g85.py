import sys, os, re, time, statistics, subprocess, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g85')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"sort"
	"syscall"
	"time"
)

func us(d time.Duration) float64 { return float64(d.Nanoseconds()) / 1000 }

func summarize(xs []float64) string {
	sort.Float64s(xs)
	return fmt.Sprintf("最小 %.0f µs / 中位 %.0f µs / 最大 %.0f µs", xs[0], xs[len(xs)/2], xs[len(xs)-1])
}

func main() {
	dir := os.Args[2]
	buf := make([]byte, 4096)
	switch os.Args[1] {
	case "latency":
		f, _ := os.Create(dir + "/a.bin")
		var w, s1, s2 []float64
		for i := 0; i < 200; i++ {
			t0 := time.Now(); f.Write(buf); w = append(w, us(time.Since(t0)))
			t0 = time.Now(); syscall.Fsync(int(f.Fd())); s1 = append(s1, us(time.Since(t0)))
			f.Write(buf)
			t0 = time.Now(); f.Sync(); s2 = append(s2, us(time.Since(t0)))
		}
		f.Close()
		fmt.Printf("  追加写 4 KiB(f.Write,只进内核页缓存):%s(200 次)\n", summarize(w))
		fmt.Printf("  写完调用 syscall.Fsync(fd)(macOS 上的 fsync):%s(200 次)\n", summarize(s1))
		fmt.Printf("  写完调用 f.Sync()(Go 在 macOS 上用 F_FULLFSYNC):%s(200 次)\n", summarize(s2))
	case "visible":
		f, _ := os.Create(dir + "/b.bin")
		f.WriteString("hello")
		g, _ := os.Open(dir + "/b.bin")
		b := make([]byte, 10)
		n, _ := g.Read(b)
		fmt.Printf("  f.Write 之后没有 Sync、没有 Close,另一个文件句柄立刻读到:%q(%d 字节)——数据已经对别的读者可见,但还没有保证落盘\n", string(b[:n]), n)
		f.Close(); g.Close()
	case "patterns":
		const N = 300
		run := func(name string, flags int, every int) {
			os.Remove(dir + "/c.bin")
			f, _ := os.OpenFile(dir+"/c.bin", os.O_CREATE|os.O_WRONLY|os.O_APPEND|flags, 0o644)
			t0 := time.Now()
			for i := 0; i < N; i++ {
				f.Write(buf[:100])
				if every > 0 && (i+1)%every == 0 { f.Sync() }
			}
			if every > 0 && N%every != 0 { f.Sync() }
			d := time.Since(t0)
			f.Close()
			fmt.Printf("  追加 %d 条各 100 字节的记录:%-34s 总耗时 %8.1f ms,平均每条 %8.1f µs\n", N, name, float64(d.Microseconds())/1000, us(d)/N)
		}
		run("不 Sync", 0, 0)
		run("每条都 f.Sync()", 0, 1)
		run("每 10 条 f.Sync() 一次(批量)", 0, 10)
		run("每 100 条 f.Sync() 一次(批量)", 0, 100)
		run("打开时加 os.O_SYNC(每次 Write 都同步)", os.O_SYNC, 0)
		os.Remove(dir + "/c.bin")
	case "atomic":
		var steps = map[string][]float64{}
		for i := 0; i < 50; i++ {
			t0 := time.Now()
			f, _ := os.Create(dir + "/tmp.new")
			f.Write(buf)
			steps["创建 + 写入"] = append(steps["创建 + 写入"], us(time.Since(t0)))
			t0 = time.Now(); f.Sync(); steps["f.Sync()"] = append(steps["f.Sync()"], us(time.Since(t0)))
			f.Close()
			t0 = time.Now(); os.Rename(dir+"/tmp.new", dir+"/final.bin"); steps["os.Rename"] = append(steps["os.Rename"], us(time.Since(t0)))
			t0 = time.Now(); dd, _ := os.Open(dir); dd.Sync(); dd.Close(); steps["目录 Sync()"] = append(steps["目录 Sync()"], us(time.Since(t0)))
		}
		for _, k := range []string{"创建 + 写入", "f.Sync()", "os.Rename", "目录 Sync()"} {
			fmt.Printf("  安全替换文件的各步骤(50 次):%-10s %s\n", k, summarize(steps[k]))
		}
	}
}
'''
d = gdir('fs1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
tmp = d / 'data'; tmp.mkdir(exist_ok=True)
def run(m):
    p = subprocess.run([str(d / 'app'), m, str(tmp)], capture_output=True, text=True, timeout=600)
    return tidy(p.stdout + p.stderr)
print('== 一:Write、fsync、Sync 各要多久(Go 1.27.1,arm64 macOS,内置 SSD)')
print(run('latency'))
print('== 二:Write 返回之后,别的读者能看到数据吗')
print(run('visible'))
print('== 三:追加日志的几种同步策略')
print(run('patterns'))
print('== 四:“写临时文件 → Sync → 重命名 → 同步目录”的各步骤成本')
print(run('atomic'))
shutil.rmtree(tmp, ignore_errors=True)
print('== 五:源码注释(internal/poll/fd_fsync_darwin.go)')
src = open(GOROOT + '/src/internal/poll/fd_fsync_darwin.go').read()
m = re.search(r'// Fsync invokes SYS_FCNTL.*?\n(?=func)', src, re.S)
print('  ' + '\n  '.join(l.strip() for l in m.group(0).split('\n') if l.strip()))
r, o = go(gdir('doc1'), 'doc', 'os.File.Sync')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:8] if l.strip()))
