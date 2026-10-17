import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g34')
PROGS = {
    'println 版(不导入 fmt)': 'package main\n\nfunc main() { println("hello") }\n',
    'fmt.Println 版': 'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("hello") }\n',
    '加 encoding/json': 'package main\n\nimport (\n\t"encoding/json"\n\t"fmt"\n)\n\nfunc main() {\n\tb, _ := json.Marshal(map[string]int{"a": 1})\n\tfmt.Println(string(b))\n}\n',
    '加 net/http 客户端': 'package main\n\nimport (\n\t"fmt"\n\t"net/http"\n)\n\nfunc main() {\n\tr, err := http.Get("http://127.0.0.1:1/")\n\tfmt.Println(r, err)\n}\n',
    '加 net/http 服务端': 'package main\n\nimport (\n\t"fmt"\n\t"net/http"\n)\n\nfunc main() {\n\thttp.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "ok") })\n\tfmt.Println(http.ListenAndServe("127.0.0.1:1", nil))\n}\n',
}
def build(name, code, flags=(), env=None, out='app'):
    d = gdir(name); write(d, {'main.go': code}); mod(d)
    rc, o = go(d, 'build', *flags, '-o', out, env=dict(CGO_ENABLED='0', **(env or {})))
    assert rc == 0, o
    return d, os.path.getsize(d / out)
print('== 一:不同程序的二进制大小(Go 1.27.1,darwin/arm64,CGO_ENABLED=0)')
MiB = 1 << 20
res = {}
for label, code in PROGS.items():
    _, a = build('bs', code)
    _, b = build('bs', code, ['-ldflags=-s -w'])
    res[label] = (a, b)
    print(f'  {label}:默认 {a} 字节({a / MiB:.2f} MiB);-ldflags="-s -w" {b} 字节({b / MiB:.2f} MiB),小 {(a - b) / a * 100:.0f}%')

print('== 二:-s 与 -w 各去掉了什么(fmt.Println 版)')
code = PROGS['fmt.Println 版']
for label, fl in [('默认', []), ('-ldflags=-s(去掉符号表)', ['-ldflags=-s']), ('-ldflags=-w(去掉 DWARF 调试信息)', ['-ldflags=-w']), ('-ldflags="-s -w"', ['-ldflags=-s -w']), ('-trimpath', ['-trimpath']), ('-trimpath 加 -s -w', ['-trimpath', '-ldflags=-s -w'])]:
    _, n = build('bs2', code, fl)
    print(f'  {label}:{n} 字节({n / MiB:.2f} MiB)')
d, _ = build('bs2', code)
rc, o = subprocess.run(['size', '-m', str(d / 'app')], capture_output=True, text=True).returncode, subprocess.run(['size', '-m', str(d / 'app')], capture_output=True, text=True).stdout
segs = [l.strip() for l in o.split('\n') if l.startswith('Segment') or l.strip().startswith('Section')]
print('  size -m(默认构建)里的段:')
for l in segs[:16]: print('    ' + l)

print('== 三:体积用在哪:go tool nm -size 按包汇总(net/http 服务端版,默认构建)')
d, n = build('bs3', PROGS['加 net/http 服务端'])
rc, nm = go(d, 'tool', 'nm', '-size', '-sort', 'size', 'app')
pk = {}
rows = []
bss = []
for l in nm.split('\n'):
    p = l.split()
    if len(p) >= 4 and p[1].isdigit():
        sz, typ, name = int(p[1]), p[2], p[3]
        if typ in ('B', 'b'): bss.append((sz, name)); continue   # 未初始化数据(BSS)不占文件空间
        rows.append((sz, name))
        m = re.match(r'^(type:\.|go:|runtime\.|[\w./-]+?)(?=\.[A-Za-z_(*\[]|$)', name)
        key = 'runtime' if name.startswith('runtime.') else ('type:*(类型描述符)' if name.startswith('type:') else ('go:*(编译器生成的数据)' if name.startswith('go:') else re.match(r'^([^.]*(?:/[^.]*)*)', name).group(1)))
        pk[key] = pk.get(key, 0) + sz
tot = sum(pk.values())
print(f'  nm 里占文件空间的符号(类型 T/R/D 等,不含 BSS)合计 {tot} 字节(文件 {n} 字节);BSS 符号合计 {sum(x for x, _ in bss)} 字节,最大的是 {sorted(bss, reverse=True)[0][1]}({sorted(bss, reverse=True)[0][0]} 字节)——BSS 不占文件空间,但运行时要映射内存')
for k, v in sorted(pk.items(), key=lambda x: -x[1])[:10]: print(f'    {k:32s} {v:9d} 字节 {v / tot * 100:5.1f}%')
print('  最大的 5 个符号:')
for sz, name in rows[:5]: print(f'    {sz:8d}  {name[:70]}')

