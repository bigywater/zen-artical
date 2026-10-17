import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c38')
img('python:3.12-alpine')
purge()
print('== 一:--pids-limit 在 cgroup 里是什么(Docker Engine 29.8.2)')
for label, opts in (('不限制', []), ('--pids-limit 100', ['--pids-limit', '100']), ('--pids-limit -1', ['--pids-limit', '-1'])):
    rc, o = dk('run', '--rm', *LAB, *opts, 'python:3.12-alpine', 'sh', '-c', 'echo pids.max=$(cat /sys/fs/cgroup/pids.max) pids.current=$(cat /sys/fs/cgroup/pids.current)')
    print(f'  {label}:{o.strip()}')
print('== 二:线程也算 pids')
TH = 'import threading,time\nts=[]\ntry:\n    while True:\n        t=threading.Thread(target=time.sleep,args=(3,)); t.start(); ts.append(t)\nexcept RuntimeError as e:\n    print("创建了 %d 个线程后失败:%s" % (len(ts), e))\nprint("pids.current =", open("/sys/fs/cgroup/pids.current").read().strip())'
rc, o = dk('run', '--rm', *LAB, '--pids-limit', '50', 'python:3.12-alpine', 'python', '-c', TH)
print('  --pids-limit 50,不停创建线程:' + o.strip().replace('\n', ' | '))
print('== 三:在 --pids-limit 64 里跑 fork 炸弹(同时限 128m 内存、1 个 CPU)')
n = 'bwlab-c38-bomb'
dk('run', '-d', '--name', n, *LAB, '--pids-limit', '64', '--memory', '128m', '--cpus', '1', 'python:3.12-alpine', 'sh', '-c', 'bomb() { bomb | bomb & }; bomb; sleep 20')
time.sleep(3)
rc, o = dk('exec', n, 'sh', '-c', 'cat /sys/fs/cgroup/pids.current /sys/fs/cgroup/pids.events')
print(f'  3 秒后在容器里 docker exec 读 pids.current / pids.events:退出码 {rc};{o.strip().replace(chr(10), " | ")[:200]}')
print('  docker stats 的 PIDS 列:' + out('stats', '--no-stream', '--format', '{{.PIDs}} 个进程;CPU {{.CPUPerc}};内存 {{.MemUsage}}', n))
t0 = time.time(); rc, o = dk('stop', '-t', '2', n); print(f'  docker stop -t 2:退出码 {rc},用时 {ms(t0):.0f} ms')
print('  虚拟机里的其它容器和 docker 命令是否正常?docker ps 退出码 ' + str(dk('ps', '-q')[0]))
dk('rm', '-f', n)
purge()
