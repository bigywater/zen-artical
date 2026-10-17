import sys, os, re, html, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g60')
HB = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

var x int

func main() {
	switch os.Args[1] {
	case "chan-send":
		c := make(chan int, 10)
		go func() { x = 1; c <- 0 }()
		<-c
		_ = x
	case "chan-close":
		c := make(chan int)
		go func() { x = 1; close(c) }()
		<-c
		_ = x
	case "unbuf-recv":
		c := make(chan int)
		go func() { x = 1; <-c }()
		c <- 0
		_ = x
	case "buf1-recv-single":
		c := make(chan int, 1)
		go func() { x = 1; time.Sleep(5 * time.Millisecond); <-c }()
		c <- 0
		time.Sleep(20 * time.Millisecond)
		_ = x
	case "buf1-recv-second":
		c := make(chan int, 1)
		c <- 0
		go func() { x = 1; <-c }()
		c <- 0
		_ = x
	case "mutex":
		var mu sync.Mutex
		mu.Lock()
		go func() { x = 1; mu.Unlock() }()
		mu.Lock()
		_ = x
	case "atomic-flag":
		var f atomic.Bool
		go func() { x = 1; f.Store(true) }()
		for !f.Load() { runtime.Gosched() }
		_ = x
	case "once":
		var o sync.Once
		var wg sync.WaitGroup
		for i := 0; i < 4; i++ { wg.Add(1); go func() { defer wg.Done(); o.Do(func() { x = 1 }); _ = x }() }
		wg.Wait()
	case "waitgroup":
		var wg sync.WaitGroup
		wg.Add(1)
		go func() { defer wg.Done(); x = 1 }()
		wg.Wait()
		_ = x
	case "go-stmt":
		x = 1
		done := make(chan bool)
		go func() { _ = x; close(done) }()
		<-done
	case "sleep-only":
		go func() { x = 1 }()
		time.Sleep(50 * time.Millisecond)
		_ = x
	case "gosched-only":
		go func() { x = 1 }()
		for i := 0; i < 100; i++ { runtime.Gosched() }
		time.Sleep(10 * time.Millisecond)
		_ = x
	}
	fmt.Println("ok")
}
'''
LIT = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sync/atomic"
)

var x, y, r1, r2 int32
var ax, ay atomic.Int32
var data int32
var flag int32
var aflag atomic.Int32
var gen, done atomic.Int64

const N = 2_000_000

func main() {
	runtime.GOMAXPROCS(4)
	mode := os.Args[1]
	var viol int
	switch mode {
	case "sb-plain", "sb-atomic":
		atom := mode == "sb-atomic"
		go func() {
			for i := int64(1); i <= N; i++ {
				for gen.Load() != i {}
				if atom { ax.Store(1); r1 = ay.Load() } else { x = 1; r1 = y }
				done.Add(1)
			}
		}()
		go func() {
			for i := int64(1); i <= N; i++ {
				for gen.Load() != i {}
				if atom { ay.Store(1); r2 = ax.Load() } else { y = 1; r2 = x }
				done.Add(1)
			}
		}()
		for i := int64(1); i <= N; i++ {
			x, y = 0, 0; ax.Store(0); ay.Store(0)
			gen.Store(i)
			for done.Load() != 2*i {}
			if r1 == 0 && r2 == 0 { viol++ }
		}
		fmt.Printf("%d\n", viol)
	case "mp-plain", "mp-atomic":
		atom := mode == "mp-atomic"
		var f, d int32
		var wr1, wr2 int32
		go func() {
			for i := int64(1); i <= N; i++ {
				for gen.Load() != i {}
				if atom { data = 1; aflag.Store(1) } else { data = 1; flag = 1 }
				done.Add(1)
			}
		}()
		go func() {
			for i := int64(1); i <= N; i++ {
				for gen.Load() != i {}
				if atom { wr1 = aflag.Load(); wr2 = data } else { wr1 = flag; wr2 = data }
				done.Add(1)
			}
		}()
		for i := int64(1); i <= N; i++ {
			data, flag = 0, 0; aflag.Store(0)
			gen.Store(i)
			for done.Load() != 2*i {}
			f, d = wr1, wr2
			if f == 1 && d == 0 { viol++ }
		}
		fmt.Printf("%d\n", viol)
	}
}
'''
def build(name, src, race=False):
    dd = gdir(name); write(dd, {'main.go': src}); mod(dd)
    rc, o = go(dd, 'build', *(['-race'] if race else []), '-o', 'app'); assert rc == 0, o
    return dd / 'app'
