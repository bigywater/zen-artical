import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r53'); R = {}
M = Node(7156, name='m53', conf={'repl-backlog-size': '16kb'}); Rp = Node(7157, name='r53', conf={'replicaof': '127.0.0.1 7160'})
M.start(); px = Proxy(7160, 7156); m = M.c()
print('== 一:没有从库连过时,backlog 还没创建')
def bl(c):
    i = info(c, 'replication'); return {k: i[k] for k in ('repl_backlog_active', 'repl_backlog_size', 'repl_backlog_first_byte_offset', 'repl_backlog_histlen', 'master_repl_offset')}
sh(m, 'CONFIG', 'GET', 'repl-backlog-size'); print(bl(m))
Rp.start(); r = Rp.c(); wait_link(r)
print('从库连上之后:', bl(m))
print()
print('== 二:backlog 里保留的历史(histlen)与 first_byte_offset 随写入量的变化(repl-backlog-size=16 KB)')
R['ring'] = []
for total in (4000, 12000, 16384, 30000, 100000):
    while int(info(m, 'replication')['master_repl_offset']) - 1 < total:
        m.do('SET', 'k', 'x' * 100)
    b = bl(m); print(f'master_repl_offset={b["master_repl_offset"]:>7}  histlen={b["repl_backlog_histlen"]:>6}  first_byte_offset={b["repl_backlog_first_byte_offset"]:>7}')
    R['ring'].append({k: int(v) for k, v in b.items() if k != 'repl_backlog_active'})
print()
print('== 三:从库断开期间主库写入 X 字节,重新连回来:部分重同步还是全量?(backlog=16 KB)')
print(f'{"断开期间写入":>12} {"结果":>10} {"sync_full":>10} {"partial_ok":>11}')
R['gap'] = []
for X in (1000, 8000, 16000, 20000, 24000, 28000, 32000, 40000, 64000, 100000):
    px.cut(); time.sleep(0.4)
    o0 = int(info(m, 'replication')['master_repl_offset']); s0 = repl_stats(m)
    while int(info(m, 'replication')['master_repl_offset']) - o0 < X:
        m.do('SET', 'k', 'x' * 100)
    wrote = int(info(m, 'replication')['master_repl_offset']) - o0
    px.resume(); time.sleep(1.5); wait_link(r); time.sleep(0.2)
    s1 = repl_stats(m)
    lg = M.log(); nf = lg.count('Full resync requested'); npa = lg.count('Partial resynchronization request from')
    res = '部分重同步' if s1['sync_partial_ok'] > s0['sync_partial_ok'] else ('全量同步' if s1['sync_full'] > s0['sync_full'] else '?')
    print(f'{wrote:>12} {res:>10} {s1["sync_full"]-s0["sync_full"]:>10} {s1["sync_partial_ok"]-s0["sync_partial_ok"]:>11}   日志累计:Full resync requested {nf} 次,Partial resynchronization request {npa} 次')
    R['gap'].append(dict(wrote=wrote, res=res))
print()
print('== 四:默认的 backlog 大小')
D = Node(7158, name='d53').start(); sh(D.c(), 'CONFIG', 'GET', 'repl-backlog-size'); sh(D.c(), 'CONFIG', 'GET', 'repl-backlog-ttl')
save('r53', R); px.cut(); cleanup([M, Rp, D])
