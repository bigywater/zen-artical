import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c12')
purge()
REFS = ['busybox:1.36', 'alpine:3.20', 'debian:12-slim', 'ubuntu:24.04']
img(*REFS)
print('== 一:四个常见基础镜像的体积(Docker Engine 29.8.2,linux/arm64;docker images 的 DISK USAGE 是压缩内容加解包后的层,CONTENT SIZE 是压缩内容)')
rows = []
for ref in REFS:
    rc, o = dk('images', ref)
    l = o.split('\n')[1]
    parts = re.split(r'\s{2,}', l.strip())
    rows.append((ref, parts))
    print(f'  {ref:16s} DISK USAGE {parts[2]:>8s}   CONTENT SIZE {parts[3]:>8s}')
print('== 二:镜像里有多少文件、什么系统库、有没有 shell 和包管理器')
CMD = r'''
echo "文件数 $(find / -xdev -type f 2>/dev/null | wc -l)"
printf "libc: "; (ls /lib/ld-musl-*.so.1 2>/dev/null | head -1) || true; ls /lib/aarch64-linux-gnu/libc.so.6 2>/dev/null | head -1; echo
printf "shell: "; for s in /bin/sh /bin/bash; do [ -e $s ] && printf "$s "; done; echo
printf "包管理器: "; for p in apk apt-get dpkg opkg; do command -v $p >/dev/null 2>&1 && printf "$p "; done; echo
. /etc/os-release 2>/dev/null; echo "系统: ${PRETTY_NAME:-无 os-release}"
'''
for ref in REFS:
    rc, o = dk('run', '--rm', *LAB, ref, 'sh', '-c', CMD)
    print(f'  [{ref}] ' + ' | '.join(l.strip() for l in o.split('\n') if l.strip()))
print('== 三:同一个静态 Go 程序放进不同基础镜像,镜像总大小')
GOSRC = 'package main\nimport "fmt"\nfunc main() { fmt.Println("hello from static go") }\n'
d = ctx('c12', {'main.go': GOSRC, 'go.mod': 'module lab\n\ngo 1.27\n'})
env = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', CGO_ENABLED='0', GOOS='linux', GOARCH='arm64')
r = subprocess.run(['/opt/homebrew/bin/go', 'build', '-ldflags=-s -w', '-o', 'app', '.'], cwd=d, env=env, capture_output=True, text=True); assert r.returncode == 0, r.stderr
binsize = (d / 'app').stat().st_size
print(f'  Go 静态二进制(-ldflags="-s -w"):{binsize / 1e6:.2f} MB')
for ref in ['scratch'] + REFS:
    tag = 'bwlab-c12-' + ref.replace(':', '-')
    dd = ctx('c12_' + ref.replace(':', '-'), {'Dockerfile': f'FROM {ref}\nCOPY app /app\nENTRYPOINT ["/app"]\n'})
    shutil.copy(d / 'app', dd / 'app')
    rc, o = build(dd, tag)
    if rc: print(f'  {ref}:构建失败 {o[-120:]}'); continue
    s = int(out('image', 'inspect', '--format', '{{.Size}}', tag))
    rc, o2 = dk('run', '--rm', *LAB, tag)
    print(f'  FROM {ref:15s} → 镜像 Size {s / 1e6:6.2f} MB;运行输出:{o2.strip()}')
print('== 四:没有 shell 的镜像里想进去看看:用 --entrypoint sh 启动')
for ref in ['scratch', 'alpine:3.20']:
    tag = 'bwlab-c12-' + ref.replace(':', '-')
    rc, o = dk('run', '--rm', *LAB, '--entrypoint', 'sh', tag, '-c', 'echo shell 可用')
    print(f'  {ref}:退出码 {rc};输出:{next((l for l in o.strip().splitlines() if 'docker:' in l or 'shell' in l), o.strip())[:260]}')
purge()
for r_ in REFS:
    if r_ != 'alpine:3.20': subprocess.run(['docker', 'rmi', '-f', r_], capture_output=True)
