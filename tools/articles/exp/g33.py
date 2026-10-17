import sys, os, re, time, statistics, subprocess, zipfile, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g33')
PROXY = GT / 'proxy2'
shutil.rmtree(PROXY, ignore_errors=True); PROXY.mkdir(parents=True)
BASE = 'example.test'
def publish(name, ver, deps, code):
    mdir = PROXY / BASE / name / '@v'; mdir.mkdir(parents=True, exist_ok=True)
    mod_txt = f'module {BASE}/{name}\n\ngo 1.21\n' + ''.join(f'\nrequire {BASE}/{dn} {dv}' for dn, dv in deps) + '\n'
    lst = mdir / 'list'; vs = set(lst.read_text().split()) if lst.exists() else set(); vs.add(ver); lst.write_text('\n'.join(sorted(vs)) + '\n')
    (mdir / f'{ver}.info').write_text(json.dumps({'Version': ver, 'Time': '2024-01-01T00:00:00Z'}))
    (mdir / f'{ver}.mod').write_text(mod_txt)
    with zipfile.ZipFile(mdir / f'{ver}.zip', 'w') as z:
        z.writestr(f'{BASE}/{name}@{ver}/go.mod', mod_txt)
        z.writestr(f'{BASE}/{name}@{ver}/{name}.go', code)
publish('e', 'v1.1.0', [], 'package e\n\nfunc Info() string { return "e v1.1.0" }\n')
publish('e', 'v1.3.0', [], 'package e\n\nfunc Info() string { return "e v1.3.0" }\n')
publish('lib', 'v1.0.0', [('e', 'v1.1.0')], f'package lib\n\nimport "{BASE}/e"\n\nfunc Info() string {{ return "lib v1.0.0(代理里已发布的版本),使用 " + e.Info() }}\n')
PENV = dict(GOPROXY='file://' + str(PROXY), GOSUMDB='off', GOFLAGS='-mod=mod')
def g(d, *args, env=None, tmo=120, ws=False):
    e = dict(PENV)
    if ws: e['GOFLAGS'] = ''
    e.update(env or {})
    return go(d, *args, env=e, timeout=tmo)
def P(title, o, n=20):
    print(f'  {title}')
    for l in o.split('\n')[:n]: print('    ' + l.replace(BASE + '/', '').replace(str(GT), '<gtmp>'))

root = gdir('ws')
app, lib = root / 'app', root / 'lib'
write(app, {'main.go': f'package main\n\nimport (\n\t"fmt"\n\t"{BASE}/e"\n\t"{BASE}/lib"\n)\n\nfunc main() {{\n\tfmt.Println(lib.Info())\n\tfmt.Println("app 直接使用 " + e.Info())\n}}\n',
            'go.mod': f'module app\n\ngo 1.21\n\nrequire (\n\t{BASE}/e v1.3.0\n\t{BASE}/lib v1.0.0\n)\n'})
write(lib, {'go.mod': f'module {BASE}/lib\n\ngo 1.21\n\nrequire {BASE}/e v1.1.0\n',
            'lib.go': f'package lib\n\nimport "{BASE}/e"\n\nfunc Info() string {{ return "lib 本地开发版(正在改的代码),使用 " + e.Info() }}\n'})
rc, o = g(app, 'mod', 'tidy'); assert rc == 0, o
gomod_before = (app / 'go.mod').read_text()
print('== 一:没有 go.work:app 用的是代理里已发布的 lib v1.0.0')
rc, o = g(app, 'run', '.'); P('app 里 go run .:', o)
print('  要在 app 里试用本地改过的 lib,传统做法是改 app/go.mod 加 replace(会改动要提交的文件):')
(app / 'go.mod').write_text(gomod_before + f'\nreplace {BASE}/lib => ../lib\n')
rc, o = g(app, 'run', '.'); P('加了 replace 之后 go run .:', o)
print('  app/go.mod 被改动的部分:' + ' | '.join(l for l in (app / 'go.mod').read_text().split('\n') if 'replace' in l).replace(BASE + '/', ''))
(app / 'go.mod').write_text(gomod_before)

print('== 二:用 go.work:app/go.mod 保持不动')
rc, o = g(root, 'work', 'init', './app', './lib'); print(f'  go work init ./app ./lib:rc={rc} {o}')
print('  go.work 内容:'); [print('    ' + l) for l in (root / 'go.work').read_text().split('\n') if l.strip()]
rc, o = g(app, 'run', '.'); P('在工作区里沿用 GOFLAGS=-mod=mod 时 go run .(工作区模式不允许 -mod=mod):', o, 3)
rc, o = g(app, 'run', '.', ws=True); P('去掉 -mod=mod 之后在 app 目录里 go run .:', o)
print(f'  app/go.mod 与之前相同?{(app / "go.mod").read_text() == gomod_before}')
rc, o = g(app, 'env', 'GOWORK'); print('  go env GOWORK(在 app 里):' + o.replace(str(GT), '<gtmp>'))
rc, o = g(app, 'list', '-m', 'all', ws=True); P('工作区里 go list -m all:', o)
rc, o = g(app, 'run', '.', env={'GOWORK': 'off'}, ws=True); P('GOWORK=off 之后 go run .(回到发布的 lib):', o)

print('== 三:工作区里的版本选择:app 要 e v1.3.0,lib 要 e v1.1.0——取并集里的最大版本')
rc, o = g(app, 'list', '-m', f'{BASE}/e', ws=True); print('  工作区里 go list -m e → ' + o.replace(BASE + '/', ''))
rc, o = g(lib, 'list', '-m', f'{BASE}/e', ws=True); print('  在 lib 目录里(也在工作区中)go list -m e → ' + o.replace(BASE + '/', ''))
rc, o = g(lib, 'list', '-m', f'{BASE}/e', env={'GOWORK': 'off'}, ws=True); print('  lib 目录里 GOWORK=off:go list -m e → ' + o.replace(BASE + '/', ''))

print('== 四:go work 的其它命令')
rc, o = g(root, 'work', 'edit', '-json'); P('go work edit -json:', o, 30)
shutil.rmtree(root / 'go.work', ignore_errors=True)
for f in ('go.work', 'go.work.sum'):
    if (root / f).exists(): (root / f).unlink()
mod(root / 'x') if False else None
extra = gdir('ws2'); write(extra, {'main.go': 'package main\n\nfunc main() {}\n', 'go.mod': 'module other\n\ngo 1.21\n'})
rc, o = g(root, 'work', 'init', './app'); rc, o = g(root, 'work', 'use', './lib'); print(f'  go work init ./app 之后 go work use ./lib:rc={rc}')
print('  再 go work use ./不存在 :' + g(root, 'work', 'use', './nothing')[1].replace(str(GT), '<gtmp>')[:160])
rc, o = g(root, 'work', 'sync'); print(f'  go work sync:rc={rc}')
print('  go.work 内容:'); [print('    ' + l) for l in (root / 'go.work').read_text().split('\n') if l.strip()]

print('== 五:go mod tidy 与 go.work:tidy 只看单个模块,不受工作区影响')
rc, o = g(app, 'mod', 'tidy', ws=True); print(f'  工作区里在 app 目录 go mod tidy:rc={rc};app/go.mod 变了吗?{(app / "go.mod").read_text() != gomod_before}')
rc, o = g(app, 'build', '-o', 'bin', '.', env={'GOWORK': 'off'}); print(f'  GOWORK=off 构建:rc={rc}')
shutil.rmtree(GT / 'ws2', ignore_errors=True)
