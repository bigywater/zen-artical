import sys, os, re, time, statistics, subprocess, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g82')
SRC = r'''
package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
	"time"
)

type cw struct{ w io.Writer; calls int; bytes int }

func (c *cw) Write(p []byte) (int, error) { c.calls++; c.bytes += len(p); return c.w.Write(p) }

type cr struct{ r io.Reader; calls int }

func (c *cr) Read(p []byte) (int, error) { c.calls++; return c.r.Read(p) }

func med(f func() float64) float64 {
	xs := []float64{f(), f(), f(), f(), f()}
	sort.Float64s(xs)
	return xs[2]
}

func ms(t0 time.Time) float64 { return float64(time.Since(t0).Microseconds()) / 1000 }

func main() {
	dir := os.Args[2]
	line := []byte("0123456789abcde\n") // 16 字节
	const N = 500_000
	switch os.Args[1] {
	case "write":
		type cfg struct{ name string; size int }
		for _, c := range []cfg{{"不缓冲", 0}, {"bufio 16 B", 16}, {"bufio 512 B", 512}, {"bufio 4096 B(默认)", 4096}, {"bufio 64 KiB", 64 << 10}, {"bufio 1 MiB", 1 << 20}} {
			var calls int
			t := med(func() float64 {
				f, _ := os.Create(dir + "/w.bin")
				cc := &cw{w: f}
				t0 := time.Now()
				var w io.Writer = cc
				var bw *bufio.Writer
				if c.size > 0 { bw = bufio.NewWriterSize(cc, c.size); w = bw }
				for i := 0; i < N; i++ { w.Write(line) }
				if bw != nil { bw.Flush() }
				d := ms(t0)
				calls = cc.calls
				f.Close()
				return d
			})
			fmt.Printf("  写 %d 次 16 字节(共 %.0f MB)到文件:%-20s 对底层 Write 的调用 %7d 次,耗时 %7.1f ms\n", N, float64(N*16)/1e6, c.name, calls, t)
		}
		os.Remove(dir + "/w.bin")
	case "flush":
		f, _ := os.Create(dir + "/f.bin")
		bw := bufio.NewWriter(f)
		for i := 0; i < 1000; i++ { bw.Write(line) } // 16000 字节
		f.Close() // 忘了 Flush
		st, _ := os.Stat(dir + "/f.bin")
		fmt.Printf("  写了 16000 字节,没有 Flush 就 Close 文件:磁盘上的文件大小 = %d 字节(缓冲区里还剩 %d 字节没写出去)\n", st.Size(), bw.Buffered())
		os.Remove(dir + "/f.bin")
	case "read":
		// 准备一个 128 MiB 文件
		src := dir + "/r.bin"
		f, _ := os.Create(src)
		chunk := bytes.Repeat([]byte("0123456789abcdef"), 1<<16)
		for i := 0; i < 128; i++ { f.Write(chunk) }
		f.Close()
		const total = 128 << 20
		for _, size := range []int{0, 16, 512, 4096, 65536, 1 << 20} {
			var calls int
			t := med(func() float64 {
				in, _ := os.Open(src)
				cc := &cr{r: in}
				t0 := time.Now()
				var n int
				if size == 0 {
					buf := make([]byte, 1<<20)
					for { k, err := cc.Read(buf); n += k; if err != nil { break } }
				} else {
					br := bufio.NewReaderSize(cc, size)
					for { _, err := br.ReadByte(); if err != nil { break }; n++ }
					if n != total { panic("n") }
				}
				d := ms(t0); calls = cc.calls; in.Close(); return d
			})
			name := fmt.Sprintf("bufio %d B", size)
			if size == 0 { name = "直接用 1 MiB 缓冲区 Read" }
			if size == 4096 { name = "bufio 4096 B(默认)" }
			unit := "逐字节 ReadByte"
			if size == 0 { unit = "整块 Read" }
			fmt.Printf("  读 128 MiB 文件(%s):%-24s 对底层 Read 的调用 %8d 次,耗时 %7.1f ms\n", unit, name, calls, t)
		}
		os.Remove(src)
	case "scanner":
		long := strings.Repeat("x", 100_000)
		sc := bufio.NewScanner(strings.NewReader("short\n" + long + "\nafter\n"))
		var got []int
		for sc.Scan() { got = append(got, len(sc.Text())) }
		fmt.Printf("  默认 Scanner 读到一行 100000 字节的内容:读到的行长 = %v,sc.Err() = %v\n", got, sc.Err())
		sc2 := bufio.NewScanner(strings.NewReader("short\n" + long + "\nafter\n"))
		sc2.Buffer(make([]byte, 0, 4096), 1<<20)
		got = nil
		for sc2.Scan() { got = append(got, len(sc2.Text())) }
		fmt.Printf("  sc.Buffer(…, 1 MiB) 之后:读到的行长 = %v,sc.Err() = %v\n", got, sc2.Err())
		fmt.Printf("  bufio.MaxScanTokenSize = %d\n", bufio.MaxScanTokenSize)
		br := bufio.NewReader(strings.NewReader("short\n" + long + "\nafter\n"))
		var lens []int
		for { l, err := br.ReadString('\n'); if len(l) > 0 { lens = append(lens, len(l)) }; if err != nil { break } }
		fmt.Printf("  bufio.Reader.ReadString('\\n') 没有行长限制:读到的行长(含换行符)= %v\n", lens)
	}
}
'''
d = gdir('bf1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
tmp = d / 'data'; tmp.mkdir(exist_ok=True)
def run(m):
    p = subprocess.run([str(d / 'app'), m, str(tmp)], capture_output=True, text=True, timeout=900)
    return tidy(p.stdout + p.stderr)
print('== 一:写:缓冲区大小对系统调用次数和耗时的影响(Go 1.27.1,arm64 macOS)')
print(run('write'))
print('== 二:忘了 Flush')
print(run('flush'))
print('== 三:读:逐字节读 128 MiB 文件,缓冲区大小的影响(每项 5 次取中位数)')
print(run('read'))
print('== 四:Scanner 的行长限制')
print(run('scanner'))
shutil.rmtree(tmp, ignore_errors=True)
