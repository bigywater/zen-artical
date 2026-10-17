import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g95')
TEST = '''
package lab

import (
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func double(x int) int { return x * 2 }

func TestCapture(t *testing.T) {
	cases := []struct{ name string; in, want int }{
		{"one", 1, 2}, {"two", 2, 4}, {"three", 3, 6},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			time.Sleep(10 * time.Millisecond)
			if !strings.HasSuffix(t.Name(), "/"+tc.name) {
				t.Errorf("子测试 %s 里看到的 tc.name 却是 %q(它测的是别人的用例)", t.Name(), tc.name)
			}
			if got := double(tc.in); got != tc.want {
				t.Errorf("%s: double(%d) = %d,想要 %d", t.Name(), tc.in, got, tc.want)
			}
		})
	}
}

func TestNames(t *testing.T) {
	for _, n := range []string{"a b", "a b", "x/y", "", "UPPER", "tab\\there"} {
		t.Run(n, func(t *testing.T) { t.Log("子测试名:", t.Name()) })
	}
}

var cur, peak atomic.Int64

func TestConcurrency(t *testing.T) {
	for i := 0; i < 8; i++ {
		t.Run("p", func(t *testing.T) {
			t.Parallel()
			n := cur.Add(1)
			for { m := peak.Load(); if n <= m || peak.CompareAndSwap(m, n) { break } }
			time.Sleep(30 * time.Millisecond)
			cur.Add(-1)
		})
	}
	t.Cleanup(func() { t.Logf("同时在跑的并行子测试最多 %d 个", peak.Load()) })
}
'''
def project(name, gover):
    d = gdir(name); write(d, {'x_test.go': TEST}); mod(d, go=gover); return d
print('== 一:并行子测试里捕获循环变量(同一份测试代码,只改 go.mod 里的 go 版本;Go 1.27.1 工具链,arm64 macOS)')
for gv in ('1.21', '1.22'):
    d = project('tt' + gv.replace('.', ''), gv)
    rc, o = go(d, 'test', '-run', 'TestCapture', '-v', '-count=1')
    lines = [l.strip() for l in o.split('\n') if l.strip()]
    sel = [l for l in lines if l.startswith(('--- FAIL', '--- PASS', 'x_test.go')) or l in ('PASS', 'FAIL') or l.startswith(('ok', 'FAIL'))]
    sel = [re.sub(r'x_test.go:\d+: ', '', l) for l in sel]
    print(f'  [go.mod 写 go {gv}] 退出码 {rc}')
    for l in sel[:12]: print('    ' + l.replace('x_test.go', 'x_test.go'))
print('== 二:子测试名里的空格、重复、斜杠、空串')
d = project('tt122n', '1.22')
rc, o = go(d, 'test', '-run', 'TestNames', '-v', '-count=1')
for l in o.split('\n'):
    if '子测试名' in l or l.strip().startswith('--- PASS'): print('  ' + l.strip())
print('== 三:用 -run 选子测试(斜杠分隔,每一段是一个正则)')
rc, o = go(d, 'test', '-run', 'TestNames/a_b', '-v', '-count=1')
print('  go test -run "TestNames/a_b" 运行了:' + ', '.join(re.findall(r'--- PASS: (\S+)', o)))
rc, o = go(d, 'test', '-run', 'TestNames/^a_b#01$', '-v', '-count=1')
print('  go test -run "TestNames/^a_b#01$" 运行了:' + ', '.join(re.findall(r'--- PASS: (\S+)', o)))
print('== 四:-parallel 限制并行子测试的数量(8 个各睡 30 ms 的并行子测试)')
for par in (1, 2, 4, 8):
    rc, o = go(d, 'test', '-run', 'TestConcurrency', '-v', '-count=1', f'-parallel={par}')
    m = re.search(r'最多 (\d+) 个', o); mt = re.search(r'ok\s+\S+\s+([\d.]+)s', o)
    print(f'  -parallel={par}:同时在跑的并行子测试最多 {m.group(1) if m else "?"} 个,总用时 {mt.group(1) if mt else "?"} s')
print('== 五:文档与发行说明')
rn = open(GOROOT + '/doc/go_spec.html').read()
t = re.sub(r'<[^>]+>', '', rn); t = re.sub(r'\s+', ' ', t)
i = t.find('Each iteration has its own separate declared variable')
print('  go_spec.html:' + (t[i:i + 330] if i >= 0 else '(未找到)'))
r, o = go(d, 'doc', 'testing.T.Run')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:11] if l.strip()))
