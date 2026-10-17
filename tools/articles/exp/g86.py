import sys, os, re as _re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
import re as pyre
tee('g86')
SRC = r'''
package main

import (
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"
)

var sinkB bool

func main() {
	switch os.Args[1] {
	case "evil":
		n, _ := strconv.Atoi(os.Args[2])
		re := regexp.MustCompile(`^(a+)+$`)
		s := strings.Repeat("a", n) + "b"
		t0 := time.Now()
		m := re.MatchString(s)
		fmt.Printf("%d %v %.3f\n", n, m, time.Since(t0).Seconds()*1000)
	case "linear":
		re := regexp.MustCompile(`^(a+)+$`)
		for _, n := range []int{1000, 10000, 100000, 1000000} {
			s := strings.Repeat("a", n) + "b"
			t0 := time.Now()
			m := re.MatchString(s)
			fmt.Printf("  Go regexp `^(a+)+$` 匹配 %7d 个 a 加一个 b:匹配结果 %v,%.1f ms\n", n, m, time.Since(t0).Seconds()*1000)
		}
	case "unsupported":
		for _, p := range []string{`(a)\1`, `(?=a)b`, `(?!a)b`, `(?<=a)b`, `a++`, `(?i)abc`, `\d{1,1001}`} {
			_, err := regexp.Compile(p)
			if err != nil { fmt.Printf("  Compile(%q) 失败:%v\n", p, err) } else { fmt.Printf("  Compile(%q) 成功\n", p) }
		}
	case "leftmost":
		re := regexp.MustCompile(`a|ab`)
		fmt.Printf("  `a|ab` 在 \"ab\" 里(默认,Perl 风格最左优先):%q\n", re.FindString("ab"))
		re2 := regexp.MustCompile(`a|ab`)
		re2.Longest()
		fmt.Printf("  同一个模式调用 Longest()(POSIX 最左最长):%q\n", re2.FindString("ab"))
		re3 := regexp.MustCompilePOSIX(`a|ab`)
		fmt.Printf("  MustCompilePOSIX:%q\n", re3.FindString("ab"))
	case "cost":
		text := strings.Repeat("hello world, this is a test line with foo=12345 and bar=67890.\n", 1000)
		re := regexp.MustCompile(`foo=(\d+)`)
		r1 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sinkB = re.MatchString(text) } })
		r2 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sinkB = strings.Contains(text, "foo=") } })
		r3 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { regexp.MustCompile(`foo=(\d+)`) } })
		r4 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sinkB, _ = regexp.MatchString(`foo=(\d+)`, "foo=1") } })
		r5 := testing.Benchmark(func(b *testing.B) { for i := 0; i < b.N; i++ { sinkB = re.MatchString("foo=1") } })
		fmt.Printf("  在 %d 字节文本的开头附近命中:re.MatchString %d ns/次;strings.Contains %d ns/次\n", len(text), r1.NsPerOp(), r2.NsPerOp())
		fmt.Printf("  regexp.MustCompile 一次:%d ns/次(%d 次分配);每次都用 regexp.MatchString(内部再编译):%d ns/次;预编译的 re.MatchString(短串):%d ns/次\n", r3.NsPerOp(), r3.AllocsPerOp(), r4.NsPerOp(), r5.NsPerOp())
	}
}
'''
d = gdir('re1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(*a):
    p = subprocess.run([str(d / 'app'), *map(str, a)], capture_output=True, text=True, timeout=300)
    return tidy(p.stdout + p.stderr)
print('== 一:经典的灾难性模式 ^(a+)+$:输入是 n 个 a 加一个 b(不匹配)。左边是 Go,右边是 Python 的 re(回溯引擎)')
print('  Go regexp(RE2 风格):')
print(run('linear'))
print('  Python re(回溯引擎),同一个模式、同样的输入(每次最多等 20 秒):')
for n in (20, 24, 26, 28, 30):
    s = 'a' * n + 'b'
    t0 = time.time()
    import signal as _s
    class TO(Exception): pass
    def h(*a): raise TO()
    _s.signal(_s.SIGALRM, h); _s.alarm(20)
    try:
        m = pyre.match(r'^(a+)+$', s); r = f'{(time.time() - t0) * 1000:.0f} ms'
    except TO:
        r = '超过 20 秒,被我中断'
    finally:
        _s.alarm(0)
    print(f'  Python re `^(a+)+$` 匹配 {n} 个 a 加一个 b:{r}')
print('== 二:Go 不支持的语法')
print(run('unsupported'))
print('== 三:最左优先 vs 最左最长')
print(run('leftmost'))
print('== 四:成本')
print(run('cost'))
print('== 五:源码里的两条说明')
src = open(GOROOT + '/src/regexp/backtrack.go').read()
m = re.search(r'// backtrack is a regular expression search with submatch.*?small\n// regexps when onepass cannot be used\.', src, re.S) if False else None
lines = src.split('\n')
i = next(i for i, l in enumerate(lines) if l.startswith('// backtrack is a regular expression search'))
print('  backtrack.go:' + ' '.join(l.lstrip('/ ') for l in lines[i:i + 10]))
r, o = go(gdir('doc1'), 'doc', 'regexp')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if 'guarantees to run in time linear' in l or 'linear in the size of the input' in l)
print('  go doc regexp:' + ' '.join(x for x in ls[max(0, i - 2):i + 3] if x))
