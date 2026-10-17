import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g67')
SRC = r'''
package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/sync/errgroup"
)

func ms(d time.Duration) string { return fmt.Sprintf("%.0f ms", float64(d.Microseconds())/1000) }

func main() {
	switch os.Args[1] {
	case "cancel":
		t0 := time.Now()
		g, ctx := errgroup.WithContext(context.Background())
		for i := 1; i <= 5; i++ {
			g.Go(func() error {
				if i == 2 {
					time.Sleep(50 * time.Millisecond)
					return fmt.Errorf("任务 %d 失败", i)
				}
				select {
				case <-time.After(time.Duration(i*200) * time.Millisecond):
					fmt.Printf("  任务 %d 正常做完,用时 %s\n", i, ms(time.Since(t0)))
					return nil
				case <-ctx.Done():
					fmt.Printf("  任务 %d 在 %s 发现 ctx 已取消:%v\n", i, ms(time.Since(t0)), context.Cause(ctx))
					return ctx.Err()
				}
			})
		}
		err := g.Wait()
		fmt.Printf("  g.Wait() 在 %s 返回:%v\n", ms(time.Since(t0)), err)
	case "waitgroup":
		t0 := time.Now()
		var wg sync.WaitGroup
		var first error
		var once sync.Once
		for i := 1; i <= 5; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				if i == 2 { time.Sleep(50 * time.Millisecond); once.Do(func() { first = fmt.Errorf("任务 %d 失败", i) }); return }
				time.Sleep(time.Duration(i*200) * time.Millisecond)
			}()
		}
		wg.Wait()
		fmt.Printf("  只用 WaitGroup(没有取消):wg.Wait() 在 %s 才返回,第一个错误是:%v\n", ms(time.Since(t0)), first)
	case "firsterr":
		var g errgroup.Group
		for i := 1; i <= 3; i++ {
			g.Go(func() error { time.Sleep(time.Duration(i*20) * time.Millisecond); return fmt.Errorf("错误 %d", i) })
		}
		fmt.Printf("  3 个任务先后都出错(20/40/60 ms),g.Wait() 返回:%v\n", g.Wait())
	case "limit":
		var g errgroup.Group
		g.SetLimit(3)
		var cur, max atomic.Int64
		t0 := time.Now()
		var blocked time.Duration
		for i := 0; i < 12; i++ {
			s := time.Now()
			g.Go(func() error {
				n := cur.Add(1)
				for { m := max.Load(); if n <= m || max.CompareAndSwap(m, n) { break } }
				time.Sleep(30 * time.Millisecond)
				cur.Add(-1)
				return nil
			})
			blocked += time.Since(s)
		}
		g.Wait()
		fmt.Printf("  SetLimit(3),12 个各 30 ms 的任务:同时运行的最大个数 = %d,总用时 %s,调用 g.Go 累计阻塞 %s\n", max.Load(), ms(time.Since(t0)), ms(blocked))
		var g2 errgroup.Group
		g2.SetLimit(1)
		g2.Go(func() error { time.Sleep(50 * time.Millisecond); return nil })
		ok := g2.TryGo(func() error { return nil })
		fmt.Printf("  SetLimit(1) 且已有一个任务在跑时,TryGo 返回 %v(不阻塞)\n", ok)
		g2.Wait()
	case "panic":
		defer func() { fmt.Printf("  g.Wait() 所在的 goroutine 捕获到 panic:%v\n", recover()) }()
		var g errgroup.Group
		g.Go(func() error { panic("任务里 panic 了") })
		g.Wait()
		fmt.Println("  g.Wait() 正常返回了(panic 没有传到 Wait)")
	case "reuse":
		g, ctx := errgroup.WithContext(context.Background())
		g.Go(func() error { return errors.New("x") })
		g.Wait()
		fmt.Printf("  Wait 返回之后 ctx.Err() = %v(WithContext 的 ctx 在 Wait 返回时被取消,即使没有错误也会取消)\n", ctx.Err())
		g3, ctx3 := errgroup.WithContext(context.Background())
		g3.Go(func() error { return nil })
		g3.Wait()
		fmt.Printf("  所有任务都成功时,Wait 返回之后 ctx.Err() = %v\n", ctx3.Err())
	}
}
'''
d = gdir('eg1'); write(d, {'main.go': SRC}); mod(d)
rc, o = goget(d, 'golang.org/x/sync@latest'); print('goget:', rc, o[-200:])
assert rc == 0
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
ver = open(d / 'go.mod').read()
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=60)
    t = tidy(p.stdout + p.stderr)
    if m == 'panic':
        lines = t.split('\n')
        keep = [l.strip() for l in lines if l.startswith('panic:') or 'errgroup.go' in l or 'main.go' in l]
        return f'  进程退出码 {p.returncode}(崩溃);' + ' | '.join(x[:140] for x in keep[:4])
    return t
print('== 零:依赖版本(go.mod)')
print('  ' + re.search(r'golang.org/x/sync v\S+', ver).group(0))
print('== 一:第一个错误取消其他任务(5 个任务;任务 2 在 50 ms 出错,其它任务本来要做 400/600/800/1000 ms 以及 200 ms)')
print(run('cancel'))
print(run('waitgroup'))
print('== 二:多个错误只返回第一个')
print(run('firsterr'))
print('== 三:SetLimit 限制并发数')
print(run('limit'))
print('== 四:任务里 panic(g.Wait() 所在的 goroutine 里加了 defer recover)')
print(run('panic'))
print('== 五:WithContext 的 ctx 什么时候取消')
print(run('reuse'))
print('== 六:errgroup 源码(Group 结构体与 Go 方法)')
import glob
src = glob.glob(str(GT / '_gopath' / 'pkg' / 'mod' / 'golang.org' / 'x' / 'sync@*' / 'errgroup' / 'errgroup.go'))[0]
t = open(src).read()
m = re.search(r'type Group struct \{.*?\n\}', t, re.S)
print('  ' + m.group(0).replace('\t', '    ').replace('\n', '\n  '))
m = re.search(r'func \(g \*Group\) Go\(f func\(\) error\) \{.*?\n\}\n', t, re.S)
print('  ' + m.group(0).replace('\t', '    ').replace('\n', '\n  '))
