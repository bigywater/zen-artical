import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g16')
LOOP = r'''
package main

import (
	"fmt"
	"sort"
	"sync"
)

func main() {
	var fs []func() int
	for i := 0; i < 3; i++ {
		fs = append(fs, func() int { return i })
	}
	fmt.Print("  三个闭包捕获 for 的 i,循环结束后依次调用:")
	for _, f := range fs { fmt.Print(" ", f()) }
	fmt.Println()

	var ps []*int
	for i := 0; i < 3; i++ { ps = append(ps, &i) }
	fmt.Printf("  取 &i 存进切片:三个指针相同?%v;解引用得到 %d %d %d\n", ps[0] == ps[1] && ps[1] == ps[2], *ps[0], *ps[1], *ps[2])

	var mu sync.Mutex
	var wg sync.WaitGroup
	var got []int
	for _, v := range []int{10, 20, 30} {
		wg.Add(1)
		go func() { defer wg.Done(); mu.Lock(); got = append(got, v); mu.Unlock() }()
	}
	wg.Wait()
	sort.Ints(got)
	fmt.Printf("  for range 里起 goroutine 引用 v(每个 goroutine 排队后才运行),收集到:%v\n", got)
}
'''
print('== 一:同一份代码,只改 go.mod 里的 go 指令:1.21(旧语义,整个循环共用一个 i)与 1.22 及以上(每次迭代一个新的 i)')
for ver in ('1.21', '1.22', '1.27'):
    d = gdir(f'cv{ver}'); write(d, {'main.go': LOOP}); mod(d, go=ver)
    rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
    r = subprocess.run([str(d / 'app')], capture_output=True, text=True)
    print(f'  go.mod 写 go {ver}:')
    for l in r.stdout.rstrip().split('\n'): print('  ' + l)

print('== 二:单个文件用 //go:build 版本约束,可以让这个文件按旧语义编译(go.mod 仍是 1.27)')
d = gdir('cvfile'); mod(d, go='1.27')
write(d, {'main.go': '''
package main

import "fmt"

func main() {
	fmt.Println("  新语义文件:", collectNew())
	fmt.Println("  旧语义文件:", collectOld())
}
''', 'new.go': '''
package main

func collectNew() (r []int) {
	var fs []func() int
	for i := 0; i < 3; i++ { fs = append(fs, func() int { return i }) }
	for _, f := range fs { r = append(r, f()) }
	return
}
''', 'old.go': '''
//go:build go1.21

package main

func collectOld() (r []int) {
	var fs []func() int
	for i := 0; i < 3; i++ { fs = append(fs, func() int { return i }) }
	for _, f := range fs { r = append(r, f()) }
	return
}
'''})
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
print(subprocess.run([str(d / 'app')], capture_output=True, text=True).stdout.rstrip())

print('== 三:编译器告诉你哪些循环受影响:-gcflags=-d=loopvar=2')
d = gdir('cvlv'); write(d, {'main.go': LOOP}); mod(d, go='1.27')
rc, o = go(d, 'build', '-gcflags=-d=loopvar=2', '-o', 'app')
for l in o.split('\n'):
    if 'loop variable' in l or 'loopvar' in l: print('  ' + l.replace('./main.go', 'main.go'))
if not any('loop variable' in l for l in o.split('\n')): print('  (无输出)原始输出前几行:' + ' / '.join(o.split('\n')[:4]))

print('== 四:代价:100 次迭代、闭包被保存下来,两种语义各分配几次(testing.AllocsPerRun)')
AL = r'''
package main

import (
	"fmt"
	"testing"
)

var sink []func() int

//go:noinline
func build(n int) {
	fs := make([]func() int, 0, n)
	for i := 0; i < n; i++ { fs = append(fs, func() int { return i }) }
	sink = fs
}

//go:noinline
func immediate(n int) int {
	s := 0
	for i := 0; i < n; i++ { f := func() int { return i }; s += f() }
	return s
}

var sinkN int

func main() {
	fmt.Printf("  闭包被保存(逃逸)的循环 build(100):%.0f 次分配;只在循环里立刻调用的闭包 immediate(100):%.0f 次分配\n", testing.AllocsPerRun(100, func() { build(100) }), testing.AllocsPerRun(100, func() { sinkN += immediate(100) }))
}
'''
for ver in ('1.21', '1.27'):
    d = gdir(f'cva{ver}'); write(d, {'main.go': AL}); mod(d, go=ver)
    rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
    print(f'  go.mod 写 go {ver}:' + subprocess.run([str(d / 'app')], capture_output=True, text=True).stdout.strip().lstrip())

print('== 五:闭包捕获的是变量,不是值')
CL = r'''
package main

import "fmt"

func counter() (func() int, func() int) {
	n := 0
	return func() int { n++; return n }, func() int { return n }
}

func main() {
	inc, get := counter()
	inc(); inc(); inc()
	fmt.Printf("  两个闭包共享同一个 n:inc() 三次后 get() = %d\n", get())
	x := 1
	f := func() int { return x }
	x = 99
	fmt.Printf("  x := 1;f := func() int { return x };x = 99;f() = %d(闭包创建之后的修改也看得到)\n", f())
	y := 1
	g := func(v int) func() int { return func() int { return v } }(y)
	y = 99
	fmt.Printf("  把 y 作为参数传进去(参数是拷贝):y = 99 之后 g() = %d\n", g())
}
'''
d = gdir('cvcl'); write(d, {'main.go': CL}); mod(d, go='1.27')
rc, o = go(d, 'build', '-gcflags=-m', '-o', 'app')
print(subprocess.run([str(d / 'app')], capture_output=True, text=True).stdout.rstrip())
for l in o.split('\n'):
    if 'moved to heap' in l: print('  编译器:' + l.replace('./main.go', 'main.go'))
