import sys, os, re, time, statistics, subprocess, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g81')
SRC = r'''
package main

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io"
	"net"
	"os"
	"sort"
	"strings"
	"testing"
	"time"
)

type countR struct {
	r     io.Reader
	sizes []int
	n     int
}

func (c *countR) Read(p []byte) (int, error) {
	if len(c.sizes) < 3 { c.sizes = append(c.sizes, len(p)) }
	c.n++
	return c.r.Read(p)
}

type wt struct{ r io.Reader; viaRead, viaWriteTo int }

func (w *wt) Read(p []byte) (int, error) { w.viaRead++; return w.r.Read(p) }
func (w *wt) WriteTo(dst io.Writer) (int64, error) { w.viaWriteTo++; return io.Copy(dst, struct{ io.Reader }{w.r}) }

type rf struct{ bytes.Buffer; viaReadFrom, viaWrite int }

func (r *rf) ReadFrom(src io.Reader) (int64, error) { r.viaReadFrom++; return r.Buffer.ReadFrom(src) }
func (r *rf) Write(p []byte) (int, error)            { r.viaWrite++; return r.Buffer.Write(p) }

func timeIt(f func()) float64 {
	var xs []float64
	for i := 0; i < 5; i++ { t0 := time.Now(); f(); xs = append(xs, float64(time.Since(t0).Microseconds())/1000) }
	sort.Float64s(xs)
	return xs[2]
}

func main() {
	data := []byte(strings.Repeat("0123456789abcdef", 1<<16)) // 1 MiB
	switch os.Args[1] {
	case "bufsize":
		c := &countR{r: bytes.NewReader(data)}
		n, _ := io.Copy(struct{ io.Writer }{io.Discard}, struct{ io.Reader }{c})
		fmt.Printf("  两边都只暴露 Read / Write 时,io.Copy 把 %d 字节(1 MiB)拷过去:调用 Read %d 次,前 3 次传入的缓冲区长度 = %v\n", n, c.n, c.sizes)
		c1 := &countR{r: bytes.NewReader(data)}
		io.Copy(io.Discard, struct{ io.Reader }{c1})
		fmt.Printf("  目标换成 io.Discard(它自带 ReadFrom):Read %d 次,缓冲区长度 = %v\n", c1.n, c1.sizes)
		c2 := &countR{r: bytes.NewReader(data)}
		buf := make([]byte, 4096)
		io.CopyBuffer(struct{ io.Writer }{io.Discard}, struct{ io.Reader }{c2}, buf)
		fmt.Printf("  io.CopyBuffer 传 4096 字节的缓冲区:Read %d 次,缓冲区长度 = %v\n", c2.n, c2.sizes)
		r1 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { io.Copy(struct{ io.Writer }{io.Discard}, io.LimitReader(bytes.NewReader(data), 100)) } })
		r2 := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { io.Copy(struct{ io.Writer }{io.Discard}, io.LimitReader(bytes.NewReader(data), 1<<20)) } })
		fmt.Printf("  源是 io.LimitReader:限 100 字节时每次 io.Copy 分配 %d B;限 1 MiB 时每次分配 %d B(源码里会按 LimitedReader.N 缩小缓冲区)\n", r1.AllocedBytesPerOp(), r2.AllocedBytesPerOp())
	case "iface":
		w := &wt{r: bytes.NewReader(data)}
		var dst bytes.Buffer
		io.Copy(&dst, w)
		fmt.Printf("  源实现了 WriterTo:io.Copy 调用了 WriteTo %d 次,Read %d 次(WriteTo 里自己再 Copy 时会走 Read)\n", w.viaWriteTo, w.viaRead)
		w2 := &wt{r: bytes.NewReader(data)}
		d := &rf{}
		io.Copy(d, struct{ io.Reader }{w2})
		fmt.Printf("  目标实现了 ReaderFrom、源只有 Read:ReadFrom %d 次,Write %d 次\n", d.viaReadFrom, d.viaWrite)
		d2 := &rf{}
		io.Copy(struct{ io.Writer }{d2}, struct{ io.Reader }{bytes.NewReader(data)})
		fmt.Printf("  两边都只暴露 Read / Write:ReadFrom %d 次,Write %d 次\n", d2.viaReadFrom, d2.viaWrite)
		a1 := testing.AllocsPerRun(20, func() { io.Copy(io.Discard, bytes.NewReader(data)) })
		a2 := testing.AllocsPerRun(20, func() { io.Copy(io.Discard, struct{ io.Reader }{bytes.NewReader(data)}) })
		fmt.Printf("  拷到 io.Discard:源是 *bytes.Reader(有 WriteTo)每次 %.0f 次分配;把它包成只有 Read 的 struct 后每次 %.0f 次分配\n", a1, a2)
	case "file":
		dir := os.Args[2]
		src := dir + "/src.bin"
		f, _ := os.Create(src)
		chunk := bytes.Repeat([]byte("x"), 1<<20)
		for i := 0; i < 256; i++ { f.Write(chunk) }
		f.Close()
		copyFile := func(hide bool) float64 {
			return timeIt(func() {
				in, _ := os.Open(src); out, _ := os.Create(dir + "/dst.bin")
				if hide { io.Copy(struct{ io.Writer }{out}, struct{ io.Reader }{in}) } else { io.Copy(out, in) }
				out.Close(); in.Close()
			})
		}
		var xa, xb []float64
		for i := 0; i < 3; i++ { xa = append(xa, copyFile(false)); xb = append(xb, copyFile(true)) }
		sort.Float64s(xa); sort.Float64s(xb)
		t1, t2 := xa[1], xb[1]
		fmt.Printf("  文件到文件 256 MiB:io.Copy(*os.File, *os.File) 中位 %.0f ms(%.0f MiB/s);包一层隐藏 ReaderFrom/WriterTo 后 %.0f ms(%.0f MiB/s)\n", t1, 256/(t1/1000), t2, 256/(t2/1000))
		sha := func(tee bool) float64 {
			return timeIt(func() {
				in, _ := os.Open(src); h := sha256.New()
				if tee { io.Copy(io.Discard, io.TeeReader(in, h)) } else { io.Copy(h, in) }
				in.Close()
			})
		}
		fmt.Printf("  读 256 MiB 文件算 SHA-256:io.Copy(hash, file) 中位 %.0f ms;io.Copy(Discard, io.TeeReader(file, hash)) 中位 %.0f ms\n", sha(false), sha(true))
		ln, _ := net.Listen("tcp", "127.0.0.1:0")
		go func() { for { c, err := ln.Accept(); if err != nil { return }; go func() { io.Copy(io.Discard, c); c.Close() }() } }()
		tcpCopy := func(hide bool) float64 {
			return timeIt(func() {
				c, _ := net.Dial("tcp", ln.Addr().String())
				in, _ := os.Open(src)
				if hide { io.Copy(struct{ io.Writer }{c}, struct{ io.Reader }{in}) } else { io.Copy(c, in) }
				in.Close(); c.Close()
			})
		}
		var ya, yb []float64
		for i := 0; i < 3; i++ { ya = append(ya, tcpCopy(false)); yb = append(yb, tcpCopy(true)) }
		sort.Float64s(ya); sort.Float64s(yb)
		t3, t4 := ya[1], yb[1]
		fmt.Printf("  文件到本机 TCP 连接 256 MiB:io.Copy(*net.TCPConn, *os.File) 中位 %.0f ms(%.0f MiB/s);隐藏接口后 %.0f ms(%.0f MiB/s)\n", t3, 256/(t3/1000), t4, 256/(t4/1000))
		os.Remove(src); os.Remove(dir + "/dst.bin")
	}
}
'''
d = gdir('io1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); print(o) if rc else None

def run(*a):
    p = subprocess.run([str(d / 'app'), *a], capture_output=True, text=True, timeout=600)
    return tidy(p.stdout + p.stderr)
print('== 一:io.Copy 的缓冲区(Go 1.27.1,arm64 macOS)')
print(run('bufsize'))
print('== 二:io.Copy 怎么挑实现:WriterTo / ReaderFrom')
print(run('iface'))
tmp = d / 'data'; tmp.mkdir(exist_ok=True)
print('== 三:真实文件与 TCP:隐藏了 ReadFrom/WriteTo 之后慢多少(两种写法交替各跑 3 轮,每轮内部 5 次取中位数,再取 3 轮的中位数)')
print(run('file', str(tmp)))
shutil.rmtree(tmp, ignore_errors=True)
print('== 四:io 包文档里 Copy 的说明')
r, o = go(gdir('doc1'), 'doc', 'io.Copy')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:14] if l.strip()))
