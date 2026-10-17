import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g31')
FILES = {
    'main.go': '''package main

import "fmt"

func main() { fmt.Println(platform(), "|", arch(), "|", feature(), "|", family()) }
''',
    'os_linux.go': 'package main\n\nfunc platform() string { return "文件名后缀 _linux" }\n',
    'os_darwin.go': 'package main\n\nfunc platform() string { return "文件名后缀 _darwin" }\n',
    'os_windows.go': 'package main\n\nfunc platform() string { return "文件名后缀 _windows" }\n',
    'cpu_amd64.go': 'package main\n\nfunc arch() string { return "文件名后缀 _amd64" }\n',
    'cpu_arm64.go': 'package main\n\nfunc arch() string { return "文件名后缀 _arm64" }\n',
    'cpu_other.go': '//go:build !amd64 && !arm64\n\npackage main\n\nfunc arch() string { return "其它架构" }\n',
    'feat_debug.go': '//go:build debug\n\npackage main\n\nfunc feature() string { return "debug 版本" }\n',
    'feat_release.go': '//go:build !debug\n\npackage main\n\nfunc feature() string { return "正式版本" }\n',
    'family_unix.go': '//go:build unix\n\npackage main\n\nfunc family() string { return "unix 家族" }\n',
    'family_win.go': '//go:build !unix\n\npackage main\n\nfunc family() string { return "非 unix" }\n',
    'tool.go': '//go:build ignore\n\npackage main\n\nfunc main() { println("go run tool.go 才会用到") }\n',
    'windows.go': 'package main\n\n// 文件名里没有下划线:不受 GOOS 约束\nfunc noUnderscore() {}\n',
    'old_style.go': '// +build linux\n\npackage main\n\nfunc oldStyle() {}\n',
    'main_test.go': 'package main\n\nimport "testing"\n\nfunc TestX(t *testing.T) {}\n',
}
d = gdir('bt1'); write(d, FILES); mod(d)
print('== 一:不同 GOOS / GOARCH / -tags 下,go list 选中的文件(Go 1.27.1,CGO_ENABLED=0)')
def lst(goos, goarch, tags=None):
    env = dict(GOOS=goos, GOARCH=goarch, CGO_ENABLED='0')
    args = ['list', '-f', '{{join .GoFiles " "}}|{{join .IgnoredGoFiles " "}}']
    if tags: args += ['-tags', tags]
    rc, o = go(d, *args, env=env)
    sel, _, ign = o.partition('|')
    if rc != 0: return None, o[:120]
    return sel.split(), ign.split()
for goos, goarch, tags in [('darwin', 'arm64', None), ('linux', 'amd64', None), ('linux', 'arm64', 'debug'), ('windows', 'amd64', None), ('linux', '386', None)]:
    sel, ign = lst(goos, goarch, tags)
    print(f'  GOOS={goos} GOARCH={goarch}' + (f' -tags {tags}' if tags else '') + ':')
    print('    选中:' + ' '.join(sel))
    print('    排除:' + ' '.join(ign))

print('== 二:实际运行(本机 darwin/arm64):默认、-tags debug、并列出 go list 认为的约束')
for tags in (None, 'debug'):
    args = ['run', '.'] if not tags else ['run', '-tags', tags, '.']
    rc, o = go(d, *args, env=dict(CGO_ENABLED='0'))
    print(f'  go run {"-tags " + tags + " " if tags else ""}.:{o}')
rc, o = go(d, 'run', 'tool.go', env=dict(CGO_ENABLED='0'))
print(f'  go run tool.go(显式给出的文件,//go:build ignore 不再生效):{o}')

print('== 三:go list 里的 “tag 全集”:发布标签与 unix、cgo 等')
rc, o = go(d, 'list', '-f', '{{context.ReleaseTags}}', env=dict(CGO_ENABLED='0'))
tags = o.strip('[]').split()
print(f'  ReleaseTags 共 {len(tags)} 个,最早 {tags[0]},最近 {" ".join(tags[-4:])}')
rc, o = go(d, 'list', '-f', '{{context.BuildTags}}|{{context.ToolTags}}|{{context.CgoEnabled}}', env=dict(CGO_ENABLED='0'))
print(f'  BuildTags | ToolTags | CgoEnabled = {o}')
rc, o = go(d, 'list', '-f', '{{context.ToolTags}}|{{context.CgoEnabled}}', env=dict(CGO_ENABLED='1'))
print(f'  CGO_ENABLED=1:ToolTags | CgoEnabled = {o}')
UNIX = []
for goos, goarch in [('darwin', 'arm64'), ('linux', 'amd64'), ('windows', 'amd64'), ('freebsd', 'amd64'), ('netbsd', 'amd64'), ('openbsd', 'amd64'), ('solaris', 'amd64'), ('aix', 'ppc64'), ('ios', 'arm64'), ('android', 'arm64'), ('js', 'wasm'), ('plan9', 'amd64')]:
    gf, ig = lst(goos, goarch)
    if gf is None: UNIX.append(f'{goos}/{goarch} go list 报错({ig})')
    else: UNIX.append(f'{goos}/{goarch} {"满足" if "family_unix.go" in gf else "不满足"}')
print('  GOOS/GOARCH 是否满足 unix 标签:' + ';'.join(UNIX))

print('== 四:go vet 对构建约束的检查')
BAD = {'go.mod': None,
 'a.go': 'package a\n\n//go:build linux\n\nfunc A() {}\n',
 'b.go': '//go:build linux\n// +build darwin\n\npackage a\n\nfunc B() {}\n',
 'c.go': '// +build linux\n\npackage a\n\nfunc C() {}\n'}
dv = gdir('bt2'); mod(dv, name='lab2'); write(dv, {k: v for k, v in BAD.items() if v})
rc, o = go(dv, 'vet', './...', env=dict(CGO_ENABLED='0'))
print(f'  go vet:rc={rc}')
for l in o.split('\n'):
    if '.go' in l: print('    ' + re.sub(r'^\./', '', l))
rc, o = go(dv, 'list', '-f', '{{.GoFiles}}|{{.IgnoredGoFiles}}', env=dict(CGO_ENABLED='0'))
print(f'  go list(darwin 本机):选中 | 排除 = {o}')
shutil.rmtree(GT / 'bt2', ignore_errors=True)
