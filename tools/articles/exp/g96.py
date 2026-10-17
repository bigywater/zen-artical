import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g96')
FILES = {
'c.go': '''
package lab

import (
	"context"
	"time"
)

// Cache 条目 TTL 过期
type Cache struct {
	m   map[string]time.Time
	ttl time.Duration
}

func NewCache(ttl time.Duration) *Cache { return &Cache{m: map[string]time.Time{}, ttl: ttl} }
func (c *Cache) Set(k string)           { c.m[k] = time.Now().Add(c.ttl) }
func (c *Cache) Has(k string) bool      { t, ok := c.m[k]; return ok && time.Now().Before(t) }

// Poll 每隔 d 调用一次 f,直到 ctx 结束,返回调用次数
func Poll(ctx context.Context, d time.Duration, f func()) int {
	n := 0
	t := time.NewTicker(d)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return n
		case <-t.C:
			f(); n++
		}
	}
}
''',
'c_test.go': '''
package lab

import (
	"context"
	"sync"
	"testing"
	"testing/synctest"
	"time"
)

func TestRealTTL(t *testing.T) {
	c := NewCache(300 * time.Millisecond)
	c.Set("k")
	if !c.Has("k") { t.Fatal("刚设置就过期了") }
	time.Sleep(350 * time.Millisecond)
	if c.Has("k") { t.Fatal("过期后还在") }
}

func TestFakeTTL(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		start := time.Now()
		c := NewCache(1 * time.Hour)
		c.Set("k")
		time.Sleep(59*time.Minute + 59*time.Second)
		if !c.Has("k") { t.Fatal("还没到 1 小时就过期了") }
		time.Sleep(2 * time.Second)
		if c.Has("k") { t.Fatal("1 小时后还在") }
		t.Logf("起点 %s;测试里过去了 %v(假时钟)", start.Format("2006-01-02 15:04:05 MST"), time.Since(start))
	})
}

func TestFakePoll(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second+time.Millisecond)
		defer cancel()
		calls := Poll(ctx, time.Second, func() {})
		t.Logf("每秒轮询一次、超时 10.001 秒:调用了 %d 次", calls)
		if calls != 10 { t.Fatalf("calls=%d", calls) }
	})
}

func TestFakeWait(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		var mu sync.Mutex
		done := false
		go func() { mu.Lock(); done = true; mu.Unlock() }()
		synctest.Wait()
		mu.Lock()
		t.Logf("synctest.Wait() 返回之后,后台 goroutine 已经执行完:done=%v", done)
		mu.Unlock()
	})
}

func TestDeadlock(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ch := make(chan int)
		<-ch // 没有任何东西会唤醒它,也没有定时器
	})
}

func TestLeakExit(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		go func() { select {} }() // 泄漏的 goroutine
	})
}
''',
}
d = gdir('sy1'); write(d, FILES); mod(d)
def t(args, tmo=120):
    t0 = time.time()
    extra = [] if any(a.startswith('-count') for a in args) else ['-count=1']
    rc, o = go(d, 'test', *args, *extra, timeout=tmo)
    return rc, o, time.time() - t0
print('== 一:测一个 TTL 一小时的缓存(Go 1.27.1,arm64 macOS)')
for name in ('TestRealTTL', 'TestFakeTTL'):
    rc, o, el = t(['-run', '^' + name + '$', '-v'])
    m = re.search(r'--- (PASS|FAIL): ' + name + r' \(([\d.]+)s\)', o)
    log = [l.strip() for l in o.split('\n') if '假时钟' in l]
    print(f'  {name}:{"通过" if m and m.group(1) == "PASS" else "失败"},测试自己报告耗时 {m.group(2) if m else "?"} 秒' + (f';{log[0]}' if log else ''))
print('  (TestRealTTL 用真实时钟,TTL 只能设 300 ms;TestFakeTTL 的 TTL 是 1 小时,在 synctest 的假时钟里瞬间完成)')
print('== 二:轮询次数是确定的')
rc, o, el = t(['-run', '^TestFakePoll$', '-v'])
print('  ' + ' | '.join(l.strip() for l in o.split('\n') if '轮询' in l or l.strip().startswith('--- ')))
rc, o, el = t(['-run', '^TestFakePoll$', '-v', '-count=50'])
print(f'  同一个测试连续重复 50 次(-count=50):通过 {o.count("--- PASS: TestFakePoll")} 次,失败 {o.count("--- FAIL")} 次')
print('== 三:synctest.Wait() 等所有其它 goroutine 都“持久阻塞”或结束')
rc, o, el = t(['-run', '^TestFakeWait$', '-v'])
print('  ' + ' | '.join(l.strip() for l in o.split('\n') if 'Wait' in l or l.strip().startswith('--- ')))
print('== 四:死锁检测:bubble 里所有 goroutine 都阻塞、又没有定时器可推进')
rc, o, el = t(['-run', '^TestDeadlock$'])
print(f'  退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if 'deadlock' in l.lower() or 'panic' in l.lower())[:300])
print('== 五:根 goroutine 退出时还有 goroutine 没结束')
rc, o, el = t(['-run', '^TestLeakExit$', '-v'])
print(f'  退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if l.strip() and not l.startswith('=== '))[:400])
print('== 六:文档里“持久阻塞”的完整清单')
r, o = go(d, 'doc', 'testing/synctest')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('The following operations durably block'))
j = next(j for j in range(i, len(ls)) if ls[j].startswith('Operations not in the above list'))
print('  ' + ' '.join(x for x in ls[i:j + 4] if x))
