import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c31')
img('python:3.12-alpine')
purge()
APP = r'''
import os, subprocess, time, sys
mode = os.environ["MODE"]; N = int(os.environ.get("N", "50"))
def zombies():
    z = 0
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                st = open("/proc/%s/stat" % p).read().rsplit(")", 1)[1].split()[0]
                if st == "Z": z += 1
            except Exception: pass
    return z
kept = []
if mode == "leak":
    for _ in range(N): kept.append(subprocess.Popen(["true"]))
elif mode == "orphan":
    for _ in range(N): subprocess.Popen(["sh", "-c", "true &"]).wait()
elif mode == "forkbomb":
    n = 0
    try:
        while True:
            kept.append(subprocess.Popen(["true"])); n += 1
    except OSError as e:
        print("第 %d 次创建子进程失败:%s" % (n + 1, e.strerror), flush=True)
time.sleep(1)
print("pid=%d mode=%s 僵尸进程数=%d 总进程数=%d" % (os.getpid(), mode, zombies(), len([p for p in os.listdir("/proc") if p.isdigit()])), flush=True)
'''
d = ctx('c31', {'app.py': APP, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY app.py /app.py\nCMD ["python","-u","/app.py"]\n'})
rc, o = build(d, 'bwlab-c31', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def go(label, mode, opts=(), n=50):
    rc, o = dk('run', '--rm', *LAB, *opts, '-e', f'MODE={mode}', '-e', f'N={n}', 'bwlab-c31')
    print(f'  {label}:' + ' | '.join(l.strip() for l in o.strip().splitlines()))
print('== 一:PID 1 是个不会 wait 的程序,创建 50 个马上退出的子进程(Docker Engine 29.8.2)')
go('PID 1 创建 50 个子进程但不 wait', 'leak')
go('同样,加 --init(PID 1 是 docker 自带的 init)', 'leak', ['--init'])
print('== 二:孤儿进程:子进程的父进程先退出,谁来收尸')
go('孤儿进程 50 个,PID 1 是 python 且不 wait', 'orphan')
go('孤儿进程 50 个,加 --init', 'orphan', ['--init'])
print('== 三:僵尸进程占着进程号:--pids-limit 40')
go('--pids-limit 40,不停创建不 wait 的子进程', 'forkbomb', ['--pids-limit', '40'])
go('--pids-limit 40,加 --init(父进程仍是 python,不是 PID 1)', 'forkbomb', ['--init', '--pids-limit', '40'])
print('== 四:docker top / ps 看到的僵尸进程')
n = 'bwlab-c31-top2'
dk('run', '-d', '--name', n, *LAB, '-e', 'MODE=leak', '-e', 'N=3', 'python:3.12-alpine', 'python', '-c', 'import subprocess, time\nk=[subprocess.Popen(["true"]) for _ in range(3)]\ntime.sleep(60)')
time.sleep(1.5)
rc, o = dk('top', n, '-o', 'pid,ppid,stat,comm'); print('  docker top(PID 1 是 python,3 个子进程已退出但没被 wait):')
for l in o.strip().splitlines(): print('    ' + l.strip())
rc, o = dk('exec', n, 'ps', '-o', 'pid,ppid,stat,comm'); print('  docker exec 里用 ps 看(同一个容器):')
for l in o.strip().splitlines(): print('    ' + l.strip())
dk('rm', '-f', n)
purge()
