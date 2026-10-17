import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c39')
img('python:3.12-alpine')
purge()
PROBE = r'''
import ctypes, os, errno, sys
libc = ctypes.CDLL(None, use_errno=True)
N = {"getpid": 172, "add_key": 217, "keyctl": 219, "unshare(CLONE_NEWUSER)": 97, "userfaultfd": 282, "perf_event_open": 241, "bpf": 280, "kcmp": 272, "personality(0xffffffff)": 92, "mount": 40, "ptrace(PTRACE_TRACEME)": 117, "clock_settime": 112, "swapon": 224}
def call(name):
    n = N[name]
    ctypes.set_errno(0)
    if name == "add_key": r = libc.syscall(n, b"user", b"c39", b"hello", 5, -2)
    elif name == "unshare(CLONE_NEWUSER)": r = libc.syscall(n, 0x10000000)
    elif name == "personality(0xffffffff)": r = libc.syscall(n, 0xffffffff)
    elif name == "ptrace(PTRACE_TRACEME)": r = libc.syscall(n, 0, 0, 0, 0)
    elif name == "clock_settime": r = libc.syscall(n, 0, 0)
    elif name == "mount": r = libc.syscall(n, b"none", b"/mnt", b"tmpfs", 0, 0)
    elif name == "swapon": r = libc.syscall(n, b"/nonexistent", 0)
    else: r = libc.syscall(n, 0, 0, 0, 0, 0, 0)
    e = ctypes.get_errno()
    return ("成功(返回 %d)" % r) if r >= 0 else errno.errorcode.get(e, str(e))
st = dict(l.split(":", 1) for l in open("/proc/self/status").read().splitlines() if l.startswith(("Seccomp", "NoNewPrivs")))
print("STATUS", " ".join("%s=%s" % (k, v.strip()) for k, v in st.items()))
for k in N: print("CALL", k, call(k))
'''
d = ctx('c39', {'p.py': PROBE, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY p.py /p.py\nENTRYPOINT ["python","/p.py"]\n'})
rc, o = build(d, 'bwlab-c39', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
print('== 一:守护进程的安全选项与容器里的 seccomp 状态(Docker Engine 29.8.2)')
print('  docker info SecurityOptions:' + out('info', '--format', '{{.SecurityOptions}}'))
res = {}
for label, opts in (('默认', []), ('--security-opt seccomp=unconfined', ['--security-opt', 'seccomp=unconfined'])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c39')
    res[label] = {l.split(' ', 2)[1] if l.startswith('CALL') else 'STATUS': (l.split(' ', 2)[2] if l.startswith('CALL') else l[7:]) for l in o.strip().splitlines()}
    print(f'  {label}:/proc/self/status → {res[label]["STATUS"]}')
print('== 二:同一批系统调用,默认 seccomp 与 unconfined 的结果对比(errno 名)')
print('  系统调用                       默认            unconfined')
for k in res['默认']:
    if k == 'STATUS': continue
    print(f'  {k:30s} {res["默认"][k]:15s} {res["--security-opt seccomp=unconfined"][k]}')
print('== 三:用 --security-opt no-new-privileges 与 --privileged 对比 Seccomp 状态')
for label, opts in (('--privileged', ['--privileged']), ('--security-opt no-new-privileges', ['--security-opt', 'no-new-privileges'])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c39')
    print(f'  {label}:{o.strip().splitlines()[0][7:]}')
purge()
