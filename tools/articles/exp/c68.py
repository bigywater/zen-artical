import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c68')
img('python:3.12-alpine')
purge()
PRINT = 'import time,sys\nfor i in range(1,6):\n    print("tick", i)\n    time.sleep(1)\ntime.sleep(5)'
ERR = 'import time,sys\nfor i in range(1,4):\n    print("err-tick", i, file=sys.stderr)\n    time.sleep(1)\ntime.sleep(4)'
FLUSH = 'import time,sys\nfor i in range(1,6):\n    print("tick", i, flush=True)\n    time.sleep(1)\ntime.sleep(5)'
def watch(label, *run_args, code=PRINT, pyargs=(), maxs=14):
    n = 'bwlab-c68-' + str(abs(hash(label)) % 10**6)
    dk('rm', '-f', n)
    t0 = time.time()
    dk('run', '-d', '--name', n, *LAB, *run_args, 'python:3.12-alpine', 'python', *pyargs, '-c', code)
    first = None; seen3 = None
    while time.time() - t0 < maxs:
        lg = dk('logs', n, raw=True)[1].strip().splitlines()
        if first is None and lg: first = time.time() - t0
        if seen3 is None and time.time() - t0 >= 3: seen3 = len(lg)
        if first is not None and seen3 is not None: break
        time.sleep(0.2)
    total = len(dk('logs', n, raw=True)[1].strip().splitlines())
    print(f'  {label}:第一行出现在 docker logs 里的时间 {("%.1f 秒" % first) if first is not None else "(" + str(maxs) + " 秒内没出现)"};第 3 秒时看到 {seen3} 行')
    dk('rm', '-f', n)
print('== 一:Python 的 print 到管道时是块缓冲(Docker Engine 29.8.2;脚本每秒 print 一行,共 5 行,然后再睡 5 秒才退出)')
watch('默认(不是 TTY)', )
watch('python -u', pyargs=['-u'])
watch('PYTHONUNBUFFERED=1', '-e', 'PYTHONUNBUFFERED=1')
watch('print(…, flush=True)', code=FLUSH)
watch('docker run -t(分配 TTY)', '-t')
print('== 二:stderr 默认不缓冲')
watch('print 到 sys.stderr', code=ERR)
print('== 三:缓冲区多大:不 flush,print 多少数据才会出现')
BIG = 'import time\nn=0\nwhile n < 400:\n    print("x" * 99)\n    n += 1\n    time.sleep(0.02)\ntime.sleep(8)'
n = 'bwlab-c68-big'
dk('run', '-d', '--name', n, *LAB, 'python:3.12-alpine', 'python', '-c', BIG)
t0 = time.time(); first = None
while time.time() - t0 < 10:
    lg = dk('logs', n, raw=True)[1]
    if lg and first is None: first = (time.time() - t0, len(lg.encode()))
    time.sleep(0.02)
    if first: break
print(f'  每 0.02 秒输出一行 100 字节(每秒约 5000 字节),不 flush:第一次在 docker logs 里看到输出是 {first[0]:.1f} 秒时,当时已有 {first[1]} 字节' if first else '  10 秒内没有输出')
dk('rm', '-f', n)
print('== 四:同样的程序用 sh 的 echo(每次 echo 直接 write)')
n = 'bwlab-c68-sh'
t0 = time.time()
dk('run', '-d', '--name', n, *LAB, 'python:3.12-alpine', 'sh', '-c', 'for i in 1 2 3 4 5; do echo tick $i; sleep 1; done; sleep 5')
first = None
while time.time() - t0 < 10:
    if dk('logs', n, raw=True)[1].strip(): first = time.time() - t0; break
    time.sleep(0.2)
print(f'  sh 的 echo:第一行出现在 {first:.1f} 秒' if first else '  10 秒内没有输出')
dk('rm', '-f', n)
purge()
