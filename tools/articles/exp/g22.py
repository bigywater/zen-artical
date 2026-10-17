import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g22')
SRC = r'''
package main

import (
	"errors"
	"fmt"
	"os"
	"runtime"
	"sync"
	"time"
)

func level3() {
	defer fmt.Println("    level3 的 defer")
	fmt.Println("    level3:即将 panic")
	panic("boom")
}

func level2() {
	defer fmt.Println("    level2 的 defer")
	level3()
	fmt.Println("    level2:不会执行到这里")
}

func level1() (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("recover 到:%v", r)
			fmt.Println("    level1 的 defer:recover 之后继续运行")
		}
	}()
	level2()
	return nil
}

func helper() any { return recover() }

func nestedRecover() (res string) {
	defer func() {
		if r := recover(); r != nil { res = fmt.Sprintf("外层 defer 才接住:%v", r) }
	}()
	defer func() {
		r := helper() // recover 不是被 defer 的函数直接调用:返回 nil
		fmt.Printf("    defer 里调用 helper() 里的 recover → %v(没有接住)\n", r)
	}()
	panic("p1")
}

func deferRecoverDirect() (res string) {
	defer func() { res = fmt.Sprint("外层 defer 接住了:", recover()) }()
	defer recover() // 直接 defer recover():不起作用
	panic("p2")
}

func main() {
	if len(os.Args) > 1 { cases(os.Args[1]); return }
	fmt.Println("  调用链 level1 → level2 → level3,level3 panic,只有 level1 里 recover:")
	fmt.Printf("    level1 返回的 err = %v\n", level1())

	fmt.Println("== 二:recover 必须由被 defer 的函数直接调用")
	fmt.Printf("    nestedRecover() = %q\n", nestedRecover())
	fmt.Printf("    deferRecoverDirect() = %q\n", deferRecoverDirect())

	fmt.Println("== 三:runtime.Goexit:退出当前 goroutine,defer 会执行,recover 返回 nil")
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		defer func() { fmt.Printf("    Goexit 期间 recover() = %v;defer 正常执行\n", recover()) }()
		runtime.Goexit()
		fmt.Println("    不会执行到这里")
	}()
	wg.Wait()

	fmt.Println("== 四:panic(nil) 与 runtime.Error")
	func() {
		defer func() {
			r := recover()
			var pe *runtime.PanicNilError
			fmt.Printf("    panic(nil) 之后 recover() = %v;类型 %T;是 *runtime.PanicNilError?%v\n", r, r, errors.As(r.(error), &pe))
		}()
		panic(nil)
	}()
	func() {
		defer func() {
			r := recover()
			re, ok := r.(runtime.Error)
			fmt.Printf("    除以 0:recover() = %v;类型 %T;实现 runtime.Error?%v\n", r, r, ok)
			_ = re
		}()
		a, b := 1, 0
		fmt.Println(a / b)
	}()
	func() {
		defer func() { fmt.Printf("    越界:recover() = %v\n", recover()) }()
		s := []int{1}
		i := 5
		fmt.Println(s[i])
	}()
	_ = time.Now
}

func cases(name string) {
	switch name {
	case "chain":
		defer func() { panic("第二个 panic(在 defer 里)") }()
		panic("第一个 panic")
	case "chain-recovered":
		defer func() { panic("第二个 panic") }()
		defer func() { recover() }()
		panic("第一个 panic")
	case "repanic":
		defer func() {
			r := recover()
			panic(fmt.Sprintf("重新 panic:%v", r))
		}()
		panic("原始 panic")
	case "other-goroutine":
		defer func() { fmt.Println("main 的 recover 收到:", recover()) }()
		go func() { panic("另一个 goroutine 的 panic") }()
		time.Sleep(200 * time.Millisecond)
	case "main-goexit":
		go func() { time.Sleep(50 * time.Millisecond); fmt.Println("    另一个 goroutine 正常结束") }()
		defer fmt.Println("    main 的 defer 执行了")
		runtime.Goexit()
	case "nil-old":
		defer func() { fmt.Printf("    recover() = %v\n", recover()) }()
		panic(nil)
	}
}
'''
print('== 一:栈展开时 defer 的执行顺序,以及 recover 的位置(Go 1.27.1)')
r = grun('pn1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 五:没被 recover 的 panic 会怎样:退出码、panic 链的打印格式(每个情形是独立的进程)')
def run_case(binp, name, env=None):
    e = dict(os.environ); e.update(env or {})
    p = subprocess.run([binp, name], capture_output=True, text=True, timeout=30, env=e)
    return p.returncode, p.stdout + p.stderr
def keep(o, n=6):
    ls = []
    for l in o.split('\n'):
        t = l.strip()
        if t.startswith(('panic:', 'fatal error', 'main 的', '另一个 goroutine 正常', 'recover()')) or (l.startswith('\t') and t.startswith('panic:')):
            ls.append(('(缩进)' if l.startswith('\t') else '') + re.sub(r'0x[0-9a-f]+', '0x…', t))
    return ls[:n]
for name, label in [('chain', 'defer 里再 panic(没有 recover)'), ('chain-recovered', '第一个 panic 被 recover,随后 defer 里又 panic'), ('repanic', 'recover 之后重新 panic'), ('other-goroutine', 'main 里 recover,panic 发生在另一个 goroutine')]:
    rc, o = run_case(r['bin'], name)
    print(f'  {label}:退出码 {rc}')
    for l in keep(o): print('    ' + l)
rc, o = run_case(r['bin'], 'main-goexit')
print(f'  main 里调用 runtime.Goexit:退出码 {rc}')
for l in keep(o, 5): print('    ' + l)

print('== 六:panic(nil) 在旧语义下:GODEBUG=panicnil=1 恢复 Go 1.20 之前的行为')
rc, o = run_case(r['bin'], 'nil-old')
print(f'  默认:退出码 {rc};' + ' / '.join(keep(o, 3)))
rc, o = run_case(r['bin'], 'nil-old', {'GODEBUG': 'panicnil=1'})
print(f'  GODEBUG=panicnil=1:退出码 {rc};' + ' / '.join(keep(o, 3)))
