import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
import re, datetime
tee('r58'); R = {}
N = 300000
def load(node):
    c = node.c()
    for i in range(0, N, 5000): c.pipeline([['SET', f'key:{i+j}', f'{random.random():.17f}' * 4] for j in range(5000)])
    return c
d0 = Node(7170, name='d58cfg').start(); dc = d0.c()
print('== 一:默认配置')
for k in ('repl-diskless-sync', 'repl-diskless-sync-delay', 'repl-diskless-sync-max-replicas', 'repl-diskless-load'): sh(dc, 'CONFIG', 'GET', k)
cleanup([d0])
def trial(name, mconf, rconf=None, second=None, port=7171):
    M = Node(port, name=f'm58{name}', conf=dict(mconf)).start(); m = load(M)
    reps = []
    R1 = Node(port + 1, name=f'r58{name}a', conf=dict(rconf or {})).start(); r1 = R1.c()
    t0 = time.time(); r1.do('REPLICAOF', '127.0.0.1', port)
    r2 = None
    if second is not None:
        time.sleep(second); R2 = Node(port + 2, name=f'r58{name}b', conf=dict(rconf or {})).start(); r2 = R2.c(); r2.do('REPLICAOF', '127.0.0.1', port); reps.append(R2)
    wait_link(r1, 60); ta = time.time() - t0
    tb = None
    if r2: wait_link(r2, 60); tb = time.time() - t0
    lg = M.log()
    res = dict(ta=ta, tb=tb, dump=(M.dir / 'dump.rdb').exists(), bgsave=lg.count('Starting BGSAVE for SYNC'), delayed=lg.count('Delay next BGSAVE'), streamed=lg.count('Streamed RDB transfer'), rdir=sorted(p.name for p in R1.dir.iterdir() if p.is_file()), mlog=[l.split('* ', 1)[-1][:120] for l in lg.splitlines() if any(k in l for k in ('BGSAVE', 'Diskless', 'diskless', 'Streamed', 'Delay'))])
    cleanup([M, R1] + reps); return res
print()
print('== 二:磁盘方式(repl-diskless-sync no)vs 无盘方式,延迟 0 / 默认延迟(30 万个 key)')
rows = {}
for name, mc in (('disk', {'repl-diskless-sync': 'no'}), ('dl0', {'repl-diskless-sync': 'yes', 'repl-diskless-sync-delay': '0'}), ('dl5', {'repl-diskless-sync': 'yes'})):
    rows[name] = trial(name, mc, port={'disk': 7171, 'dl0': 7175, 'dl5': 7179}[name])
    x = rows[name]; print(f'{name:>5}: 从库同步完成耗时 {x["ta"]:.2f} s;主库磁盘上有 dump.rdb: {x["dump"]}')
R['rows'] = rows
print()
print('== 三:无盘方式下主库日志(默认 repl-diskless-sync-delay,只有 1 个从库)')
for l in rows['dl5']['mlog']: print('  ', l)
print()
print('== 四:等待窗口内来第二个从库,共用同一次传输(延迟 3 秒,第二个从库晚 1 秒连)')
x = trial('two', {'repl-diskless-sync': 'yes', 'repl-diskless-sync-delay': '3'}, second=1.0, port=7183)
print(f'从库 A 完成 {x["ta"]:.2f} s,从库 B 完成 {x["tb"]:.2f} s;主库 "Starting BGSAVE for SYNC" 次数 = {x["bgsave"]}(两个从库)')
for l in x['mlog']: print('  ', l)
R['two'] = x
print()
print('== 五:从库的无盘加载 repl-diskless-load:磁盘方式(disabled)会在从库目录里落盘一份;swapdb 不会')
for name, rc in (('disabled', {'repl-diskless-load': 'disabled'}), ('swapdb', {'repl-diskless-load': 'swapdb'})):
    x = trial('ld' + name, {'repl-diskless-sync': 'yes', 'repl-diskless-sync-delay': '0'}, rc, port=7187 if name == 'disabled' else 7191)
    print(f'{name:>9}: 同步 {x["ta"]:.2f} s;从库目录里的文件:{x["rdir"]}'); R['ld_' + name] = x
save('r58', R)
