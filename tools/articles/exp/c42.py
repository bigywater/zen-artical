import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c42')
img('python:3.12-alpine')
purge()
PROBE = r'''
import os, errno, sys, tempfile
def t(path, flags=os.O_WRONLY | os.O_CREAT):
    try:
        fd = os.open(path, flags, 0o600); os.close(fd)
        if flags & os.O_CREAT and not path.endswith(("hosts", "resolv.conf", "hostname")): os.unlink(path)
        return "可写"
    except OSError as e: return errno.errorcode.get(e.errno, str(e.errno))
paths = ["/new-file", "/tmp/x", "/var/tmp/x", "/dev/shm/x", "/run/x", "/etc/hosts", "/etc/resolv.conf", "/etc/hostname", "/data/x", "/usr/local/x"]
for p in paths:
    if p in ("/etc/hosts", "/etc/resolv.conf", "/etc/hostname"): print(p, t(p, os.O_WRONLY))
    else: print(p, t(p))
mp = [l.split()[3].split(",")[0] for l in open("/proc/mounts") if l.split()[1] == "/"]
print("MOUNT_/", mp)
try: tempfile.NamedTemporaryFile().close(); print("tempfile", "可用")
except Exception as e: print("tempfile", type(e).__name__, str(e)[:80])
'''
d = ctx('c42', {'p.py': PROBE, 'Dockerfile': 'FROM python:3.12-alpine\nRUN mkdir /data\nCOPY p.py /p.py\nENTRYPOINT ["python","/p.py"]\n'})
rc, o = build(d, 'bwlab-c42', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def show(label, opts):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c42')
    print(f'  {label}:')
    L = o.strip().splitlines()
    print('    ' + ';  '.join(l.replace(' ', '=', 1) if not l.startswith('MOUNT') else l for l in L))
print('== 一:默认可写层 与 --read-only(Docker Engine 29.8.2)')
show('默认', [])
show('--read-only', ['--read-only'])
print('== 二:--read-only 搭配可写的位置')
show('--read-only --tmpfs /tmp --tmpfs /run', ['--read-only', '--tmpfs', '/tmp', '--tmpfs', '/run'])
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c42v')
show('--read-only -v 命名卷:/data', ['--read-only', '-v', 'bwlab-c42v:/data'])
show('--read-only -v 命名卷:/data:ro', ['--read-only', '-v', 'bwlab-c42v:/data:ro'])
print('== 三:HostConfig 与 docker diff')
n = 'bwlab-c42-d'
dk('run', '-d', '--name', n, *LAB, '--read-only', '--tmpfs', '/tmp', 'python:3.12-alpine', 'sleep', '60')
print(f'  HostConfig.ReadonlyRootfs = {out("inspect", "--format", "{{.HostConfig.ReadonlyRootfs}}", n)}')
dk('exec', n, 'sh', '-c', 'echo x > /tmp/a')
print(f'  容器里往 /tmp(tmpfs)写了文件后,docker diff 输出:{dk("diff", n)[1].strip() or "(空)"}')
rc, o = dk('exec', n, 'sh', '-c', 'echo x > /root/a'); print(f'  往 /root 写 → 退出码 {rc};{o.strip()[:80]}')
dk('rm', '-f', n)
n = 'bwlab-c42-d2'
dk('run', '-d', '--name', n, *LAB, 'python:3.12-alpine', 'sleep', '60')
dk('exec', n, 'sh', '-c', 'echo x > /root/a; echo y > /tmp/b')
print(f'  对比:不带 --read-only 写 /root/a 和 /tmp/b 后,docker diff:{dk("diff", n)[1].strip().replace(chr(10), " ; ")}')
dk('rm', '-f', n)
purge()
