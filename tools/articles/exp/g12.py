import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g12')
W = r'''
package main

import (
	"fmt"
	"os"
	"sync"
)

func main() {
	mode := os.Args[1]
	n := 100000
	m := map[int]int{}
	var wg sync.WaitGroup
	defer func() { fmt.Println("recover 收到:", recover()) }()
	switch mode {
	case "ww": // 两个 goroutine 同时写
		for g := 0; g < 2; g++ {
			wg.Add(1)
			go func(g int) { defer wg.Done(); for i := 0; i < n; i++ { m[i*2+g] = i } }(g)
		}
	case "rw": // 一个写一个读
		wg.Add(2)
		go func() { defer wg.Done(); for i := 0; i < n; i++ { m[i] = i } }()
		go func() { defer wg.Done(); s := 0; for i := 0; i < n; i++ { s += m[i] }; _ = s }()
	case "iw": // 一个遍历一个写
		for i := 0; i < 1000; i++ { m[i] = i }
		wg.Add(2)
		go func() { defer wg.Done(); for r := 0; r < 200; r++ { for range m {} } }()
		go func() { defer wg.Done(); for i := 0; i < n; i++ { m[i%1000] = i } }()
	case "mutex":
		var mu sync.Mutex
		for g := 0; g < 2; g++ {
			wg.Add(1)
			go func(g int) { defer wg.Done(); for i := 0; i < n; i++ { mu.Lock(); m[i*2+g] = i; mu.Unlock() } }(g)
		}
	case "syncmap":
		var sm sync.Map
		for g := 0; g < 2; g++ {
			wg.Add(1)
			go func(g int) { defer wg.Done(); for i := 0; i < n; i++ { sm.Store(i*2+g, i) } }(g)
		}
	case "tiny": // 每个 goroutine 只写 3 次
		for g := 0; g < 2; g++ {
			wg.Add(1)
			go func(g int) { defer wg.Done(); for i := 0; i < 3; i++ { m[i*2+g] = i } }(g)
		}
	}
	wg.Wait()
	fmt.Println("正常结束,len =", len(m))
}
'''
def run(binp, mode, tmo=60):
    try:
        r = subprocess.run([binp, mode], capture_output=True, text=True, timeout=tmo)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -9, '(超时)'
def first(o, n=2):
    ls = [re.sub(r'0x[0-9a-f]+', '0x…', l.strip()) for l in o.split('\n') if l.strip() and not l.startswith(('goroutine', 'main.', '\t', 'created by', 'exit status'))]
    return ' / '.join(ls[:n])
print('== 一:没有同步地并发读写 map:运行时直接 fatal(Go 1.27.1,arm64)——不是 panic,recover 接不住')
r = grun('mc1', {'main.go': W})
assert r['crc'] == 0, r['cout']
for mode, label in [('ww', '两个 goroutine 同时写'), ('rw', '一个写、一个读'), ('iw', '一个遍历、一个写')]:
    rc, o = run(r['bin'], mode)
    print(f'  {label}(模式 {mode}):退出码 {rc};{first(o, 1)};输出里有 "recover 收到"?{"recover 收到" in o}')
print('  (每个程序都用 defer + recover() 包住了 main:fatal error 不是 panic,defer 没有机会执行)')

print('== 二:检测是尽力而为,不保证每次都发现:同一个程序各跑 30 次')
for mode, label in [('ww', '2 个 goroutine 各写 10 万次'), ('tiny', '2 个 goroutine 各只写 3 次')]:
    fat = ok = 0
    kinds = {}
    for _ in range(30):
        rc, o = run(r['bin'], mode)
        if 'fatal error' in o:
            fat += 1; k = [l for l in o.split('\n') if l.startswith('fatal error')][0]; kinds[k] = kinds.get(k, 0) + 1
        else: ok += 1
    print(f'  {label}:30 次里 fatal {fat} 次、正常结束 {ok} 次;fatal 的信息分布:{kinds}')

print('== 三:检测的原理:Map 里有一个 writing 标志。写入前发现它非 0 就 fatal,写完发现它是 0 也 fatal,否则 XOR 1(runtime 源码的 fatal 调用点与标志定义)')
base = '/opt/homebrew/Cellar/go/1.27.1/libexec/src/internal/runtime/maps/'
o = subprocess.run('grep -n "fatal(\\"concurrent" ' + base + 'map.go ' + base + 'table.go ' + base + 'runtime_swiss.go 2>/dev/null; grep -n "writing" ' + base + 'map.go | head -12', shell=True, capture_output=True, text=True).stdout
for l in o.strip().split('\n')[:16]: print('  ' + l.replace(base, 'internal/runtime/maps/'))

print('== 四:加了同步之后:sync.Mutex 与 sync.Map 各跑 10 次;再用 -race 编译看竞态检测器怎么报告')
for mode in ('mutex', 'syncmap'):
    res = [run(r['bin'], mode) for _ in range(10)]
    print(f'  {mode}:10 次里正常结束 {sum(1 for rc, o in res if "正常结束" in o)} 次;fatal {sum(1 for rc, o in res if "fatal" in o)} 次')
rr = grun('mc2', {'main.go': W}, race=True)
rc, o = run(rr['bin'], 'ww')
lines = [l.strip() for l in o.split('\n') if l.strip()]
hit = [l for l in lines if l.startswith(('WARNING', 'fatal', 'Write at', 'Previous write at', 'Found'))][:5]
print(f'  -race 编译的 ww 模式:退出码 {rc};输出里的关键行:' + ' / '.join(re.sub(r'0x[0-9a-f]+', '0x…', l) for l in hit))
rc2, o2 = run(rr['bin'], 'mutex')
print(f'  -race 编译的 mutex 模式:退出码 {rc2};输出:{first(o2)}')
