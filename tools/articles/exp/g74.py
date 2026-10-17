import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g74')
SRC = r'''
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"
)

var sink time.Time
var sinkD time.Duration

func has(t time.Time) string { if strings.Contains(t.String(), "m=") { return "有 m=" }; return "无 m=" }

func main() {
	switch os.Args[1] {
	case "string":
		t := time.Now()
		fmt.Printf("  time.Now().String() 的尾部:%s\n", t.String()[strings.LastIndex(t.String(), " m=")-0:])
		fmt.Printf("  同一个值 Round(0) 之后的完整输出:%s\n", t.Round(0).String())
		fmt.Printf("  Round(0) 之前的完整输出:%s\n", t.String())
	case "strip":
		t := time.Now()
		fmt.Printf("  time.Now():%s\n", has(t))
		fmt.Printf("  t.Add(time.Hour):%s\n", has(t.Add(time.Hour)))
		fmt.Printf("  t.AddDate(0,0,1):%s\n", has(t.AddDate(0, 0, 1)))
		fmt.Printf("  t.Round(time.Second):%s\n", has(t.Round(time.Second)))
		fmt.Printf("  t.Truncate(time.Second):%s\n", has(t.Truncate(time.Second)))
		fmt.Printf("  t.Round(0):%s\n", has(t.Round(0)))
		fmt.Printf("  t.UTC():%s\n", has(t.UTC()))
		fmt.Printf("  t.Local():%s\n", has(t.Local()))
		fmt.Printf("  t.In(time.UTC):%s\n", has(t.In(time.UTC)))
		fmt.Printf("  time.Unix(t.Unix(), 0):%s\n", has(time.Unix(t.Unix(), 0)))
		fmt.Printf("  time.Date(…):%s\n", has(time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)))
	case "equal":
		t := time.Now()
		w := t.Round(0)
		fmt.Printf("  t == t.Round(0):%v;t.Equal(t.Round(0)):%v\n", t == w, t.Equal(w))
		b, _ := json.Marshal(t)
		var u time.Time
		json.Unmarshal(b, &u)
		fmt.Printf("  经过 JSON 序列化再反序列化:t == u:%v;t.Equal(u):%v;t.Sub(u) = %v(JSON 只保留到纳秒的墙钟时间,单调读数丢了)\n", t == u, t.Equal(u), t.Sub(u))
		m := map[time.Time]string{t: "x"}
		_, ok1 := m[t]
		_, ok2 := m[t.Round(0)]
		fmt.Printf("  用 time.Time 当 map 的 key:用 t 查 %v;用 t.Round(0) 查 %v(同一个时刻!)\n", ok1, ok2)
		d := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
		l := d.In(time.FixedZone("CST", 8*3600))
		fmt.Printf("  同一时刻、不同时区:d == l:%v;d.Equal(l):%v\n", d == l, d.Equal(l))
	case "cost":
		t0 := time.Now()
		r1 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sink = time.Now() } })
		r2 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sinkD = time.Since(t0) } })
		r3 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sink = t0.Round(0) } })
		fmt.Printf("  time.Now() %d ns/次;time.Since(t) %d ns/次;t.Round(0) %d ns/次\n", r1.NsPerOp(), r2.NsPerOp(), r3.NsPerOp())
	}
}
'''
d = gdir('tm2'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:time.Now() 带着一个单调时钟读数(Go 1.27.1,arm64 macOS)')
print(run('string'))
print('== 二:哪些操作会去掉(strip)单调读数')
print(run('strip'))
print('== 三:== 、Equal、map key 与序列化')
print(run('equal'))
print('== 四:成本')
print(run('cost'))
print('== 五:文档原文(go doc time,Monotonic Clocks 一节节选)')
r, o = go(gdir('doc1'), 'doc', 'time')
ls = [l.rstrip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('# Monotonic Clocks'))
txt = ' '.join(x.strip() for x in ls[i + 1:i + 70])
for k in ('The general rule is that the wall clock is for telling time and the monotonic clock is for measuring time.',
          'The canonical way to strip a monotonic clock reading is to use t = t.Round(0).',
          'If Times t and u both contain monotonic clock readings, the operations t.After(u), t.Before(u), t.Equal(u), t.Compare(u), and t.Sub(u) are carried out using the monotonic clock readings alone, ignoring the wall clock readings. If either t or u contains no monotonic clock reading, these operations fall back to using the wall clock readings.',
          'On some systems the monotonic clock will stop if the computer goes to sleep.'):
    print('  ' + (k if k in txt else '(未找到)' + k))
j = next((x for x in range(i, len(ls)) if 'Go == operator compares' in ls[x]), None)
print('  ' + ' '.join(x.strip() for x in ls[j:j + 10]).split('# Timer')[0].strip() if j else '  (== 一段未找到)')
