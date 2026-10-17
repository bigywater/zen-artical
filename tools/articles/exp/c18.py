import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c18')
img('alpine:3.20')
purge()
def mk(tag, seed, mb, frm='alpine:3.20'):
    d = ctx('c18_' + seed, {'Dockerfile': f'FROM {frm}\nCOPY f.bin /f-{seed}.bin\n', 'f.bin': os.urandom(int(mb * 1024 * 1024))})
    rc, o = build(d, tag, '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def table():
    rc, o = dk('system', 'df', '-v')
    rows = {}
    for l in o.split('\n'):
        p = l.split()
        if len(p) >= 8 and p[0].startswith('bwlab-c18') and re.match(r'[\d.]+(B|kB|MB|GB)$', p[-4]):
            rows[p[0]] = tuple(p[-4:])
    return rows
def mb(s):
    m = re.match(r'([\d.]+)(B|kB|MB|GB)', s); v = float(m.group(1))
    return v * {'B': 1e-6, 'kB': 1e-3, 'MB': 1, 'GB': 1e3}[m.group(2)]
print('== 一:一个 20 MB 的“基础”镜像,三个镜像 FROM 它,各自再加 1 MB 随机文件(Docker Engine 29.8.2,docker system df -v)')
mk('bwlab-c18base', 'base', 20)
t = table()
print(f'  只有基础镜像时:{t}')
for n, s in (('x', 'x'), ('y', 'y'), ('z', 'z')): mk(f'bwlab-c18{n}', s, 1, 'bwlab-c18base')
t = table()
for k, v in t.items(): print(f'  {k:16s} SIZE {v[0]:>8s}  SHARED SIZE {v[1]:>8s}  UNIQUE SIZE {v[2]:>8s}  CONTAINERS {v[3]}')
tot = sum(mb(v[0]) for k, v in t.items()); real = mb(t['bwlab-c18base'][0]) + sum(mb(t[k][2]) for k in ('bwlab-c18x', 'bwlab-c18y', 'bwlab-c18z'))
print(f'  四个镜像的 SIZE 加起来 {tot:.1f} MB;基础镜像加上三个 UNIQUE SIZE 是 {real:.1f} MB(这才是更接近真实占用的数字)')
print('== 二:删掉基础镜像的名字,三个子镜像受影响吗')
rc, o = dk('rmi', 'bwlab-c18base'); print(f'  docker rmi bwlab-c18base → 退出码 {rc};输出:{o.strip().splitlines()[0][:80]}')
t2 = table()
print(f'  剩下的镜像:{sorted(t2)}')
for k in ('bwlab-c18x',): print(f'  {k}:SIZE {t2[k][0]} SHARED {t2[k][1]} UNIQUE {t2[k][2]}')
rc, o = dk('run', '--rm', 'bwlab-c18x', 'ls', '-l', '/f-x.bin'); print(f'  运行 x(仍可用?)退出码 {rc};{o.split()[4] if rc == 0 else o[:60]} 字节')
print('== 三:docker image ls 的 SIZE 与 docker system df -v 的 SIZE')
mk('bwlab-c18q', 'q', 5)
rc, o = dk('images', 'bwlab-c18q'); print('  docker images 的 DISK USAGE 与 CONTENT SIZE:' + ' / '.join(re.split(r'\s{2,}', o.split('\n')[1].strip())[2:4]))
print('  docker system df -v:SIZE ' + table()['bwlab-c18q'][0] + ',SHARED ' + table()['bwlab-c18q'][1] + ',UNIQUE ' + table()['bwlab-c18q'][2])
purge()
