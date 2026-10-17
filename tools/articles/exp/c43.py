import sys, os, re, time, subprocess, json, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c43')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
print('== 一:这个 Docker 有没有开 userns-remap,容器里的 root 是谁(Docker Engine 29.8.2)')
print('  docker info SecurityOptions:' + out('info', '--format', '{{.SecurityOptions}}'))
n = 'bwlab-c43a'
dk('run', '-d', '--name', n, *LAB, 'alpine:3.20', 'sleep', '60')
pid = out('inspect', '--format', '{{.State.Pid}}', n)
print('  容器里 /proc/self/uid_map:' + dk('exec', n, 'cat', '/proc/self/uid_map')[1].strip())
print('  容器里 /proc/self/gid_map:' + dk('exec', n, 'cat', '/proc/self/gid_map')[1].strip())
print(f'  虚拟机里看这个容器的主进程(PID {pid}):' + vm(f"ps -o user=,uid=,pid=,args= -p {pid}"))
print('  虚拟机里 /proc/%s/uid_map:' % pid + vm(f"cat /proc/{pid}/uid_map"))
dk('rm', '-f', n)
print('== 二:手动造一个用户命名空间,看映射规则(uid 1000 的容器进程,seccomp=unconfined 才允许 unshare)')
SCRIPT = r'''
import os, sys, time
print("进入前:uid=%d euid=%d,/proc/self/uid_map=%r" % (os.getuid(), os.geteuid(), open("/proc/self/uid_map").read().strip()))
open("/tmp/f", "w").close()
os.unshare(os.CLONE_NEWUSER)
print("unshare(CLONE_NEWUSER) 之后(还没写映射):uid=%d" % os.getuid())
open("/proc/self/setgroups", "w").write("deny")
open("/proc/self/uid_map", "w").write("0 1000 1")
open("/proc/self/gid_map", "w").write("0 0 1")
print("写入 uid 映射 0 1000 1、gid 映射 0 0 1 之后:uid=%d,uid_map=%r,gid_map=%r" % (os.getuid(), open("/proc/self/uid_map").read().strip(), open("/proc/self/gid_map").read().strip()))
for p in ("/etc/hosts", "/tmp/f", "/etc/passwd"):
    st = os.stat(p); print("  stat %s:显示的属主 uid=%d" % (p, st.st_uid))
try: os.chown("/tmp/f", 0, 0); print("  chown /tmp/f 0 0 成功")
except OSError as e: print("  chown /tmp/f 0 0 失败:", e.strerror)
try: os.chown("/tmp/f", 5, 5); print("  chown /tmp/f 5 5 成功")
except OSError as e: print("  chown /tmp/f 5 5 失败(5 没有映射):", e.strerror)
print("  CapEff:", [l.split()[1] for l in open("/proc/self/status") if l.startswith("CapEff")][0])
print("READY", os.getpid(), flush=True)
time.sleep(6)
'''
d = ctx('c43', {'s.py': SCRIPT, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY s.py /s.py\nENTRYPOINT ["python","-u","/s.py"]\n'})
rc, o = build(d, 'bwlab-c43', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
n = 'bwlab-c43b'
dk('run', '-d', '--name', n, *LAB, '--user', '1000', '--security-opt', 'seccomp=unconfined', 'bwlab-c43')
time.sleep(2.5)
lg = dk('logs', n)[1]
for l in lg.strip().splitlines():
    if l.startswith('READY'): cpid = l.split()[1]
    else: print('  ' + l)
hp = int(out('inspect', '--format', '{{.State.Pid}}', n))
print(f'  虚拟机里看这个进程(容器里的 PID {cpid}):' + vm(f"ps -o user=,uid=,pid=,args= -p {hp}") + '(容器里它看自己是 uid 0)')
dk('rm', '-f', n)
purge()
