import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c37')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
HOG = 'x=[]\nwhile True: x.append(bytearray(5<<20)); x[-1][::4096]=b"x"*len(x[-1][::4096])'
print('== 一:容器内存被打爆时,docker 和内核各留下什么(Docker Engine 29.8.2)')
t1 = int(time.time()) - 1
n = 'bwlab-c37a'
rc, o = dk('run', '--name', n, *LAB, '--memory', '32m', '--memory-swap', '32m', 'python:3.12-alpine', 'python', '-c', HOG)
time.sleep(1); t2 = int(time.time()) + 1
s = json.loads(out('inspect', '--format', '{{json .State}}', n))
print(f'  docker run 退出码 {rc};State.OOMKilled={s["OOMKilled"]} ExitCode={s["ExitCode"]} Error={s["Error"]!r}')
rc, o = dk('events', '--since', str(t1), '--until', str(t2), '--filter', f'container={n}', '--format', '{{.Action}}', timeout=60)
print('  docker events:' + ' → '.join(o.split()))
kl = vm("dmesg | grep -i 'out of memory' | tail -2 | cut -c1-230")
print('  虚拟机内核日志(dmesg)里的相关行:' + kl.replace('\n', ' ; '))
dk('rm', '-f', n)
print('== 二:容器里有多个进程时,杀哪一个')
n = 'bwlab-c37b'
dk('run', '-d', '--name', n, *LAB, '--memory', '48m', '--memory-swap', '48m', 'python:3.12-alpine', 'sh', '-c', f"sleep 600 & python -c '{HOG}'; echo 子进程 python 结束 状态 $?; sleep 20")
time.sleep(5)
s = json.loads(out('inspect', '--format', '{{json .State}}', n))
print(f'  5 秒后容器 Status={s["Status"]} OOMKilled={s["OOMKilled"]};日志:{dk("logs", n)[1].strip().replace(chr(10), " | ")}')
print(f'  容器里还活着的进程:{dk("exec", n, "ps", "-o", "pid,comm")[1].strip().replace(chr(10), " | ")}')
dk('rm', '-f', n)
print('== 三:cgroup 的 memory.events 计数')
n = 'bwlab-c37c'
dk('run', '-d', '--name', n, *LAB, '--memory', '48m', '--memory-swap', '48m', 'python:3.12-alpine', 'sh', '-c', f"sleep 600 & python -c '{HOG}'; sleep 60")
time.sleep(4)
print('  memory.events:' + dk('exec', n, 'sh', '-c', 'cat /sys/fs/cgroup/memory.events | tr "\\n" ";"')[1].strip())
print('  memory.events.local 里 oom_kill:' + dk('exec', n, 'sh', '-c', 'grep oom_kill /sys/fs/cgroup/memory.events.local')[1].strip())
dk('rm', '-f', n)
print('== 四:--oom-kill-disable 在 cgroup v2 的 Docker Desktop 上')
n = 'bwlab-c37d'
rc, o = dk('run', '-d', '--name', n, *LAB, '--memory', '32m', '--memory-swap', '32m', '--oom-kill-disable', 'python:3.12-alpine', 'python', '-c', HOG)
print(f'  docker run -d 退出码 {rc};输出:{" | ".join(l.strip()[:150] for l in o.strip().splitlines())}')
time.sleep(4)
if rc == 0:
    s = json.loads(out('inspect', '--format', '{{json .State}}', n))
    print(f'  4 秒后 Status={s["Status"]} OOMKilled={s["OOMKilled"]};HostConfig.OomKillDisable={out("inspect", "--format", "{{.HostConfig.OomKillDisable}}", n)}')
dk('rm', '-f', n)
purge()
