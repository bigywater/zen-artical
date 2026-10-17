import sys, os, re, time, statistics, subprocess, shutil, pathlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g97')
OUTSIDE = GT / 'tc_outside.txt'
FILES = {
'c.go': '''
package lab

//go:noinline
func Add(a, b int) int { return a + b }
''',
'c_test.go': '''
package lab

import (
	"os"
	"testing"
	"time"
)

func TestAdd(t *testing.T) {
	x := len(os.Args)
	if Add(x, 2) != x+2 { t.Fatal("bad") }
}

func TestSlow(t *testing.T) { time.Sleep(1500 * time.Millisecond) }

func TestEnv(t *testing.T) { t.Logf("FOO=%q", os.Getenv("FOO")) }

func TestFile(t *testing.T) {
	b, err := os.ReadFile("data.txt")
	if err != nil { t.Fatal(err) }
	t.Logf("data.txt=%q", string(b))
}

func TestOutside(t *testing.T) {
	b, err := os.ReadFile(os.Getenv("OUTSIDE_FILE"))
	if err != nil { t.Fatal(err) }
	t.Logf("outside=%q", string(b))
}

func TestClock(t *testing.T) { t.Logf("秒数的个位=%d", time.Now().Unix()%10) }
''',
'data.txt': 'v1',
}
d = gdir('tc1'); write(d, FILES); mod(d)
go(d, 'clean', '-testcache')  # 先清空,避免之前运行留下的缓存
OUTSIDE.write_text('o1')
def t(pat, *extra, env=None, label=None, pkg='.'):
    t0 = time.time()
    rc, o = go(d, 'test', '-run', pat, *extra, *([pkg] if pkg else []), env=dict(OUTSIDE_FILE=str(OUTSIDE), **(env or {})), timeout=120)
    el = time.time() - t0
    m = re.search(r'(ok|FAIL)\s+\S+\s+(\(cached\)|[\d.]+s)', o)
    st = m.group(2) if m else '?'
    logs = [re.sub(r'^\s*c_test.go:\d+: ', '', l.strip()) for l in o.split('\n') if 'c_test.go' in l]
    print(f'  {label or pat:44s} → {st:10s} (go test 整体耗时 {el:.2f} s){("  " + " ".join(logs)) if logs else ""}')
print('== 零:没有包参数的 go test(本地目录模式)根本不缓存')
t('TestSlow', '-v', pkg=None, label='go test -run TestSlow -v(无包参数)第 1 次')
t('TestSlow', '-v', pkg=None, label='同上,第 2 次')
print('== 一:同样的命令带上包参数 .(包列表模式),连续跑(TestSlow 睡 1.5 秒;Go 1.27.1,arm64 macOS)')
t('TestSlow', '-v', label='第 1 次 go test -run TestSlow -v .')
t('TestSlow', '-v', label='第 2 次,什么都没改')
t('TestSlow', '-v', '-count=1', label='第 3 次,加 -count=1')
print('== 二:哪些改动会让缓存失效')
t('TestAdd', label='基线:TestAdd')
t('TestAdd', label='再跑一次')
(d / 'c.go').write_text('package lab\n\n// 只加了一行注释\n//go:noinline\nfunc Add(a, b int) int { return a + b }\n')
t('TestAdd', label='只改了注释之后')
(d / 'c.go').write_text('package lab\n\n//go:noinline\nfunc Add(a, b int) int { return b + a }\n')
t('TestAdd', label='把 a + b 改写成 b + a 之后(语义相同)')
(d / 'c.go').write_text('package lab\n\n//go:noinline\nfunc Add(a, b int) int {\n\tif a == 0 {\n\t\treturn b\n\t}\n\treturn a + b\n}\n')
t('TestAdd', label='加了一个 if a == 0 分支(真的改了代码)')
t('TestAdd', label='再跑一次')
t('TestAdd', '-race', label='加 -race(不同的测试二进制)')
t('TestAdd', '-race', label='再跑一次 -race')
for fl in ('-short', '-v', '-timeout=5m', '-count=2'):
    t('TestAdd', fl, label=f'加 {fl}:第 1 次')
    t('TestAdd', fl, label=f'加 {fl}:第 2 次')
print('== 三:测试读环境变量')
t('TestEnv', '-v', env={'FOO': 'a'}, label='FOO=a')
t('TestEnv', '-v', env={'FOO': 'a'}, label='FOO=a 再跑')
t('TestEnv', '-v', env={'FOO': 'b'}, label='FOO=b')
t('TestEnv', '-v', env={'FOO': 'a', 'OTHER': 'x'}, label='FOO=a,另外加一个测试没读的 OTHER=x')
print('== 四:测试读文件')
t('TestFile', '-v', label='读模块内的 data.txt(内容 v1)')
t('TestFile', '-v', label='再跑一次')
(d / 'data.txt').write_text('v2')
t('TestFile', '-v', label='把 data.txt 改成 v2')
t('TestOutside', '-v', label='读模块外的文件(内容 o1)')
t('TestOutside', '-v', label='再跑一次')
OUTSIDE.write_text('o2')
t('TestOutside', '-v', label='把模块外的文件改成 o2')
print('== 五:测试依赖时间,缓存会让结果“冻住”')
t('TestClock', '-v', label='第 1 次')
time.sleep(1.2)
t('TestClock', '-v', label='1.2 秒之后再跑一次')
print('== 六:go clean -testcache')
rc, o = go(d, 'clean', '-testcache')
t('TestClock', '-v', label='go clean -testcache 之后:第 1 次')
t('TestClock', '-v', label='第 2 次')
OUTSIDE.unlink(missing_ok=True)
print('== 七:文档(go help test)')
r = subprocess.run([GO, 'help', 'test'], capture_output=True, text=True, env=genv())
ls = r.stdout.split('\n')
i = next(i for i, l in enumerate(ls) if l.startswith('The rule for a match in the cache'))
print('  ' + ' '.join(x.strip() for x in ls[i:i + 14]))
