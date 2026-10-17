import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c20')
purge()
MB = 128
PY = '''
import os, time, sys
def t(f):
    t0 = time.perf_counter(); f(); return (time.perf_counter() - t0) * 1000
def append(p, n=b"x"):
    def f():
        with open(p, "ab") as h: h.write(n)
    return f
def chm(p):
    def f(): os.chmod(p, 0o600)
    return f
def rd(p):
    def f():
        with open(p, "rb") as h: h.read(1)
    return f
def mkbig(p):
    def f():
        with open(p, "wb") as h: h.write(b"\\0" * (MB << 20)); h.flush(); os.fsync(h.fileno())
    return f
MB = %d
print("读 big1.bin 的 1 字节: %%.1f ms" %% t(rd("/data/big1.bin")))
print("第 1 次往 big1.bin 追加 1 字节: %%.1f ms" %% t(append("/data/big1.bin")))
print("第 2 次往 big1.bin 追加 1 字节: %%.1f ms" %% t(append("/data/big1.bin")))
print("第 3 次往 big1.bin 追加 1 字节: %%.1f ms" %% t(append("/data/big1.bin")))
print("对没碰过的 big2.bin 只做 chmod: %%.1f ms" %% t(chm("/data/big2.bin")))
print("往 small.txt(1 KB)追加 1 字节: %%.1f ms" %% t(append("/data/small.txt")))
print("新建并写入 %%d MiB 的新文件(含 fsync): %%.1f ms" %% (MB, t(mkbig("/new.bin"))))
''' % MB
d = ctx('c20', {'Dockerfile': 'FROM python:3.12-alpine\nCOPY data /data\nCOPY m.py /m.py\n', 'data/big1.bin': os.urandom(MB << 20), 'data/big2.bin': os.urandom(MB << 20), 'data/small.txt': 'a' * 1024, 'm.py': PY})
rc, o = build(d, 'bwlab-c20', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
print(f'== 一:第一次写入一个大文件要整个复制到可写层(镜像里两个 {MB} MiB 的随机文件,python:3.12-alpine 做基础;Docker Engine 29.8.2)')
runs = []
for i in range(3):
    cid = out('run', '-d', *LAB, 'bwlab-c20', 'sleep', '600')
    rc, o = dk('exec', cid, 'python', '/m.py')
    runs.append({l.split(':')[0]: float(re.search(r'([\d.]+) ms', l).group(1)) for l in o.strip().splitlines() if 'ms' in l})
    if i < 2: dk('rm', '-f', cid)
for k in runs[0]:
    vals = [r[k] for r in runs]
    print(f'  {k}:{" / ".join(f"{v:.1f}" for v in vals)} ms(3 个新容器各跑一次;中位数 {med(vals):.1f} ms)')
print('== 二:copy-up 之后,upperdir 里多了什么')
mt = vm(f"grep '{cid}' /proc/mounts").splitlines()[0]
up = re.search(r'upperdir=([^,]+)', mt.split()[3]).group(1)
print('  upperdir 里的文件(最后一个容器):' + vm(f"cd {up} && find . -type f | xargs ls -l | awk '{{print $5, $9}}'").replace('\n', ' ; '))
print(f'  big1.bin 在 upperdir 里的大小 = {int(vm(f"stat -c %s {up}/data/big1.bin"))} 字节(原来 {MB << 20},追加了 3 字节);big2.bin 做了 chmod 后 = {int(vm(f"stat -c %s {up}/data/big2.bin"))} 字节')
print('== 三:大文件放在 volume 里(用 cp 先复制进去),再追加 1 字节')
dk('rm', '-f', cid)
dk('volume', 'create', 'bwlab-c20v')
rc, o = dk('run', '--rm', *LAB, '-v', 'bwlab-c20v:/vdata', 'bwlab-c20', 'sh', '-c', f'cp /data/big1.bin /vdata/big1.bin')
rc, o = dk('run', '--rm', *LAB, '-v', 'bwlab-c20v:/vdata', 'bwlab-c20', 'python', '-c', 'import time\nt0=time.perf_counter()\nopen("/vdata/big1.bin","ab").write(b"x")\nprint("volume 里的 big1.bin 第 1 次追加 1 字节: %.1f ms" % ((time.perf_counter()-t0)*1000))')
print('  ' + o.strip())
purge()
