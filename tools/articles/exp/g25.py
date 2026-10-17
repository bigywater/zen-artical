import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g25')
FILES = {
    'tr/tr.go': '''
package tr

import "fmt"

func Log(s string) string { fmt.Println("   ", s); return s }
''',
    'b/b.go': '''
package b

import "lab/tr"

var B = tr.Log("b: 变量 B 初始化")

func init() { tr.Log("b: init()") }
''',
    'a/a1.go': '''
package a

import (
	"lab/b"
	"lab/tr"
)

var A = tr.Log("a1.go: 变量 A 初始化,用到 b.B = " + b.B)

func init() { tr.Log("a1.go: init() #1") }
func init() { tr.Log("a1.go: init() #2(同一个文件里的第二个 init)") }
''',
    'a/a0.go': '''
package a

import "lab/tr"

var A0 = tr.Log("a0.go: 变量 A0 初始化")

func init() { tr.Log("a0.go: init()") }
''',
    'c/c.go': '''
package c

import "lab/tr"

var C = tr.Log("c: 变量 C 初始化(c 不依赖 a、b)")

func init() { tr.Log("c: init()") }
''',
    'main.go': '''
package main

import (
	"lab/a"
	"lab/c"
	"lab/tr"
)

var M1 = tr.Log("main.go: 变量 M1 初始化")

func init() { tr.Log("main.go: init()") }

func main() {
	tr.Log("main(): 开始,a.A = " + a.A + ",c.C = " + c.C)
}
''',
    'zz.go': '''
package main

import "lab/tr"

var Z = tr.Log("zz.go: 变量 Z 初始化(文件名排在 main.go 后面)")

func init() { tr.Log("zz.go: init()") }
''',
}
d = gdir('in1'); write(d, FILES); mod(d)
print('== 一:跨包与跨文件的初始化顺序(模块 lab:main 导入 a 与 c,a 导入 b;a 有两个文件 a1.go 与 a0.go)')
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
out = subprocess.run([str(d / 'app')], capture_output=True, text=True).stdout.rstrip()
print(out)
print('  go list -deps 给出的依赖顺序(叶子在前):' + ' '.join(subprocess.run([GO, 'list', '-deps', '.'], cwd=d, env=genv(), capture_output=True, text=True).stdout.split()[-6:]))
rc, o = go(d, 'list', '-f', '{{.GoFiles}}', './a')
print(f'  go list 报告 a 包的文件顺序:{o}')

print('== 二:同一个包里变量的初始化顺序:按依赖,不是按书写顺序')
DEP = '''
package main

import "fmt"

var a = trace("a", c+1)
var b = trace("b", f())
var c = trace("c", g())
var d = trace("d", 100)

func f() int { fmt.Println("    f() 被调用,读取 d =", d); return d + 1 }
func g() int { return 10 }

func trace(n string, v int) int { fmt.Printf("    初始化 %s = %d\\n", n, v); return v }

func init() { fmt.Println("    init():a, b, c, d =", a, b, c, d) }

func main() {}
'''
r = grun('in2', {'main.go': DEP}); print('  变量声明顺序是 a、b、c、d;a 依赖 c;b 依赖 f(),f 读取 d:'); print(r['out'] if r['crc'] == 0 else r['cout'])

print('== 三:go run 时命令行里文件的顺序会影响同包多个文件的 init 顺序;go build 则按文件名排序')
d3 = gdir('in3'); mod(d3, name='lab3')
write(d3, {'a.go': 'package main\n\nimport "fmt"\n\nfunc init() { fmt.Println("    a.go 的 init") }\n',
           'b.go': 'package main\n\nimport "fmt"\n\nfunc init() { fmt.Println("    b.go 的 init") }\n',
           'm.go': 'package main\n\nfunc main() {}\n'})
for args in (['a.go', 'b.go', 'm.go'], ['b.go', 'a.go', 'm.go']):
    rc, o = go(d3, 'run', *args)
    print(f'  go run {" ".join(args)}:\n{o}')
rc, o = go(d3, 'run', '.')
print(f'  go run .(按文件名排序):\n{o}')

print('== 四:GODEBUG=inittrace=1:运行时打印每个包 init 的耗时与分配')
e = dict(os.environ); e['GODEBUG'] = 'inittrace=1'
p = subprocess.run([str(d / 'app')], capture_output=True, text=True, env=e)
lines = [re.sub(r'@[\d.]+ ms, [\d.]+ ms clock', '@… ms, … ms clock', l) for l in p.stderr.split('\n') if l.startswith('init ')]
print(f'  标准库与运行时一共有 {len(lines)} 条 init 记录;其中 lab 模块的包:')
for l in p.stderr.split('\n'):
    if l.startswith('init lab') or l.startswith('init main'): print('    ' + re.sub(r'@[\d.]+ ms, ([\d.]+) ms clock, (\d+) bytes, (\d+) allocs', r'@… ms, \1 ms clock, \2 bytes, \3 allocs', l))

print('== 五:编译器对初始化的限制')
def ce(name, code, n=3):
    rr = grun(name, {'main.go': code})
    return [re.sub(r'^\./', '', l) for l in rr['cout'].split('\n') if re.match(r'^(\./)?main\.go:\d+', l)][:n], rr
for title, code in [('初始化循环', 'package main\n\nvar a = b\nvar b = a\n\nfunc main() {}\n'),
                    ('通过函数形成的初始化循环', 'package main\n\nvar x = f()\n\nfunc f() int { return x + 1 }\n\nfunc main() {}\n'),
                    ('手动调用 init()', 'package main\n\nfunc init() {}\n\nfunc main() { init() }\n'),
                    ('init 带参数或返回值', 'package main\n\nfunc init(n int) {}\n\nfunc main() {}\n'),
                    ('init 作为变量使用', 'package main\n\nvar f = init\n\nfunc init() {}\n\nfunc main() {}\n')]:
    ls, rr = ce('ie', code)
    print(f'  {title}:')
    for l in ls: print('    ' + l)
