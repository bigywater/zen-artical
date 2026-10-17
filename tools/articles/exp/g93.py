import sys, os, re, time, statistics, subprocess, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g93')
FILES = {
'p.go': '''
package lab

// 一个藏着 bug 的函数:只有输入以 "Go!?" 开头才会 panic
func Parse(s string) int {
	if len(s) > 3 && s[0] == 'G' {
		if s[1] == 'o' {
			if s[2] == '!' {
				if s[3] == '?' {
					panic("找到了 bug")
				}
			}
		}
	}
	return len(s)
}

// 同样的分支结构,但不会 panic:用来观察 fuzz 的统计输出
func ParseSafe(s string) int {
	if len(s) > 3 && s[0] == 'G' {
		if s[1] == 'o' {
			if s[2] == '!' {
				if s[3] == '?' {
					return -1
				}
			}
		}
	}
	return len(s)
}
''',
'p_test.go': '''
package lab

import "testing"

func FuzzSafe(f *testing.F) {
	f.Add("hello")
	f.Fuzz(func(t *testing.T, s string) {
		ParseSafe(s)
	})
}

func FuzzParse(f *testing.F) {
	f.Add("hello")
	f.Add("Gx")
	f.Fuzz(func(t *testing.T, s string) {
		Parse(s)
	})
}
''',
}
d = gdir('fz1'); write(d, FILES); mod(d)
def run_fuzz(args, tmo=180):
    t0 = time.time()
    rc, o = go(d, 'test', *args, timeout=tmo)
    return rc, o, time.time() - t0
print('== 一:藏着 bug 的函数:只有输入以 "Go!?" 开头才会 panic(随机猜中 4 个固定字节的概率是 2 的 −32 次方)')
print('  go test(不开 fuzz),只跑种子语料 hello 和 Gx:')
rc, o, t = run_fuzz(['-run', 'FuzzParse', '-v'])
print('    ' + '\n    '.join(l for l in o.split('\n') if l.strip())[:600])
shutil.rmtree(GT / '_gocache' / 'fuzz', ignore_errors=True)  # 冷启动:清掉之前的 fuzz 语料缓存
print('== 二:go test -fuzz=FuzzParse -fuzztime=60s(Go 1.27.1,arm64 macOS;先清空 GOCACHE/fuzz,冷启动)')
rc, o, t = run_fuzz(['-fuzz=FuzzParse', '-fuzztime=60s', '-parallel=4'])
lines = [l for l in o.split('\n') if l.strip()]
keep = [l for l in lines if l.startswith(('fuzz:', '--- FAIL: FuzzParse (', 'FAIL')) or 'panic: 找到了 bug' in l or 'Failing input written' in l or 'To re-run' in l or l.strip().startswith('go test -run')]
print(f'  退出码 {rc},总用时 {t:.1f} 秒;输出(节选,省略了 panic 的调用栈):')
print('\n'.join('    ' + l.strip() if not l.startswith('fuzz:') else '    ' + l for l in keep))
print('  同一个函数的“不会 panic”版本 FuzzSafe,fuzz 10 秒,看统计:')
rc2, o2, t2 = run_fuzz(['-run', '^$', '-fuzz=FuzzSafe', '-fuzztime=10s', '-parallel=4'])
print('\n'.join('    ' + l for l in o2.split('\n') if l.startswith('fuzz:') or l.startswith('PASS') or l.startswith('ok')))
print('  重复 5 次冷启动(每次清空语料缓存和 testdata),看多久找到 bug、最初的失败输入多长、最终缩小到多长:')
for k in range(5):
    shutil.rmtree(GT / '_gocache' / 'fuzz', ignore_errors=True); shutil.rmtree(d / 'testdata', ignore_errors=True)
    rc3, o3, t3 = run_fuzz(['-run', '^$', '-fuzz=FuzzParse', '-fuzztime=60s', '-parallel=4'])
    m = re.search(r'minimizing (\d+)-byte failing input', o3)
    f = next(iter((d / 'testdata' / 'fuzz' / 'FuzzParse').iterdir()), None)
    final = f.read_text().strip().split('\n')[-1] if f else '(无)'
    print(f'    第 {k + 1} 次:{t3:.2f} 秒内找到;最初的失败输入 {m.group(1) if m else "?"} 字节;最终保存的输入 {final}')
print('== 三:失败的输入被存到了 testdata/fuzz 目录')
fz = d / 'testdata' / 'fuzz' / 'FuzzParse'
if fz.exists():
    for f in sorted(fz.iterdir()):
        print(f'  文件 testdata/fuzz/FuzzParse/{f.name[:8]}…(文件名是内容哈希):')
        print('    ' + f.read_text().replace('\n', '\n    ').rstrip())
else:
    print('  (没有生成失败文件)')
print('== 四:之后普通的 go test 会自动重放这个失败输入(回归测试)')
rc, o, t = run_fuzz(['-run', 'FuzzParse'])
print(f'  退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if l.strip().startswith(('--- FAIL', 'panic:', 'FAIL')))[:300])
print('== 五:语料缓存在 GOCACHE/fuzz 里')
cache = GT / '_gocache' / 'fuzz'
n = 0; size = 0
for root, _, fs in os.walk(cache):
    for f in fs: n += 1; size += os.path.getsize(os.path.join(root, f))
print(f'  GOCACHE/fuzz 里有 {n} 个语料文件,共 {size} 字节(这是 fuzz 过程中发现的“有新覆盖”的输入)')
print('== 六:go help testflag 中关于 -fuzz 的说明')
r = subprocess.run([GO, 'help', 'testflag'], capture_output=True, text=True, env=genv())
ls = r.stdout.split('\n')
i = next(i for i, l in enumerate(ls) if l.strip().startswith('-fuzz regexp'))
print('  ' + ' '.join(x.strip() for x in ls[i:i + 5]))
j = next(i for i, l in enumerate(ls) if l.strip().startswith('-fuzzminimizetime'))
print('  ' + ' '.join(x.strip() for x in ls[j:j + 6]))
