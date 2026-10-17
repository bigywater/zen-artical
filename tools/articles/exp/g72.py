import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g72')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"runtime"
	"syscall"
	"time"
)

func cpu() float64 {
	var r syscall.Rusage
	syscall.Getrusage(0, &r)
	return float64(r.Utime.Sec+r.Stime.Sec) + float64(r.Utime.Usec+r.Stime.Usec)/1e6
}

func main() {
	switch os.Args[1] {
	case "fair":
		a, b := make(chan int, 1), make(chan int, 1)
		var na, nb int
		for i := 0; i < 1_000_000; i++ {
			a <- 1; b <- 1
			select {
			case <-a: na++; <-b
			case <-b: nb++; <-a
			}
		}
		fmt.Printf("  两个 channel 总是同时就绪,select 100 万次:选中第一个 %d 次,第二个 %d 次(%.1f%% / %.1f%%)\n", na, nb, float64(na)/1e4, float64(nb)/1e4)
	case "priority":
		hi, lo := make(chan int, 1), make(chan int, 1)
		var plainLo, nestedLo int
		for i := 0; i < 1_000_000; i++ {
			hi <- 1; lo <- 1
			select {
			case <-hi: <-lo
			case <-lo: plainLo++; <-hi
			}
		}
		for i := 0; i < 1_000_000; i++ {
			hi <- 1; lo <- 1
			select {
			case <-hi:
				<-lo
			default:
				select {
				case <-hi:
					<-lo
				case <-lo:
					nestedLo++
					<-hi
				}
			}
		}
		fmt.Printf("  高、低优先级 channel 总是同时就绪,各 100 万次:普通 select 选中低优先级 %d 次;先单独试高优先级再兜底的嵌套 select 选中低优先级 %d 次\n", plainLo, nestedLo)
	case "tie":
		picked := map[string]int{}
		for i := 0; i < 100000; i++ {
			res := make(chan int, 1)
			res <- 1
			timer := time.NewTimer(0)
			time.Sleep(50 * time.Microsecond) // 让定时器已经到期
			select {
			case <-res: picked["结果"]++
			case <-timer.C: picked["超时"]++
			}
		}
		fmt.Printf("  结果和超时同时就绪(定时器已到期、结果也已放进 channel),10 万次:选中“结果” %d 次,选中“超时” %d 次\n", picked["结果"], picked["超时"])
	case "nil":
		// 合并两个 channel;其中一个先关闭
		for _, useNil := range []bool{false, true} {
			a, b := make(chan int), make(chan int)
			go func() { for i := 0; i < 5; i++ { a <- i }; close(a) }()
			go func() { time.Sleep(200 * time.Millisecond); for i := 0; i < 5; i++ { b <- i }; close(b) }()
			spins := 0
			c0 := cpu()
			aa, bb := (<-chan int)(a), (<-chan int)(b)
			for aa != nil || bb != nil {
				select {
				case _, ok := <-aa:
					spins++
					if !ok && useNil { aa = nil }
				case _, ok := <-bb:
					spins++
					if !ok { bb = nil }
				}
				if !useNil && spins > 3_000_000 { break }
			}
			fmt.Printf("  a 很快关闭,b 要 200 ms 后才有数据。关闭后%s:循环了 %d 次,进程 CPU 时间 %.3f 秒\n", map[bool]string{true: "把 a 置为 nil", false: "不处理(继续 select 已关闭的 a)"}[useNil], spins, cpu()-c0)
		}
	case "default":
		ch := make(chan int)
		c0 := cpu(); n := 0
		end := time.Now().Add(300 * time.Millisecond)
		for time.Now().Before(end) { select { case <-ch: default: n++ } }
		fmt.Printf("  select + default 的忙等待 300 ms:循环 %d 次,CPU 时间 %.3f 秒\n", n, cpu()-c0)
		c0 = cpu()
		go func() { time.Sleep(300 * time.Millisecond); ch <- 1 }()
		<-ch
		fmt.Printf("  阻塞的 <-ch 等 300 ms:CPU 时间 %.3f 秒\n", cpu()-c0)
		_ = runtime.NumCPU
	}
}
'''
d = gdir('sl1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:多个 case 同时就绪时 select 怎么选(Go 1.27.1,arm64 macOS)')
print(run('fair'))
print('== 二:想要优先级怎么办')
print(run('priority'))
print('== 三:结果和超时撞车')
print(run('tie'))
print('== 四:已关闭的 channel 在 select 里会一直就绪;置为 nil 才能禁用这个 case')
print(run('nil'))
print('== 五:select + default 的忙等待 vs 阻塞等待')
print(run('default'))
print('== 六:语言规范原文(go_spec.html)')
t = open(GOROOT + '/doc/go_spec.html').read()
t = re.sub(r'<[^>]+>', '', t); t = re.sub(r'\s+', ' ', t)
for k in ('If one or more of the communications can proceed, a single one that can proceed is chosen via a uniform pseudo-random selection. Otherwise, if there is a default case, that case is chosen.', 'Since communication on nil channels can never proceed, a select with only nil channels and no default case blocks forever.'):
    print('  ' + (k if k in t else '(未找到)' + k))
