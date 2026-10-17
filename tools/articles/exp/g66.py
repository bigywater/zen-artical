import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g66')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

func main() {
	runtime.GOMAXPROCS(8)
	switch os.Args[1] {
	case "if", "for":
		useFor := os.Args[1] == "for"
		const consumers = 8
		const items = 3000
		var mu sync.Mutex
		cond := sync.NewCond(&mu)
		queue := 0
		var underflow, got atomic.Int64
		var wg sync.WaitGroup
		for c := 0; c < consumers; c++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for {
					mu.Lock()
					if useFor {
						for queue <= 0 && got.Load() < items { cond.Wait() }
					} else {
						if queue <= 0 && got.Load() < items { cond.Wait() }
					}
					if got.Load() >= items { mu.Unlock(); return }
					if queue <= 0 { underflow.Add(1) } // 醒来后条件仍不成立,却照常取
					queue--
					got.Add(1)
					mu.Unlock()
				}
			}()
		}
		for i := 0; i < items; i++ {
			mu.Lock(); queue++; mu.Unlock()
			cond.Broadcast()
			for t0 := time.Now(); time.Since(t0) < 50*time.Microsecond; {} // 生产者比消费者慢,消费者会排空队列再去 Wait
		}
		mu.Lock()
		for got.Load() < items { mu.Unlock(); time.Sleep(time.Millisecond); mu.Lock() }
		mu.Unlock()
		cond.Broadcast()
		wg.Wait()
		fmt.Printf("  Wait 放在 %s 里:%d 个元素,取走 %d 个,醒来后队列里其实没有元素、却照常取走的次数 = %d\n", map[bool]string{true: "for 循环", false: "if"}[useFor], items, got.Load(), underflow.Load())
	case "wake":
		// 8 个消费者都在 Wait;放入 1 个元素,看有多少个被唤醒(从 Wait 返回)
		for _, mode := range []string{"Signal", "Broadcast"} {
			var mu sync.Mutex
			cond := sync.NewCond(&mu)
			var woke atomic.Int64
			ready := 0
			avail := 0
			var wg sync.WaitGroup
			for c := 0; c < 8; c++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					mu.Lock(); ready++
					cond.Wait()
					woke.Add(1)
					if avail > 0 { avail-- }
					mu.Unlock()
				}()
			}
			for { mu.Lock(); r := ready; mu.Unlock(); if r == 8 { break }; time.Sleep(time.Millisecond) }
			time.Sleep(20 * time.Millisecond)
			mu.Lock(); avail = 1; mu.Unlock()
			if mode == "Signal" { cond.Signal() } else { cond.Broadcast() }
			time.Sleep(50 * time.Millisecond)
			fmt.Printf("  8 个 goroutine 在 Wait,放入 1 个元素后调用 %s:从 Wait 返回的有 %d 个\n", mode, woke.Load())
			mu.Lock(); avail = 8; mu.Unlock()
			cond.Broadcast() // 收尾
			wg.Wait()
		}
	case "lost":
		var mu sync.Mutex
		cond := sync.NewCond(&mu)
		cond.Signal() // 此时没有人在等:信号直接丢失
		done := make(chan bool)
		go func() { mu.Lock(); cond.Wait(); mu.Unlock(); done <- true }()
		select {
		case <-done: fmt.Println("  Signal 先于 Wait 调用:消费者被唤醒了")
		case <-time.After(300 * time.Millisecond): fmt.Println("  Signal 先于 Wait 调用:300 ms 后消费者仍卡在 Wait(信号丢失了)")
		}
	case "pingpong":
		const N = 200000
		var mu sync.Mutex
		cond := sync.NewCond(&mu)
		turn := 0
		var wg sync.WaitGroup
		wg.Add(1)
		t0 := time.Now()
		go func() { defer wg.Done(); for i := 0; i < N; i++ { mu.Lock(); for turn != 1 { cond.Wait() }; turn = 0; cond.Signal(); mu.Unlock() } }()
		for i := 0; i < N; i++ { mu.Lock(); for turn != 0 { cond.Wait() }; turn = 1; cond.Signal(); mu.Unlock() }
		wg.Wait()
		e1 := time.Since(t0)
		a, b := make(chan int), make(chan int)
		wg.Add(1)
		t0 = time.Now()
		go func() { defer wg.Done(); for i := 0; i < N; i++ { <-a; b <- 1 } }()
		for i := 0; i < N; i++ { a <- 1; <-b }
		wg.Wait()
		e2 := time.Since(t0)
		fmt.Printf("  两个 goroutine 来回传递 %d 次:sync.Cond %.0f ns/个来回;无缓冲 channel %.0f ns/个来回\n", N, float64(e1.Nanoseconds())/N, float64(e2.Nanoseconds())/N)
	}
}
'''
d = gdir('cd1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr).rstrip()
print('== 一:Wait 放在 if 里还是 for 里(8 个消费者、1 个生产者每隔约 50 µs 放一个元素并 Broadcast,3000 个元素;Go 1.27.1,arm64 macOS)')
for m in ('if', 'for'): print(run(m))
print('== 二:Signal 与 Broadcast 唤醒几个')
print(run('wake'))
print('== 三:信号先发后等,会丢')
print(run('lost'))
print('== 四:用 Cond 和用 channel 来回传递的耗时')
print(run('pingpong'))
print('== 五:文档原文(go doc sync.Cond.Wait)')
r, o = go(gdir('doc1'), 'doc', 'sync.Cond.Wait')
print('\n'.join('  ' + l.strip() for l in o.split('\n')[3:] if l.strip()))