print('== 四:-s 之后还能看到函数名吗:panic 的栈回溯靠 pclntab,不靠符号表')
PAN = 'package main\n\nfunc boom() { var m map[string]int; m["a"] = 1 }\n\nfunc main() { boom() }\n'
for label, fl in [('默认', []), ('-ldflags="-s -w"', ['-ldflags=-s -w'])]:
    d, n = build('bs4', PAN, fl)
    p = subprocess.run([str(d / 'app')], capture_output=True, text=True)
    fns = [re.sub(r'\(0x[0-9a-f, ]*\)|\(\)', '()', l.strip()) for l in p.stderr.split('\n') if l.startswith('main.')]
    rc, nm = go(d, 'tool', 'nm', 'app')
    print(f'  {label}:{n} 字节;go tool nm {"可用,符号 " + str(len(nm.splitlines())) + " 个" if rc == 0 and nm.strip() else "没有符号:" + nm.strip()[:60]};panic 回溯里的函数:{" ".join(fns)}')

print('== 五:反射用法会让链接器保留更多方法:同一个类型有 200 个导出方法,是否通过反射按名字调用')
methods = '\n'.join(f'func (T) M{i}() int {{ return {i} }}' for i in range(200))
NOREF = f'package main\n\nimport "fmt"\n\ntype T struct{{}}\n\n{methods}\n\nfunc main() {{ fmt.Println(T{{}}.M1()) }}\n'
REF = f'package main\n\nimport (\n\t"fmt"\n\t"reflect"\n\t"os"\n)\n\ntype T struct{{}}\n\n{methods}\n\nfunc main() {{\n\tname := "M" + fmt.Sprint(len(os.Args))\n\tfmt.Println(reflect.ValueOf(T{{}}).MethodByName(name).Call(nil)[0])\n}}\n'
REF2 = f'package main\n\nimport (\n\t"fmt"\n\t"reflect"\n)\n\ntype T struct{{}}\n\n{methods}\n\nfunc main() {{\n\tfmt.Println(reflect.TypeOf(T{{}}).Name())\n}}\n'
for label, c in [('不用反射,只直接调 M1', NOREF), ('reflect.TypeOf(...).Name()(用了反射但不调方法)', REF2), ('reflect.Value.MethodByName(动态名字)', REF)]:
    _, n = build('bs5', c)
    _, ns = build('bs5', c, ['-ldflags=-s -w'])
    d, _ = build('bs5', c)
    rc, nm = go(d, 'tool', 'nm', 'app')
    cnt = len([1 for l in nm.split('\n') if re.search(r' main\.T\.M\d+$', l)])
    print(f'  {label}:默认 {n} 字节、-s -w {ns} 字节;符号表里 main.T.M<数字> 的函数有 {cnt} 个')
print('  同一个类型的方法数 N 变化时(都用 MethodByName,默认构建):')
base_n = None
for N in (0, 20, 100, 200):
    ms = '\n'.join(f'func (T) M{i}() int {{ return {i} }}' for i in range(N))
    c = f'package main\n\nimport (\n\t"fmt"\n\t"os"\n\t"reflect"\n)\n\ntype T struct{{}}\n\n{ms}\n\nfunc main() {{\n\tname := "M" + fmt.Sprint(len(os.Args))\n\tfmt.Println(reflect.ValueOf(T{{}}).MethodByName(name).IsValid())\n}}\n'
    _, n = build('bs5', c)
    if base_n is None: base_n = n
    print(f'    N = {N:3d}:{n} 字节,比 N = 0 多 {n - base_n} 字节' + (f'(每个方法约 {(n - base_n) / N:.0f} 字节)' if N else ''))
print('== 六:不同平台的 hello world(fmt.Println 版,CGO_ENABLED=0,交叉编译)')
for goos, goarch in [('darwin', 'arm64'), ('linux', 'amd64'), ('linux', 'arm64'), ('windows', 'amd64')]:
    _, n = build('bs6', PROGS['fmt.Println 版'], env=dict(GOOS=goos, GOARCH=goarch))
    _, ns = build('bs6', PROGS['fmt.Println 版'], ['-ldflags=-s -w'], env=dict(GOOS=goos, GOARCH=goarch))
    print(f'  {goos}/{goarch}:默认 {n} 字节({n / MiB:.2f} MiB);-s -w {ns} 字节({ns / MiB:.2f} MiB)')
shutil.rmtree(GT / 'bs', ignore_errors=True)
