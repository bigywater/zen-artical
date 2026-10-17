import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g37')
SRC = r'''
package main

import (
	"bytes"
	"compress/flate"
	"flag"
	"fmt"
	"io"
	"math"
	"os"
	"regexp"
	"runtime/pprof"
	"time"
)

type Shape interface{ Area() float64 }
type Circle struct{ r float64 }
type Square struct{ s float64 }
type Tri struct{ b, h float64 }

func (c Circle) Area() float64 { return math.Pi * c.r * c.r }
func (s Square) Area() float64 { return s.s * s.s }
func (t Tri) Area() float64    { return 0.5 * t.b * t.h }

// 热点函数:比较长,代价超过默认的内联预算 80
func score(x, y, z float64) float64 {
	a := x*x + y*y
	b := y*y + z*z
	c := z*z + x*x
	if a > b { a, b = b, a }
	if b > c { b, c = c, b }
	if a > b { a, b = b, a }
	d := math.Sqrt(a) + math.Sqrt(b)*0.5 + math.Sqrt(c)*0.25
	if d > 100 { d = 100 }
	e := d*d - a*b + c*0.01
	if e < 0 { e = -e }
	f := math.Sqrt(e + 1)
	return f*0.7 + d*0.3 + a*1e-9
}

func runBoth(shapes []Shape, n int) float64 {
	total := 0.0
	for i := 0; i < n; i++ {
		s := shapes[i%len(shapes)]
		a := s.Area()
		total += score(a, float64(i&255), 3)
	}
	return total
}

func runIface(shapes []Shape, n int) float64 {
	total := 0.0
	for i := 0; i < n; i++ { total += shapes[i%len(shapes)].Area() }
	return total
}

func runInline(n int) float64 {
	total := 0.0
	for i := 0; i < n; i++ { total += score(float64(i&1023), float64(i&255), 3) }
	return total
}

func runFlate(n int) float64 {
	data := bytes.Repeat([]byte("hello pgo world, 0123456789 "), 1<<17)
	total := 0
	for i := 0; i < n; i++ {
		w, _ := flate.NewWriter(io.Discard, 6)
		w.Write(data)
		w.Close()
		total += len(data)
	}
	return float64(total)
}

var emailRe = regexp.MustCompile(`^(\w+)@(\w+)\.(com|org|net)$`)

func runRegexp(n int) float64 {
	inputs := []string{"alice@example.com", "bob@site.org", "not an email", "carol@host.net", "dave@@bad.com", "erin@x.io"}
	hits := 0
	for i := 0; i < n; i++ {
		if emailRe.MatchString(inputs[i%len(inputs)]) { hits++ }
	}
	return float64(hits)
}

func main() {
	n := flag.Int("n", 50_000_000, "迭代次数")
	mode := flag.String("mode", "both", "both / iface / inline")
	prof := flag.String("cpuprofile", "", "写 CPU profile")
	flag.Parse()
	// 95% 的元素是 Circle,另外 Square、Tri 各 2.5%
	shapes := make([]Shape, 1000)
	for i := range shapes {
		switch {
		case i%40 == 7: shapes[i] = Square{float64(i%10 + 1)}
		case i%40 == 21: shapes[i] = Tri{float64(i%7 + 1), 2}
		default: shapes[i] = Circle{float64(i%5 + 1)}
		}
	}
	if *prof != "" {
		f, _ := os.Create(*prof)
		pprof.StartCPUProfile(f)
		defer pprof.StopCPUProfile()
	}
	t0 := time.Now()
	var total float64
	switch *mode {
	case "iface": total = runIface(shapes, *n)
	case "inline": total = runInline(*n)
	case "flate": total = runFlate(*n)
	case "regexp": total = runRegexp(*n)
	default: total = runBoth(shapes, *n)
	}
	fmt.Printf("total=%.3f elapsed_ms=%d\n", total, time.Since(t0).Milliseconds())
}
'''
d = gdir('pg1'); write(d, {'main.go': SRC}); mod(d)
MODES = [('iface', '只有接口调用 s.Area()(95% 是 Circle)', 400_000_000), ('inline', '只有直接调用较长的 score()', 100_000_000), ('both', '接口调用 + 较长的 score()', 100_000_000), ('flate', 'compress/flate 压缩 3.6 MB 重复文本', 20), ('regexp', 'regexp 匹配邮箱格式', 3_000_000)]
print('== 一:没有 profile 时编译器怎么看这个程序(默认构建 -gcflags=-m=2 的诊断)')
rc, o = go(d, 'build', '-gcflags=-m=2', '-o', 'base')
for l in o.split('\n'):
    if re.search(r'cannot inline score|can inline run|inlining call to score|devirtualiz', l): print('  ' + l.replace('./main.go', 'main.go')[:200])