hb = build('mm1', HB, race=True)
lit = build('mm2', LIT)
print('== 一:用 -race 检测每种“同步”到底有没有建立 happens-before(Go 1.27.1,arm64 macOS;没有竞争 = 这种同步足以让读看到写)')
rows = [
    ('chan-send', '缓冲 channel:写 x 后 send,另一边 receive 后读 x'),
    ('chan-close', 'close 之后另一边 receive 到零值,再读 x'),
    ('unbuf-recv', '无缓冲 channel:对方先 receive,send 完成之后读 x'),
    ('buf1-recv-single', '容量 1 的 channel:只 send 一次,不等 receive 就读 x(睡 20 ms 后读)'),
    ('buf1-recv-second', '容量 1 的 channel:第 2 次 send 完成之后读 x(第 1 次 receive 在 goroutine 里)'),
    ('mutex', 'goroutine 里写 x 再 Unlock,main 的第二次 Lock 之后读 x'),
    ('atomic-flag', 'atomic.Bool 的 Store(true)/Load() 当作发布标志,之后读普通变量 x'),
    ('once', 'sync.Once 里写 x,4 个 goroutine 在 Do 之后读 x'),
    ('waitgroup', 'goroutine 里写 x 再 Done,Wait 之后读 x'),
    ('go-stmt', 'go 语句之前写 x,新 goroutine 里读 x'),
    ('sleep-only', '只靠 time.Sleep(50ms)'),
    ('gosched-only', '只靠 runtime.Gosched() 与 Sleep'),
]
for mode, desc in rows:
    p = subprocess.run([str(hb), mode], capture_output=True, text=True, timeout=60)
    t = p.stdout + p.stderr
    r = '报告 DATA RACE' if 'DATA RACE' in t else '无竞争'
    print(f'  [{mode}] {desc} → {r}(退出码 {p.returncode})')
print('== 二:弱内存序的真实表现:arm64 上的两个 litmus 测试(各 200 万轮,普通变量 vs sync/atomic)')
def lrun(m):
    p = subprocess.run([str(lit), m], capture_output=True, text=True, timeout=300)
    return int(p.stdout.strip())
print('  SB(store buffering):线程 A: x=1; r1=y  线程 B: y=1; r2=x。顺序一致时不可能 r1=0 且 r2=0')
print(f'    普通变量:r1=0 且 r2=0 出现 {lrun("sb-plain")} 次')
print(f'    sync/atomic:r1=0 且 r2=0 出现 {lrun("sb-atomic")} 次')
print('  MP(message passing):线程 A: data=1; flag=1  线程 B: f=flag; d=data。看到 flag=1 却看到 data=0 就是重排')
print(f'    普通变量:f=1 且 d=0 出现 {lrun("mp-plain")} 次')
print(f'    flag 用 atomic:f=1 且 d=0 出现 {lrun("mp-atomic")} 次')
print('== 三:Go 内存模型文档(本机 $GOROOT/doc/go_mem.html)原文')
t = open(GOROOT + '/doc/go_mem.html').read()
t = re.sub(r'<[^>]+>', '', t); t = html.unescape(t); t = re.sub(r'\s+', ' ', t)
for k, n in (('A send on a channel is synchronized before the completion of the corresponding receive from that channel.', 0),
             ('The closing of a channel is synchronized before a receive that returns a zero value because the channel is closed.', 0),
             ('A receive from an unbuffered channel is synchronized before the completion of the corresponding send on that channel.', 0),
             ('The kth receive from a channel with capacity C is synchronized before the completion of the k+Cth send on that channel.', 0),
             ('call n of l.Unlock() is synchronized before call m of l.Lock() returns.', 0),
             ('The go statement that starts a new goroutine is synchronized before the start of the goroutine\'s execution.', 0),
             ('If the effect of an atomic operation A is observed by atomic operation B, then A is synchronized before B.', 0),
             ('A data race is defined as a write to a memory location happening concurrently with another read or write to that same location, unless all the accesses involved are atomic data accesses as provided by the sync/atomic package.', 0),
             ('If you must read the rest of this document to understand the behavior of your program, you are being too clever. Don\'t be clever.', 0)):
    print(('  ' if k in t else '  (未找到)') + k)
