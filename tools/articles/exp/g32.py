import sys, os, re, time, statistics, subprocess, zipfile, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g32')
# ---------- 本地 GOPROXY:file:// 目录,按 Go 的代理协议放 list / info / mod / zip ----------
PROXY = GT / 'proxy'
shutil.rmtree(PROXY, ignore_errors=True); PROXY.mkdir(parents=True)
BASE = 'example.test'
# 模块图:名字 → {版本: [(依赖名, 依赖版本)]}
GRAPH = {
    'b': {'v1.1.0': [('d', 'v1.1.0')], 'v1.2.0': [('d', 'v1.3.0')]},
    'c': {'v1.1.0': [('d', 'v1.2.0')], 'v1.2.0': [('d', 'v1.4.0')]},
    'd': {'v1.1.0': [('e', 'v1.1.0')], 'v1.2.0': [('e', 'v1.1.0')], 'v1.3.0': [('e', 'v1.2.0')], 'v1.4.0': [('e', 'v1.2.0')]},
    'e': {'v1.1.0': [], 'v1.2.0': [], 'v1.3.0': []},
}
def modfile(name, deps):
    return f'module {BASE}/{name}\n\ngo 1.21\n' + ''.join(f'\nrequire {BASE}/{dn} {dv}' for dn, dv in deps) + '\n'
def src(name, ver, deps):
    imp = ''.join(f'\t{dn} "{BASE}/{dn}"\n' for dn, dv in deps)
    body = f'"{name} {ver}"' + ''.join(f' + " → " + {dn}.Info()' for dn, dv in deps)
    return f'package {name}\n\nimport (\n{imp})\n\nfunc Info() string {{ return {body} }}\n' if deps else f'package {name}\n\nfunc Info() string {{ return "{name} {ver}" }}\n'
for name, vers in GRAPH.items():
    mdir = PROXY / BASE / name / '@v'; mdir.mkdir(parents=True)
    (mdir / 'list').write_text('\n'.join(vers) + '\n')
    for v, deps in vers.items():
        (mdir / f'{v}.info').write_text(json.dumps({'Version': v, 'Time': '2024-01-01T00:00:00Z'}))
        (mdir / f'{v}.mod').write_text(modfile(name, deps))
        with zipfile.ZipFile(mdir / f'{v}.zip', 'w') as z:
            z.writestr(f'{BASE}/{name}@{v}/go.mod', modfile(name, deps))
            z.writestr(f'{BASE}/{name}@{v}/{name}.go', src(name, v, deps))
PENV = dict(GOPROXY='file://' + str(PROXY), GOSUMDB='off', GOFLAGS='-mod=mod', GONOSUMCHECK='1')
def g(d, *args, tmo=120):
    return go(d, *args, env=PENV, timeout=tmo)
def show(title, o, n=30, ind='    '):
    print(f'  {title}')
    for l in o.split('\n')[:n]: print(ind + l.replace(BASE + '/', ''))

print('== 一:模块图。主模块直接依赖 b v1.2.0 与 c v1.2.0;各模块的 go.mod 需求如下(本机 file:// 代理里的真实文件)')
for name, vers in GRAPH.items():
    for v, deps in vers.items():
        print(f'  {name} {v} 需要:' + (', '.join(f'{dn} {dv}' for dn, dv in deps) or '(无)'))
d = gdir('mv1')
write(d, {'main.go': f'package main\n\nimport (\n\t"fmt"\n\t"{BASE}/b"\n\t"{BASE}/c"\n)\n\nfunc main() {{\n\tfmt.Println(b.Info())\n\tfmt.Println(c.Info())\n}}\n',
          'go.mod': f'module app\n\ngo 1.21\n\nrequire (\n\t{BASE}/b v1.2.0\n\t{BASE}/c v1.2.0\n)\n'})
rc, o = g(d, 'mod', 'tidy'); assert rc == 0, o
print('  go mod tidy 之后的 go.mod:')
for l in (d / 'go.mod').read_text().replace(BASE + '/', '').split('\n'): print('    ' + l)

