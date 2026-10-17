import sys, os, re, time, statistics, subprocess, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g68')
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

	"golang.org/x/sync/singleflight"
)

func ms(d time.Duration) string { return fmt.Sprintf("%.0f ms", float64(d.Microseconds())/1000) }

var calls atomic.Int64

func slowLoad(key string) (any, error) {
	calls.Add(1)
	time.Sleep(100 * time.Millisecond)
	return "值-" + key, nil
}

func main() {
	switch os.Args[1] {
	case "same":
		for _, useSF := range []bool{false, true} {
			calls.Store(0)
			var g singleflight.Group
			var wg sync.WaitGroup
			var shared atomic.Int64
			t0 := time.Now()
			for i := 0; i < 100; i++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					if useSF {
						_, _, sh := g.Do("k", func() (any, error) { return slowLoad("k") })
						if sh { shared.Add(1) }
					} else {
						slowLoad("k")
					}
				}()
			}
			wg.Wait()
			fmt.Printf("  100 个并发请求同一个键,加载函数耗时 100 ms:%s → 加载函数被调用 %d 次,总用时 %s%s\n", map[bool]string{true: "singleflight", false: "不合并"}[useSF], calls.Load(), ms(time.Since(t0)), map[bool]string{true: fmt.Sprintf(",shared=true 的调用方 %d 个", shared.Load()), false: ""}[useSF])
		}
	case "keys":
		var g singleflight.Group
		calls.Store(0)
		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(1)
			key := fmt.Sprintf("k%d", i%4)
			go func() { defer wg.Done(); g.Do(key, func() (any, error) { return slowLoad(key) }) }()
		}
		wg.Wait()
		fmt.Printf("  100 个并发请求,分布在 4 个不同的键上:加载函数被调用 %d 次\n", calls.Load())
	case "notcache":
		var g singleflight.Group
		calls.Store(0)
		for i := 0; i < 3; i++ { g.Do("k", func() (any, error) { return slowLoad("k") }) }
		fmt.Printf("  同一个键顺序调用 3 次(每次等上一次结束):加载函数被调用 %d 次(singleflight 不是缓存)\n", calls.Load())
	case "stampede":
		// 缓存 TTL 到期的瞬间:200 个请求在 50 ms 内陆续到达,后端慢 100 ms
		for _, useSF := range []bool{false, true} {
			calls.Store(0)
			var mu sync.Mutex
			cache := map[string]string{}
			var g singleflight.Group
			get := func(k string) string {
				mu.Lock(); v, ok := cache[k]; mu.Unlock()
				if ok { return v }
				load := func() (any, error) { v, _ := slowLoad(k); mu.Lock(); cache[k] = v.(string); mu.Unlock(); return v, nil }
				if useSF { v, _, _ := g.Do(k, load); return v.(string) }
				v2, _ := load(); return v2.(string)
			}
			var wg sync.WaitGroup
			t0 := time.Now()
			for i := 0; i < 200; i++ {
				wg.Add(1)
				go func() { defer wg.Done(); time.Sleep(time.Duration(i) * 250 * time.Microsecond); get("hot") }()
			}
			wg.Wait()
			fmt.Printf("  缓存刚过期,200 个请求在 50 ms 内陆续到达,后端每次 100 ms:%s → 打到后端 %d 次,总用时 %s\n", map[bool]string{true: "用 singleflight", false: "不合并"}[useSF], calls.Load(), ms(time.Since(t0)))
		}
	case "error":
		var g singleflight.Group
		var wg sync.WaitGroup
		var errs [3]error
		for i := 0; i < 3; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				time.Sleep(time.Duration(i) * 10 * time.Millisecond)
				_, errs[i], _ = g.Do("k", func() (any, error) { time.Sleep(50 * time.Millisecond); return nil, errors.New("后端失败") })
			}()
		}
		wg.Wait()
		fmt.Printf("  三个请求先后到达(0/10/20 ms),第一个的加载函数返回错误:三个调用方得到的错误 = %v / %v / %v\n", errs[0], errs[1], errs[2])
	case "cancel":
		var g singleflight.Group
		var wg sync.WaitGroup
		res := make([]string, 2)
		load := func(ctx context.Context) func() (any, error) {
			return func() (any, error) {
				select {
				case <-time.After(100 * time.Millisecond): return "ok", nil
				case <-ctx.Done(): return nil, ctx.Err()
				}
			}
		}
		ctx1, cancel1 := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel1()
		ctx2 := context.Background()
		for i, ctx := range []context.Context{ctx1, ctx2} {
			wg.Add(1)
			go func() {
				defer wg.Done()
				time.Sleep(time.Duration(i) * 5 * time.Millisecond)
				v, err, _ := g.Do("k", load(ctx))
				res[i] = fmt.Sprintf("%v/%v", v, err)
			}()
		}
		wg.Wait()
		fmt.Printf("  第一个调用方的 ctx 20 ms 后超时,第二个调用方的 ctx 不会超时,加载函数用的是第一个调用方的 ctx:第一个得到 %s;第二个得到 %s\n", res[0], res[1])
	case "dochan":
		var g singleflight.Group
		t0 := time.Now()
		ch := g.DoChan("k", func() (any, error) { time.Sleep(200 * time.Millisecond); return "ok", nil })
		select {
		case r := <-ch: fmt.Printf("  DoChan 结果 %v\n", r.Val)
		case <-time.After(30 * time.Millisecond): fmt.Printf("  DoChan + select:调用方自己在 %s 超时离开,后台的加载仍会继续\n", ms(time.Since(t0)))
		}
	case "panic":
		var g singleflight.Group
		var wg sync.WaitGroup
		var got [3]string
		for i := 0; i < 3; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				defer func() { if r := recover(); r != nil { got[i] = fmt.Sprintf("recover 到 panic(%T)", r) } }()
				time.Sleep(time.Duration(i) * 5 * time.Millisecond)
				g.Do("k", func() (any, error) { time.Sleep(30 * time.Millisecond); panic("加载函数 panic") })
				got[i] = "正常返回"
			}()
		}
		wg.Wait()
		fmt.Printf("  加载函数 panic:三个调用方的结果 = %v\n", got)
	}
}
'''
d = gdir('sf1'); write(d, {'main.go': SRC}); mod(d)
rc, o = goget(d, 'golang.org/x/sync@v0.24.0'); assert rc == 0, o
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=60)
    return tidy(p.stdout + p.stderr)
print('== 一:合并同一个键的并发请求(golang.org/x/sync v0.24.0;Go 1.27.1,arm64 macOS)')
print(run('same')); print(run('keys')); print(run('notcache'))
print('== 二:缓存击穿:热点键刚过期')
print(run('stampede'))
print('== 三:错误也被共享;调用方的 ctx 被“借用”')
print(run('error')); print(run('cancel')); print(run('dochan'))
print('== 四:加载函数 panic')
print(run('panic'))
print('== 五:源码里的几处注释(singleflight.go)')
src = glob.glob(str(GT / '_gopath' / 'pkg' / 'mod' / 'golang.org' / 'x' / 'sync@v0.24.0' / 'singleflight' / 'singleflight.go'))[0]
t = open(src).read()
for pat in (r'// Do executes and returns the results of the given function.*?// The return value shared indicates whether v was given to multiple callers\.', r'// Forget tells the singleflight to forget about a key\..*?\n(?=func)'):
    m = re.search(pat, t, re.S)
    print('  ' + '\n  '.join(l.strip() for l in m.group(0).split('\n') if l.strip()))