rc, o = go(d, 'build', '-pgo=off', '-o', 'base'); assert rc == 0, o
def timeit(binp, mode, n, k=7):
    ts = []
    for _ in range(k):
        p = subprocess.run([binp, '-mode', mode, '-n', str(n)], capture_output=True, text=True)
        ts.append(int(re.search(r'elapsed_ms=(\d+)', p.stdout).group(1)))
    return sorted(ts)

print('== 二:收集 CPU profile:把五种 mode 各跑一遍,用 go tool pprof -proto 合并成 default.pgo')
profs = []
for mode, _, n in MODES:
    pf = str(d / f'{mode}.pprof')
    p = subprocess.run([str(d / 'base'), '-mode', mode, '-n', str(n), '-cpuprofile', pf], capture_output=True, text=True)
    profs.append(pf); print(f'  mode={mode}:{p.stdout.strip()};profile {os.path.getsize(pf)} 字节')
(d / 'default.pgo').write_bytes(subprocess.run([GO, 'tool', 'pprof', '-proto', *profs], cwd=d, env=genv(), capture_output=True).stdout)
print(f'  合并后的 default.pgo {os.path.getsize(d / "default.pgo")} 字节')
rc, o = go(d, 'tool', 'pprof', '-top', '-nodecount=6', 'base', 'default.pgo')
print('  go tool pprof -top(前几行):')
for l in o.split('\n')[4:12]: print('    ' + re.sub(r'\s+', ' ', l.strip())[:110])

print('== 三:用 profile 重新编译:-pgo=default.pgo 之后编译器的决定')
rc, o = go(d, 'build', '-pgo=default.pgo', '-gcflags=-m=2', '-o', 'pgo')
for l in o.split('\n'):
    if re.search(r'hot callsite|devirtualiz|inlining call to score|inlining call to (main\.)?(Circle|Square|Tri)|can inline score|cannot inline score', l): print('  ' + l.replace('./main.go', 'main.go')[:190])
rc, o = go(d, 'build', '-pgo=default.pgo', '-o', 'pgo'); assert rc == 0, o

print('== 四:运行时间对比(每种 mode 各跑 7 次,毫秒,排序后)')
for mode, label, n in MODES:
    tb = timeit(str(d / 'base'), mode, n); tp = timeit(str(d / 'pgo'), mode, n)
    mb, mp = tb[3], tp[3]
    print(f'  {label}(n = {n}):')
    print(f'    基线:{tb};中位 {mb}')
    print(f'    PGO :{tp};中位 {mp}')
    print(f'    PGO 比基线{"快" if mp < mb else "慢"} {abs(1 - mp / mb) * 100:.1f}%(中位数)')
print(f'  二进制大小:基线 {os.path.getsize(d / "base")} 字节,PGO {os.path.getsize(d / "pgo")} 字节')

print('== 五:-pgo=auto(默认):main 包目录里的 default.pgo 会被自动使用')
rc, o = go(d, 'build', '-o', 'auto')
rc, o = go(d, 'version', '-m', 'auto')
print('  默认 go build 的产物里的构建信息:' + ' / '.join(l.strip().replace(str(GT), '<gtmp>') for l in o.split('\n') if 'pgo' in l.lower()))
rc, o = go(d, 'build', '-pgo=off', '-o', 'off'); rc, o = go(d, 'version', '-m', 'off')
print('  -pgo=off 的产物:' + (' / '.join(l.strip() for l in o.split('\n') if 'pgo' in l.lower()) or '构建信息里没有 -pgo'))
