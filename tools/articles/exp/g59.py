import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g59')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

var counter int
var flag int64
var data = make([]int, 1<<20)
var mu sync.Mutex

func compute() int {
	s := 0
	for r := 0; r < 40; r++ {
		for i := range data { data[i] += i ^ r; s += data[i] & 7 }
	}
	return s
}

func lockHeavy() int {
	var wg sync.WaitGroup
	total := 0
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() { defer wg.Done(); for i := 0; i < 200000; i++ { mu.Lock(); total++; mu.Unlock() } }()
	}
	wg.Wait()
	return total
}

func main() {
	switch os.Args[1] {
	case "counter":
		var wg sync.WaitGroup
		for g := 0; g < 2; g++ {
			wg.Add(1)
			go func() { defer wg.Done(); for i := 0; i < 1000; i++ { counter++ } }()
		}
		wg.Wait()
		fmt.Println("counter =", counter)
	case "sleepordered":
		go func() { counter = 42 }()
		time.Sleep(100 * time.Millisecond) // 靠睡眠“保证”写在读之前,但没有同步
		fmt.Println("读到", counter)
	case "atomicmixed":
		go func() { atomic.StoreInt64(&flag, 1) }()
		time.Sleep(50 * time.Millisecond)
		fmt.Println("普通读到", flag)
	case "readonly":
		var wg sync.WaitGroup
		for g := 0; g < 4; g++ { wg.Add(1); go func() { defer wg.Done(); s := 0; for i := 0; i < 1000; i++ { s += counter }; _ = s }() }
		wg.Wait()
		fmt.Println("只读,无竞争")
	case "rare":
		// 只有设置了环境变量才会走到有竞争的分支
		var wg sync.WaitGroup
		for g := 0; g < 2; g++ {
			wg.Add(1)
			go func() { defer wg.Done(); if os.Getenv("TRIGGER") != "" { counter++ } }()
		}
		wg.Wait()
		fmt.Println("done")
	case "many":
		var wg sync.WaitGroup
		stop := make(chan struct{})
		n, _ := strconv.Atoi(os.Args[2])
		for g := 0; g < n; g++ { wg.Add(1); go func() { defer wg.Done(); <-stop }() }
		time.Sleep(200 * time.Millisecond)
		close(stop)
		wg.Wait()
		fmt.Printf("%d 个 goroutine 同时存活,正常结束\n", n)
	case "compute":
		t0 := time.Now(); s := compute(); fmt.Printf("%.3f %d\n", time.Since(t0).Seconds(), s)
	case "lock":
		t0 := time.Now(); n := lockHeavy(); fmt.Printf("%.3f %d\n", time.Since(t0).Seconds(), n)
	}
}
'''
d = gdir('rc1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'plain'); assert rc == 0, o
rc, o = go(d, 'build', '-race', '-o', 'racy'); assert rc == 0, o
def run(binname, *a, env=None, tmo=120, rss=False):
    e = dict(os.environ); e.update(env or {})
    cmd = [str(d / binname), *a]
    if rss: cmd = ['/usr/bin/time', '-l'] + cmd
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=tmo, env=e)
    return p.returncode, (p.stdout + p.stderr)
def clean(t):
    out = []
    for l in t.rstrip().split('\n'):
        l = l.replace(str(d), '<gtmp>/rc1')
        out.append(l.rstrip())
    return '\n'.join(out)
def head(t, n=24):
    return '\n'.join('  ' + l for l in clean(t).split('\n')[:n])
print('== 一:两个 goroutine 同时对一个 int 做 counter++(go build -race,Go 1.27.1,arm64 macOS)')
rcode, o = run('racy', 'counter')
print(head(o, 26)); print(f'  进程退出码:{rcode}')
rcode, o = run('plain', 'counter')
print(f'  同一份源码不加 -race 编译:{o.strip()}(退出码 {rcode},没有任何提示)')
print('== 二:检测的是“有没有 happens-before 关系”,不是“这次碰巧有没有同时发生”')
for m in ('sleepordered', 'atomicmixed'):
    rcode, o = run('racy', m)
    print(f'  [{m}] 退出码 {rcode}')
    print('\n'.join('    ' + l for l in clean(o).split('\n') if l.startswith(('WARNING', 'Write at', 'Read at', 'Previous', '读到', '普通读到'))))
rcode, o = run('racy', 'readonly'); print(f'  [readonly] 退出码 {rcode}:{o.strip()}')
print('== 三:没跑到的竞争不会被报告:同一个二进制,不设环境变量 vs 设了 TRIGGER=1')
rcode, o = run('racy', 'rare'); print(f'  [不触发] 退出码 {rcode}:{o.strip()}')
rcode, o = run('racy', 'rare', env={'TRIGGER': '1'}); print(f'  [TRIGGER=1] 退出码 {rcode}:' + ' | '.join(l for l in clean(o).split('\n') if l.startswith(('WARNING', 'done'))))
print('== 四:GORACE 选项:exitcode 与 halt_on_error')
rcode, o = run('racy', 'counter', env={'GORACE': 'exitcode=7'}); print(f'  GORACE=exitcode=7:退出码 {rcode}')
rcode, o = run('racy', 'counter', env={'GORACE': 'halt_on_error=1'}); print(f'  GORACE=halt_on_error=1:退出码 {rcode};出现 "WARNING: DATA RACE" {o.count("WARNING: DATA RACE")} 次;最后一行 "{clean(o).strip().split(chr(10))[-1]}"')
print('== 五:同时存活的 goroutine 上限')
for n in (10000, 100000):
    for b, lab in (('racy', '-race'), ('plain', '普通')):
        rcode, o = run(b, 'many', str(n)); print(f'  {lab}版本:{o.strip()[:120]}(退出码 {rcode})')
print('== 六:代价(各 5 次取最小/中位/最大;内存是 /usr/bin/time -l 报的 maximum resident set size)')
def rssmb(t):
    m = re.search(r'(\d+)\s+maximum resident set size', t); return int(m.group(1)) / 1e6 if m else 0
for mode, label in (('compute', '内存密集的循环(数组 1M×40 遍)'), ('lock', '8 个 goroutine 争锁各 20 万次')):
    res = {}
    for b in ('plain', 'racy'):
        ts = []; rs = []
        for i in range(5):
            rcode, o = run(b, mode, rss=True)
            ts.append(float(o.strip().split('\n')[0].split()[0])); rs.append(rssmb(o))
        res[b] = (min(ts), statistics.median(ts), max(ts), statistics.median(rs))
        print(f'  {label} {"-race" if b == "racy" else "普通 "}:耗时 {res[b][0]:.3f} / {res[b][1]:.3f} / {res[b][2]:.3f} s;内存中位 {res[b][3]:.0f} MB')
    print(f'    → 耗时中位数比 {res["racy"][1] / res["plain"][1]:.1f} 倍;内存中位数比 {res["racy"][3] / res["plain"][3]:.1f} 倍')