print('== 二:go list -m all(构建列表)与 go mod graph(需求边)')
rc, o = g(d, 'list', '-m', 'all'); show('go list -m all:', o)
rc, o = g(d, 'mod', 'graph'); show('go mod graph:', o)
rc, o = g(d, 'list', '-m', '-versions', f'{BASE}/e'); print('  e 仓库里有的版本:' + o.replace(BASE + '/', ''))
rc, o = g(d, 'run', '.'); print('  go run . 输出(每个模块把自己实际用的版本打印出来):'); [print('    ' + l) for l in o.split('\n')]

print('== 三:MVS 取的是“需求里出现过的最大版本”,不是仓库里最新的版本')
print('  构建列表里 d 是 v1.4.0(b 要 v1.3.0、c 要 v1.4.0,取大者);e 是 v1.2.0(d v1.4.0 要 e v1.2.0)——即使 e 已经有 v1.3.0。')
rc, o = g(d, 'list', '-m', f'{BASE}/e'); print('  go list -m e → ' + o.replace(BASE + '/', ''))

print('== 四:升级与降级')
d2 = gdir('mv2'); shutil.copytree(d / 'go.mod', d2 / 'go.mod') if False else None
write(d2, {'main.go': (d / 'main.go').read_text(), 'go.mod': (d / 'go.mod').read_text()})
shutil.copy(d / 'go.sum', d2 / 'go.sum')
rc, o = g(d2, 'get', f'{BASE}/e@latest'); print('  go get e@latest:' + ' / '.join(o.replace(BASE + '/', '').split('\n')[:3]))
rc, o = g(d2, 'list', '-m', 'all'); show('升级之后 go list -m all:', o)
print('  go.mod 里新增的需求:' + ' | '.join(l.strip().replace(BASE + '/', '') for l in (d2 / 'go.mod').read_text().split('\n') if 'e v' in l or 'indirect' in l and ' e ' in l))
d3 = gdir('mv3'); write(d3, {'main.go': (d / 'main.go').read_text(), 'go.mod': (d / 'go.mod').read_text()})
shutil.copy(d / 'go.sum', d3 / 'go.sum')
rc, o = g(d3, 'get', f'{BASE}/d@v1.1.0'); show('go get d@v1.1.0(降级):', o.replace(BASE + '/', ''), 8)
rc, o = g(d3, 'list', '-m', 'all'); show('降级之后 go list -m all:', o)
rc, o = go(d3, 'run', '.', env={**PENV, 'GOFLAGS': '-mod=readonly'})
print(f'  降级后用 -mod=readonly 构建(不允许自动改 go.mod):rc={rc}'); [print('    ' + l.replace(BASE + '/', '')) for l in o.split('\n')[:3]]
print('  降级后 go.mod:'); [print('    ' + l.replace(BASE + '/', '')) for l in (d3 / 'go.mod').read_text().split('\n') if l.strip()]

print('== 五:why、exclude 与 replace')
rc, o = g(d, 'mod', 'why', '-m', f'{BASE}/e'); show('go mod why -m e:', o.replace(BASE + '/', ''))
d4 = gdir('mv4'); write(d4, {'main.go': (d / 'main.go').read_text(), 'go.mod': (d / 'go.mod').read_text() + f'\nexclude {BASE}/d v1.4.0\n'})
shutil.copy(d / 'go.sum', d4 / 'go.sum')
rc, o = g(d4, 'list', '-m', 'all'); show('go.mod 里 exclude d v1.4.0 之后 go list -m all:', o)
d5 = gdir('mv5'); write(d5, {'main.go': (d / 'main.go').read_text(), 'go.mod': (d / 'go.mod').read_text() + f'\nreplace {BASE}/e => ../e_local\n', 'x': ''})
shutil.copy(d / 'go.sum', d5 / 'go.sum')
write(d5.parent / 'e_local', {'go.mod': f'module {BASE}/e\n\ngo 1.21\n', 'e.go': 'package e\n\nfunc Info() string { return "e 本地替换版" }\n'})
rc, o = g(d5, 'run', '.'); print('  replace e => ../e_local 之后 go run . 输出:'); [print('    ' + l.replace(BASE + '/', '')) for l in o.split('\n')]
shutil.rmtree(GT / 'e_local', ignore_errors=True)
