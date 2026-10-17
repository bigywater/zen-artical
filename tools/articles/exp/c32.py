import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c32')
img('alpine:3.20', 'python:3.12-alpine')
purge()
print('== 一:--init 给容器里放的是什么(Docker Engine 29.8.2)')
cid = out('run', '-d', '--name', 'bwlab-c32a', *LAB, '--init', 'alpine:3.20', 'sleep', '600')
def ex(c): return dk('exec', cid, 'sh', '-c', c)[1].strip().replace('\n', ' | ')
CMDLINE = "tr '\\0' ' ' < /proc/1/cmdline"
SZ = "ls -l /sbin/docker-init | awk '{print $1, $5}'"
MI = "grep docker-init /proc/self/mountinfo | head -1 | cut -c1-140"
print('  容器里 /proc/1/cmdline:' + ex(CMDLINE))
print('  进程列表:' + ex('ps -o pid,ppid,comm,args'))
print('  /sbin/docker-init --version:' + ex('/sbin/docker-init --version 2>&1 | head -2'))
print('  /sbin/docker-init 文件(权限 大小):' + ex(SZ) + ';不加 --init 的同一个镜像里有它吗?' + dk('run', '--rm', 'alpine:3.20', 'sh', '-c', 'ls /sbin/docker-init 2>&1')[1].strip()[:60])
print('  /sbin/docker-init 来自哪里(mountinfo):' + ex(MI))
print('  PID 1 的内存 VmRSS:' + ex('grep VmRSS /proc/1/status'))
print('  docker inspect 的 HostConfig.Init = ' + out('inspect', '--format', '{{.HostConfig.Init}}', cid))
dk('rm', '-f', cid)
print('== 二:退出码如何穿过 init')
for label, args, opts in (('子进程 exit 3', ['sh', '-c', 'exit 3'], ['--init']), ('子进程 exit 3(不用 --init)', ['sh', '-c', 'exit 3'], []), ('子进程被 SIGKILL(kill -9 $$)', ['sh', '-c', 'kill -9 $$'], ['--init']), ('子进程被 SIGTERM(kill -TERM $$)', ['sh', '-c', 'kill -TERM $$'], ['--init']), ('子进程被 SIGTERM(不用 --init,PID 1 是 sh)', ['sh', '-c', 'kill -TERM $$'], [])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'alpine:3.20', *args)
    print(f'  {label}:docker run 退出码 {rc}')
print('== 三:信号转发:给容器发 SIGUSR1,子进程收到吗')
PYC = 'import signal,time,sys\nsignal.signal(signal.SIGUSR1, lambda n,f: (print("子进程收到 SIGUSR1", flush=True), sys.exit(0)))\nprint("ready", flush=True)\nwhile True: time.sleep(1)'
for label, opts in (('--init', ['--init']), ('不用 --init', [])):
    n = 'bwlab-c32-sig'
    dk('run', '-d', '--name', n, *LAB, *opts, 'python:3.12-alpine', 'python', '-u', '-c', PYC); time.sleep(1)
    dk('kill', '-s', 'USR1', n); time.sleep(1.5)
    s = json.loads(out('inspect', '--format', '{{json .State}}', n))
    print(f'  {label}:日志 {dk("logs", n)[1].strip().replace(chr(10), " | ")};Status={s["Status"]} ExitCode={s["ExitCode"]}')
    dk('rm', '-f', n)
print('== 四:--init 的启动开销:docker run --rm alpine true,各 10 次')
T = {'不用 --init': [], '--init': []}
for i in range(10):
    for k, o in (('不用 --init', []), ('--init', ['--init'])):
        t0 = time.time(); dk('run', '--rm', *LAB, *o, 'alpine:3.20', 'true'); T[k].append(ms(t0))
for k, v in T.items(): print(f'  {k}:中位数 {med(v):.0f} ms,最小 {min(v):.0f},最大 {max(v):.0f}')
purge()
