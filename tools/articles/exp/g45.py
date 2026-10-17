import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g45')
SRC = r'''
package main

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"regexp"
	"runtime"
	"runtime/pprof"
	"sort"
	"strings"
	"sync"
	"time"
)

var globalCh = make(chan int)

func leakSend()   { ch := make(chan int); go func() { ch <- 1 }() }
func leakRecv()   { ch := make(chan int); go func() { <-ch }() }
func leakNil()    { var ch chan int; go func() { <-ch }() }
func leakMutex()  { var mu sync.Mutex; mu.Lock(); go func() { mu.Lock() }() }
func leakWG()     { var wg sync.WaitGroup; wg.Add(1); go func() { wg.Wait() }() }
func leakSelect() { go func() { select {} }() }
func blockedGlobal() { go func() { <-globalCh }() }

func fixedBuffered() { ch := make(chan int, 1); go func() { ch <- 1 }() }
func fixedCtx() {
	ctx, cancel := context.WithCancel(context.Background())
	ch := make(chan int)
	go func() {
		select {
		case ch <- 1:
		case <-ctx.Done():
		}
	}()
	cancel()
}

var fileLine = regexp.MustCompile(`([\w./-]+\.go:\d+)`)

// 把 goroutine profile(debug=1)整理成 “个数 @ 栈顶的用户函数 文件:行”
func summarize(p *pprof.Profile, label string) {
	var b bytes.Buffer
	p.WriteTo(&b, 1)
	text := b.String()
	blocks := strings.Split(text, "\n\n")
	type row struct {
		n   int
		loc string
	}
	var rows []row
	for _, blk := range blocks {
		lines := strings.Split(strings.TrimSpace(blk), "\n")
		for len(lines) > 0 && !strings.Contains(lines[0], " @") { lines = lines[1:] } // 跳过 “goroutine profile: total N” 这样的标题行
		if len(lines) == 0 { continue }
		var n int
		if _, err := fmt.Sscanf(lines[0], "%d @", &n); err != nil { continue }
		loc := ""
		for _, l := range lines[1:] {
			if strings.Contains(l, "main.") {
				f := strings.Fields(l)
				fn := f[len(f)-2]
				fn = fn[:strings.Index(fn+"+", "+")]
				m := fileLine.FindString(l)
				if i := strings.LastIndex(m, "/"); i >= 0 { m = m[i+1:] }
				loc = fn + " " + m
				break
			}
		}
		if loc == "" { continue }
		rows = append(rows, row{n, loc})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].loc < rows[j].loc })
	fmt.Printf("  %s(%d 个 goroutine):\n", label, p.Count())
	for _, r := range rows { fmt.Printf("    %4d 个 @ %s\n", r.n, r.loc) }
}

func waitReasons() map[string]int {
	var b bytes.Buffer
	pprof.Lookup("goroutine").WriteTo(&b, 2)
	re := regexp.MustCompile(`(?m)^goroutine \d+ \[([^\],]+)`)
	m := map[string]int{}
	for _, x := range re.FindAllStringSubmatch(b.String(), -1) { m[x[1]]++ }
	return m
}

func main() {
	const N = 100
	base := runtime.NumGoroutine()
	for i := 0; i < N; i++ {
		leakSend(); leakRecv(); leakNil(); leakMutex(); leakWG(); leakSelect(); blockedGlobal(); fixedBuffered(); fixedCtx()
	}
	time.Sleep(200 * time.Millisecond)
	fmt.Printf("  起始 NumGoroutine = %d;每种写法调用 %d 次之后 NumGoroutine = %d(7 种泄漏 + 2 种修好的写法)\n", base, N, runtime.NumGoroutine())
	fmt.Println("== 二:goroutine profile(debug=1)按栈聚合:谁卡在哪一行(只列用户代码的栈顶位置)")
	summarize(pprof.Lookup("goroutine"), "goroutine profile")
	fmt.Println("== 三:debug=2 的完整转储里每个 goroutine 的等待原因")
	m := waitReasons()
	var ks []string
	for k := range m { ks = append(ks, k) }
	sort.Strings(ks)
	for _, k := range ks { fmt.Printf("    %-24s %d 个\n", "["+k+"]", m[k]) }
	fmt.Println("== 四:goroutineleak profile:由 GC 判断“被阻塞的 goroutine 等待的同步对象不可达”")
	t0 := time.Now()
	summarize(pprof.Lookup("goroutineleak"), "goroutineleak profile")
	fmt.Printf("  生成 goroutineleak profile 耗时 %.1f ms\n", float64(time.Since(t0).Microseconds())/1000)
	_ = os.Stdout
}
'''
d = gdir('gl1'); write(d, {'main.go': SRC}); mod(d)
print('== 一:几种泄漏写法各调用 100 次(Go 1.27.1)')
rc, o = go(d, 'build', '-gcflags=-l', '-o', 'app')
if rc != 0: print(o)
p = subprocess.run([str(d / 'app')], capture_output=True, text=True, timeout=120)
print((p.stdout + p.stderr).rstrip())
