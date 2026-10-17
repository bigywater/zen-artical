import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g92')
SRC = r'''
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"log/slog"
	"os"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func noTime(groups []string, a slog.Attr) slog.Attr {
	if a.Key == slog.TimeKey && len(groups) == 0 { return slog.Attr{} }
	return a
}

type lazy struct{ n *atomic.Int64 }

func (l lazy) LogValue() slog.Value { l.n.Add(1); return slog.StringValue("计算出来的值") }

func main() {
	switch os.Args[1] {
	case "format":
		opts := &slog.HandlerOptions{ReplaceAttr: noTime}
		th := slog.New(slog.NewTextHandler(os.Stdout, opts))
		jh := slog.New(slog.NewJSONHandler(os.Stdout, opts))
		fmt.Println("  TextHandler:")
		fmt.Print("    ")
		th.Info("请求完成", "method", "GET", "path", "/a b", "status", 200, "dur", 1500*time.Microsecond)
		fmt.Print("    ")
		th.With("req_id", 7).WithGroup("http").Info("请求完成", "status", 200)
		fmt.Println("  JSONHandler:")
		fmt.Print("    ")
		jh.Info("请求完成", "method", "GET", "path", "/a b", "status", 200, "dur", 1500*time.Microsecond)
		fmt.Print("    ")
		jh.With("req_id", 7).WithGroup("http").Info("请求完成", "status", 200)
		fmt.Print("    ")
		jh.Info("缺值", "orphan")
		fmt.Println("  (上一行:key 后面没有配对的值,会变成 !BADKEY)")
	case "level":
		var cnt atomic.Int64
		l := slog.New(slog.NewJSONHandler(io.Discard, &slog.HandlerOptions{Level: slog.LevelInfo}))
		l.Debug("调试", "k", lazy{&cnt})
		fmt.Printf("  Level=Info 时调用 Debug,带一个 LogValuer 参数:LogValue 被调用了 %d 次(被过滤的日志不会计算它)\n", cnt.Load())
		l.Info("信息", "k", lazy{&cnt})
		fmt.Printf("  调用 Info:LogValue 被调用了 %d 次\n", cnt.Load())
		x := 42
		a1 := testing.AllocsPerRun(1000, func() { l.Debug("调试", "k", x, "s", "str") })
		a2 := testing.AllocsPerRun(1000, func() { l.LogAttrs(context.Background(), slog.LevelDebug, "调试", slog.Int("k", x), slog.String("s", "str")) })
		a3 := testing.AllocsPerRun(1000, func() { l.Info("信息", "k", x, "s", "str") })
		a4 := testing.AllocsPerRun(1000, func() { l.LogAttrs(context.Background(), slog.LevelInfo, "信息", slog.Int("k", x), slog.String("s", "str")) })
		fmt.Printf("  被过滤的 Debug:l.Debug(…,key,value 形式)%.0f 次分配;l.LogAttrs(…,slog.Attr 形式)%.0f 次分配\n", a1, a2)
		fmt.Printf("  输出到 io.Discard 的 Info:l.Info 形式 %.0f 次分配;LogAttrs 形式 %.0f 次分配\n", a3, a4)
	case "bench":
		x := 42
		jh := slog.New(slog.NewJSONHandler(nopW{}, nil))
		th := slog.New(slog.NewTextHandler(nopW{}, nil))
		js := slog.New(slog.NewJSONHandler(nopW{}, &slog.HandlerOptions{AddSource: true}))
		dis := slog.New(slog.NewJSONHandler(nopW{}, &slog.HandlerOptions{Level: slog.LevelWarn}))
		std := log.New(nopW{}, "", log.LstdFlags)
		stdDiscard := log.New(io.Discard, "", log.LstdFlags)
		b := func(f func()) (int64, int64) { r := testing.Benchmark(func(b *testing.B) { b.ReportAllocs(); for i := 0; i < b.N; i++ { f() } }); return r.NsPerOp(), r.AllocsPerOp() }
		type row struct{ n string; f func() }
		rows := []row{
			{"slog JSONHandler.Info(msg, k, s)", func() { jh.Info("请求完成", "k", x, "s", "str") }},
			{"slog TextHandler.Info(msg, k, s)", func() { th.Info("请求完成", "k", x, "s", "str") }},
			{"slog JSONHandler + AddSource", func() { js.Info("请求完成", "k", x, "s", "str") }},
			{"slog JSONHandler.LogAttrs", func() { jh.LogAttrs(context.Background(), slog.LevelInfo, "请求完成", slog.Int("k", x), slog.String("s", "str")) }},
			{"slog 被级别过滤的 Info", func() { dis.Info("请求完成", "k", x, "s", "str") }},
			{"标准库 log.Printf", func() { std.Printf("请求完成 k=%d s=%s", x, "str") }},
			{"fmt.Fprintf(nopW)", func() { fmt.Fprintf(nopW{}, "请求完成 k=%d s=%s\n", x, "str") }},
			{"标准库 log.Printf(写到 io.Discard)", func() { stdDiscard.Printf("请求完成 k=%d s=%s", x, "str") }},
		}
		for _, r := range rows { ns, al := b(r.f); fmt.Printf("  %-34s %6d ns/次 %3d 次分配\n", r.n, ns, al) }
	case "concurrent":
		var buf bytes.Buffer
		var mu sync.Mutex
		w := writerFunc(func(p []byte) (int, error) { mu.Lock(); defer mu.Unlock(); return buf.Write(p) })
		l := slog.New(slog.NewJSONHandler(w, nil))
		var wg sync.WaitGroup
		for g := 0; g < 8; g++ {
			wg.Add(1)
			go func() { defer wg.Done(); for i := 0; i < 2000; i++ { l.Info("并发日志", "g", g, "i", i, "pad", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") } }()
		}
		wg.Wait()
		lines := bytes.Split(bytes.TrimSpace(buf.Bytes()), []byte("\n"))
		bad := 0
		for _, ln := range lines { var m map[string]any; if json.Unmarshal(ln, &m) != nil { bad++ } }
		fmt.Printf("  8 个 goroutine 各写 2000 条 JSON 日志:共 %d 行,每行都是完整合法 JSON 的有 %d 行(损坏 %d 行)\n", len(lines), len(lines)-bad, bad)
	}
}

type nopW struct{}

func (nopW) Write(p []byte) (int, error) { return len(p), nil }

type writerFunc func([]byte) (int, error)

func (f writerFunc) Write(p []byte) (int, error) { return f(p) }
'''
d = gdir('sl1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:两种 Handler 的输出(Go 1.27.1;为了输出稳定,用 ReplaceAttr 去掉了时间字段)')
print(run('format'))
print('== 二:级别过滤与参数求值')
print(run('level'))
print('== 三:一条日志多少钱(输出到一个什么都不做、但不是 io.Discard 的 writer,arm64 macOS)')
print(run('bench'))
print('== 四:并发写日志会不会交错')
print(run('concurrent'))
print('== 五:文档')
r, o = go(gdir('doc1'), 'doc', 'log/slog')
ls = [l.strip() for l in o.split('\n')]
print('  ' + ' '.join(ls[3:10]))
