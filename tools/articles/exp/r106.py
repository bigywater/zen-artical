import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r106'); R = {}
def nthreads(pid):
    r = subprocess.run(['ps', '-M', '-p', str(pid)], capture_output=True, text=True).stdout.strip().splitlines()
    return max(0, len(r) - 2)   # 去掉表头和进程行
def cpu(pid):
    r = subprocess.run(['ps', '-o', 'time=', '-p', str(pid)], capture_output=True, text=True).stdout.strip(); return r
print('== 一:Redis 进程有几个线程?(macOS 用 ps -M 计数;进程行本身不计)')
rows = []
for name, conf in (('默认', {}), ('io-threads 4', {'io-threads': 4}), ('io-threads 4 + appendonly yes', {'io-threads': 4, 'appendonly': 'yes'})):
    n = Node(8100, name='r106', conf=dict(conf)).start(); time.sleep(0.5)
    c = n.c(); c.do('SET', 'k', 1)
    t = nthreads(n.p.pid); rows.append((name, t)); print(f'  {name:<28} 线程数 = {t + 1}(含主线程)')
    cleanup([n]); time.sleep(0.5)
R['threads'] = rows
print()
print('== 二:用 redis-benchmark(C 程序,不受 GIL 限制)加压:SET,管道 16,50 万条;客户端连接数 1 / 4 / 16 / 64')
n = Node(8100, name='r106b').start()
def bench(cc, extra=()):
    r = subprocess.run(['redis-benchmark', '-p', '8100', '-q', '-n', '500000', '-t', 'set', '-c', str(cc), '-P', '16'] + list(extra), capture_output=True, text=True, timeout=120)
    m = re.search(r'([\d.]+) requests per second', r.stdout.replace('\r', '\n')); return float(m.group(1))
print(f'{"连接数":>8} {"吞吐(条/秒)":>14}')
R['scale'] = []
for k in (1, 4, 16, 64):
    v = statistics.median(bench(k) for _ in range(2)); R['scale'].append((k, v)); print(f'{k:>8} {v:>14.0f}')
print()
print('== 三:压测期间 Redis 主进程的 CPU 占用(top 采样)——单个线程跑满一个核')
p = subprocess.Popen(['redis-benchmark', '-p', '8100', '-q', '-n', '30000000', '-t', 'set', '-c', '32', '-P', '16'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
t = subprocess.run(['top', '-l', '4', '-s', '1', '-pid', str(n.p.pid), '-stats', 'pid,cpu,threads'], capture_output=True, text=True, timeout=30).stdout
L = [l.split() for l in t.splitlines() if l.strip().startswith(str(n.p.pid))]
p.kill(); p.wait()
print('  top 三次采样(pid  %cpu  线程数):', [' '.join(x) for x in L]); R['cpu'] = [x for x in L]
save('r106', R); cleanup([n])
