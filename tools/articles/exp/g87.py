import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g87')
SRC = r'''
package main

import (
	"bytes"
	"fmt"
	"os"
	"strings"
	"testing"
)

var sinkS string

const piece = "0123456789abcdef" // 16 字节

func concat(n int) string { s := ""; for i := 0; i < n; i++ { s += piece }; return s }

func builder(n int) string { var b strings.Builder; for i := 0; i < n; i++ { b.WriteString(piece) }; return b.String() }

func builderGrow(n int) string { var b strings.Builder; b.Grow(n * len(piece)); for i := 0; i < n; i++ { b.WriteString(piece) }; return b.String() }

func buffer(n int) string { var b bytes.Buffer; for i := 0; i < n; i++ { b.WriteString(piece) }; return b.String() }

func join(n int) string { parts := make([]string, n); for i := range parts { parts[i] = piece }; return strings.Join(parts, "") }

func sprintf(n int) string { s := ""; for i := 0; i < n; i++ { s = fmt.Sprintf("%s%s", s, piece) }; return s }

func main() {
	switch os.Args[1] {
	case "bench":
		type fn struct{ name string; f func(int) string }
		fns := []fn{{"s += piece", concat}, {"strings.Builder", builder}, {"Builder + Grow", builderGrow}, {"bytes.Buffer", buffer}, {"strings.Join", join}, {`Sprintf("%s%s")`, sprintf}}
		for _, n := range []int{100, 1000, 10000, 50000} {
			for _, f := range fns {
				if f.name == `Sprintf("%s%s")` && n > 10000 { continue }
				if f.name == "s += piece" && n > 50000 { continue }
				r := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { sinkS = f.f(n) } })
				fmt.Printf("  拼接 %6d 段(每段 16 字节,结果 %7d 字节):%-16s %12d ns/次 %10d B/次 %6d 次分配\n", n, n*16, f.name, r.NsPerOp(), r.AllocedBytesPerOp(), r.AllocsPerOp())
			}
		}
	case "string":
		var b strings.Builder
		b.WriteString(strings.Repeat("x", 1000))
		var buf bytes.Buffer
		buf.WriteString(strings.Repeat("x", 1000))
		fmt.Printf("  strings.Builder.String():每次 %.0f 次分配;bytes.Buffer.String():每次 %.0f 次分配(复制了一份)\n", testing.AllocsPerRun(1000, func() { sinkS = b.String() }), testing.AllocsPerRun(1000, func() { sinkS = buf.String() }))
	case "copy":
		defer func() { fmt.Printf("  复制一个已写入的 Builder 后再写:panic: %v\n", recover()) }()
		var a strings.Builder
		a.WriteString("hello")
		b := a
		b.WriteString("x")
	case "growth":
		var b strings.Builder
		prev := -1
		var caps []string
		for i := 0; i < 2000; i++ {
			b.WriteString(piece)
			if b.Cap() != prev { caps = append(caps, fmt.Sprintf("%d", b.Cap())); prev = b.Cap() }
		}
		fmt.Printf("  Builder 连续写 2000 个 16 字节段(共 32000 字节),容量变化依次为:%s\n", strings.Join(caps, " → "))
	}
}
'''
d = gdir('sb1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=900)
    return tidy(p.stdout + p.stderr)
print('== 一:几种拼接方式(Go 1.27.1,arm64 macOS)')
print(run('bench'))
print('== 二:String() 要不要复制')
print(run('string'))
print('== 三:Builder 的容量怎么长')
print(run('growth'))
print('== 四:不能复制')
print(run('copy'))
print('== 五:文档')
r, o = go(gdir('doc1'), 'doc', 'strings.Builder')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:9] if l.strip()))
