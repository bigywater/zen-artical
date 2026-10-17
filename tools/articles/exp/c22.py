import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c22')
img('alpine:3.20', 'python:3.12-alpine')
purge()
d = ctx('c22', {'Dockerfile': 'FROM alpine:3.20\nRUN mkdir /app && echo from-image > /app/hello.txt\n'})
rc, o = build(d, 'bwlab-c22', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def vols(): return sorted(v for v in out('volume', 'ls', '-q', '--filter', 'label=bwlab=1').split())
print('== 一:生命周期:docker rm 之后数据去哪了(Docker Engine 29.8.2)')
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c22-named')
rc, o = dk('run', '--name', 'bwlab-c22-a', *LAB, '-v', 'bwlab-c22-named:/data', '-v', '/anon', 'bwlab-c22', 'sh', '-c', 'echo keep > /data/f.txt; echo anon > /anon/f.txt')
anon = [v for v in out('inspect', '--format', '{{range .Mounts}}{{.Name}} {{end}}', 'bwlab-c22-a').split() if v != 'bwlab-c22-named'][0]
print(f'  容器退出后:命名卷 bwlab-c22-named、匿名卷 {anon[:12]}…(64 位随机名)都存在?{"bwlab-c22-named" in out("volume", "ls", "-q")} / {anon in out("volume", "ls", "-q")}')
dk('rm', 'bwlab-c22-a')
print(f'  docker rm(不带 -v)之后:命名卷在?{"bwlab-c22-named" in out("volume", "ls", "-q")};匿名卷在?{anon in out("volume", "ls", "-q")}')
rc, o = dk('run', '--rm', '-v', 'bwlab-c22-named:/data', 'alpine:3.20', 'cat', '/data/f.txt'); print(f'  新容器挂上命名卷,读到 /data/f.txt = {o.strip()}')
rc, o = dk('run', '--name', 'bwlab-c22-b', *LAB, '-v', '/anon2', 'alpine:3.20', 'true')
anon2 = out('inspect', '--format', '{{range .Mounts}}{{.Name}}{{end}}', 'bwlab-c22-b')
dk('rm', '-v', 'bwlab-c22-b')
print(f'  docker rm -v 之后:匿名卷在?{anon2 in out("volume", "ls", "-q")}')
dk('volume', 'rm', anon)
print('== 二:第一次挂载时,卷里的内容从哪来')
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c22-init')
rc, o = dk('run', '--rm', '-v', 'bwlab-c22-init:/app', 'bwlab-c22', 'ls', '-A', '/app'); print(f'  镜像的 /app 里有 hello.txt;空的命名卷挂到 /app:ls = {o.strip()}(卷第一次挂载时,镜像该目录的内容被复制进去)')
hp = str(DT / 'c22-bind'); os.makedirs(hp, exist_ok=True)
rc, o = dk('run', '--rm', '-v', f'{hp}:/app', 'bwlab-c22', 'ls', '-A', '/app'); print(f'  空的宿主机目录 bind mount 到 /app:ls = {o.strip() or "(空)"}(镜像里的内容被盖住了)')
print(f'  宿主机目录里事后有文件吗?{os.listdir(hp)}')
print('  重建镜像(hello.txt 内容改成 from-image-v2)后,再挂同一个已有内容的卷:')
d2 = ctx('c22b', {'Dockerfile': 'FROM alpine:3.20\nRUN mkdir /app && echo from-image-v2 > /app/hello.txt\n'})
build(d2, 'bwlab-c22v2', '--provenance=false', '--sbom=false')
rc, o = dk('run', '--rm', '-v', 'bwlab-c22-init:/app', 'bwlab-c22v2', 'cat', '/app/hello.txt'); print(f'    cat /app/hello.txt = {o.strip()}(卷里已有第一次复制进去的 from-image,新镜像里的 from-image-v2 不会覆盖它)')
print('== 三:读写速度:镜像层(可写层)、命名卷、宿主机 bind mount(macOS)')
PY = '''
import os, time, sys
base = sys.argv[1]
def t(f):
    t0 = time.perf_counter(); f(); return (time.perf_counter() - t0) * 1000
def big():
    with open(base + "/big.bin", "wb") as h:
        for _ in range(64): h.write(b"\\0" * (1 << 20))
        h.flush(); os.fsync(h.fileno())
def small():
    for i in range(1000):
        with open(base + "/s%d.txt" % i, "w") as h: h.write("x")
def lst():
    for _ in range(20): os.listdir(base)
def rd():
    with open(base + "/big.bin", "rb") as h:
        while h.read(1 << 20): pass
os.makedirs(base, exist_ok=True)
print("%.0f %.0f %.0f %.0f" % (t(big), t(small), t(rd), t(lst)))
'''
d3 = ctx('c22p', {'m.py': PY})
hp2 = str(DT / 'c22-bind-perf'); os.makedirs(hp2, exist_ok=True)
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c22-perf')
modes = {'容器可写层': [], '命名卷': ['-v', 'bwlab-c22-perf:/w'], 'bind mount(宿主机目录)': ['-v', f'{hp2}:/w']}
res = {k: [] for k in modes}
for rnd in range(3):
    for k, o_ in modes.items():
        path = '/w/t' + str(rnd) if o_ else '/tmp/t' + str(rnd)
        rc, o = dk('run', '--rm', *LAB, *o_, '-v', f'{d3}/m.py:/m.py:ro', 'python:3.12-alpine', 'python', '/m.py', path)
        res[k].append([int(x) for x in o.strip().split()])
for k in modes:
    cols = list(zip(*res[k]))
    print(f'  {k}:写 64 MiB 含 fsync {med(cols[0]):.0f} ms;建 1000 个小文件 {med(cols[1]):.0f} ms;顺序读 64 MiB {med(cols[2]):.0f} ms;listdir 20 次 {med(cols[3]):.0f} ms(3 轮取中位数)')
print('== 四:挂载一个不存在的宿主机路径:-v 和 --mount 的差别')
miss = str(DT / 'c22-missing-v')
rc, o = dk('run', '--rm', '-v', f'{miss}:/x', 'alpine:3.20', 'true')
print(f'  -v {os.path.basename(miss)}:/x → 退出码 {rc};宿主机上现在有这个目录吗?{os.path.isdir(miss)}')
miss2 = str(DT / 'c22-missing-m')
rc, o = dk('run', '--rm', '--mount', f'type=bind,source={miss2},target=/x', 'alpine:3.20', 'true')
print(f'  --mount type=bind,source={os.path.basename(miss2)} → 退出码 {rc};{[l for l in o.splitlines() if "rror" in l or "bind source" in l][0][:140]};宿主机上有这个目录吗?{os.path.isdir(miss2)}')
purge()
