import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
import re
tee('r59'); R = {}
n = Node(7200, name='p59', conf={'appendonly': 'yes', 'appendfsync': 'everysec', 'auto-aof-rewrite-min-size': '1mb', 'auto-aof-rewrite-percentage': '0'}).start(); c = n.c()
aofdir = n.dir / 'appendonlydir'
def ls():
    return sorted((p.name, p.stat().st_size) for p in aofdir.iterdir())
def manifest():
    return (aofdir / [p.name for p in aofdir.iterdir() if p.name.endswith('.manifest')][0]).read_text().strip()
print('== 一:刚启动、还没写数据:appendonlydir 里有什么')
for f, s in ls(): print(f'{s:>10}  {f}')
print('manifest:'); print(manifest())
print()
print('== 二:对同一个 key INCR 30 万次 + 再写 5 万个不同 key,然后 BGREWRITEAOF 前后的文件')
for i in range(0, 300000, 5000): c.pipeline([['INCR', 'counter'] for _ in range(5000)])
for i in range(0, 50000, 5000): c.pipeline([['SET', f'k{i+j}', 'v' * 20] for j in range(5000)])
time.sleep(1.2)
print('重写前:'); [print(f'{s:>10}  {f}') for f, s in ls()]
print('manifest:'); print(manifest())
before = ls(); pi = info(c, 'persistence')
t0 = time.time(); sh(c, 'BGREWRITEAOF')
seen = []
while True:
    pi = info(c, 'persistence')
    seen.append((round(time.time() - t0, 3), pi['aof_rewrite_in_progress']))
    if pi['aof_rewrite_in_progress'] == '0' and time.time() - t0 > 0.05: break
    time.sleep(0.005)
time.sleep(0.3)
print(f'重写耗时(INFO aof_rewrite_in_progress 从 1 变 0):约 {seen[-1][0]:.2f} s;aof_last_rewrite_time_sec = {pi["aof_last_rewrite_time_sec"]};aof_last_bgrewrite_status = {pi["aof_last_bgrewrite_status"]}')
print('重写后:'); [print(f'{s:>10}  {f}') for f, s in ls()]
print('manifest:'); print(manifest())
R['sizes'] = dict(before=before, after=ls())
print()
print('== 三:重写把 30 万条 INCR 折叠成什么?看 base 文件开头')
base = [p for p in aofdir.iterdir() if '.base.' in p.name][0]
raw = base.read_bytes(); print(f'{base.name}: 前 9 字节 = {raw[:9]!r}')
print('是 RDB 格式(aof-use-rdb-preamble 默认 yes)。DBSIZE =', c.do('DBSIZE'), ' counter =', c.do('GET', 'counter'))
print()
print('== 四:日志里的重写过程')
for l in n.log().splitlines():
    if any(k in l for k in ('rewrit', 'Rewrit', 'AOF', 'BGREWRITEAOF', 'Successfully')): print(' ', l.split('* ', 1)[-1][:130])
print()
print('== 五:自动触发:前面把自动重写关了(percentage 0);现在设 percentage 100(min-size 1mb),持续写入直到日志出现 "Starting automatic rewriting"')
sh(c, 'CONFIG', 'SET', 'auto-aof-rewrite-percentage', 100)
cnt0 = n.log().count('Starting automatic rewriting'); i = 0; t0 = time.time()
sizes = []
while n.log().count('Starting automatic rewriting') == cnt0 and time.time() - t0 < 60:
    c.pipeline([['SET', f'a{i+j}', 'x' * 50] for j in range(2000)]); i += 2000
    pi = info(c, 'persistence'); sizes.append((i, int(pi['aof_base_size']), int(pi['aof_current_size'])))
L = [l for l in n.log().splitlines() if 'Starting automatic rewriting' in l]
print('日志:', L[-1].split('* ', 1)[-1] if L else '(60 秒内未触发)')
b, cur = sizes[-1][1], sizes[-1][2]
print(f'触发时写入了 {i} 个 key;aof_base_size = {b},aof_current_size = {cur}(触发条件:current ≥ base×2 且 ≥ 1 MB)')
R['auto'] = dict(base=b, cur=cur, keys=i)
save('r59', R); cleanup([n])
