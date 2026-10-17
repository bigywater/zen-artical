import sys, os, re, time, statistics, subprocess, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g98')
FILES = {
'f.go': '''
package lab

func Classify(n int) string {
	if n < 0 {
		return "负数"
	}
	if n == 0 {
		return "零"
	}
	for i := 2; i*i <= n; i++ {
		if n%i == 0 {
			return "合数"
		}
	}
	return "质数或 1"
}

func Unused() int {
	x := 1
	x++
	return x
}

func Hot(n int) int {
	s := 0
	for i := 0; i < n; i++ {
		if i%3 == 0 {
			s += i
		} else {
			s -= 1
		}
	}
	return s
}
''',
'f_test.go': '''
package lab

import "testing"

func TestClassify(t *testing.T) {
	for _, n := range []int{-1, 0, 7, 7, 7, 9} {
		Classify(n)
	}
}

func BenchmarkHot(b *testing.B) {
	for i := 0; i < b.N; i++ {
		Hot(1000)
	}
}
''',
}
d = gdir('cv2'); write(d, FILES); mod(d)
def run(*args, tmo=300):
    rc, o = go(d, *args, timeout=tmo)
    return rc, o
print('== 一:go test -cover 的百分比(Go 1.27.1,arm64 macOS)')
rc, o = run('test', '-count=1', '-cover', '.')
print('  ' + o.strip().replace('\n', '\n  '))
print('== 二:三种 -covermode 生成的覆盖率文件(-coverprofile)')
prof = {}
for mode in ('set', 'count', 'atomic'):
    rc, o = run('test', '-count=1', f'-covermode={mode}', f'-coverprofile=c_{mode}.out', '.')
    prof[mode] = (d / f'c_{mode}.out').read_text().strip().split('\n')
for mode in ('set', 'count'):
    lines = prof[mode]
    print(f'  -covermode={mode}:{lines[0]}(每行:文件:起始行.列,结束行.列 语句数 计数)')
    for l in lines[1:]:
        if 'f.go:' in l: print('    ' + l.replace('lab/', ''))
same = prof['atomic'][1:] == prof['count'][1:]
print(f'  -covermode=atomic:{prof["atomic"][0]};各行的计数与 count 模式{"完全相同" if same else "不同"}(单线程测试里没有区别)')
print('== 三:go tool cover -func(用 count 模式的文件)')
r = subprocess.run([GO, 'tool', 'cover', '-func', str(d / 'c_count.out')], capture_output=True, text=True, env=genv(), cwd=d)
for l in (r.stdout + r.stderr).strip().split('\n'): print('  ' + re.sub(r'\s+', ' ', l.replace('lab/', '')))
print('== 四:插桩的开销:Hot(1000) 的基准(-benchtime=300ms,每种取 3 次最小)')
def bench(extra):
    best = 1e18
    for _ in range(3):
        rc, o = run('test', '-run', '^$', '-bench', 'Hot', '-benchtime', '300ms', '-count=1', *extra, '.')
        m = re.search(r'BenchmarkHot\S*\s+\d+\s+([\d.]+) ns/op', o)
        if m: best = min(best, float(m.group(1)))
    return best
b0 = bench([]); bs = bench(['-cover', '-covermode=set']); bc = bench(['-cover', '-covermode=count']); ba = bench(['-cover', '-covermode=atomic'])
print(f'  不插桩 {b0:.0f} ns/op;-covermode=set {bs:.0f} ns/op({bs/b0:.2f} 倍);count {bc:.0f} ns/op({bc/b0:.2f} 倍);atomic {ba:.0f} ns/op({ba/b0:.2f} 倍)')
print('== 五:不是测试的程序也能收集覆盖率(go build -cover + GOCOVERDIR)')
(d / 'cmd').mkdir(exist_ok=True)
(d / 'cmd' / 'main.go').write_text('package main\n\nimport (\n\t"fmt"\n\t"lab"\n)\n\nfunc main() { fmt.Println(lab.Classify(11), lab.Classify(-3)) }\n')
rc, o = run('build', '-cover', '-o', 'app', './cmd')
cdir = d / 'covdata'; cdir.mkdir(exist_ok=True)
p = subprocess.run([str(d / 'app')], capture_output=True, text=True, env=dict(os.environ, GOCOVERDIR=str(cdir)))
print('  程序输出:' + p.stdout.strip() + f';GOCOVERDIR 里生成了 {len(list(cdir.iterdir()))} 个文件')
r = subprocess.run([GO, 'tool', 'covdata', 'percent', f'-i={cdir}'], capture_output=True, text=True, env=genv(), cwd=d)
print('  go tool covdata percent:' + (r.stdout + r.stderr).strip().replace(str(d), '<模块>'))
print('== 六:go help testflag 里 -covermode 的说明')
r = subprocess.run([GO, 'help', 'testflag'], capture_output=True, text=True, env=genv())
ls = r.stdout.split('\n')
i = next(i for i, l in enumerate(ls) if l.strip().startswith('-covermode'))
print('  ' + ' '.join(x.strip() for x in ls[i:i + 9]))
