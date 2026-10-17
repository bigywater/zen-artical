import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r67'); R = {}
def fill(c, N, off=0, prefix='user'):
    rnd = random.Random(off + 1)
    for i in range(0, N, 5000):
        c.pipeline([['SET', f'{prefix}:{off+i+j}', '%032x%032x' % (rnd.getrandbits(128), rnd.getrandbits(128))] for j in range(5000)])
def wait_done(c, key):
    time.sleep(0.1)
    while info(c, 'persistence')[key] == '1': time.sleep(0.05)
def loadsec(n):
    L = [l for l in n.log().splitlines() if 'DB loaded from' in l]
    return L[-1].split('* ', 1)[-1] if L else ''
cfgs = [('RDB', {'appendonly': 'no'}), ('AOF(RDB base)', {'appendonly': 'yes', 'aof-use-rdb-preamble': 'yes', 'auto-aof-rewrite-percentage': '0'}), ('AOF(纯命令)', {'appendonly': 'yes', 'aof-use-rdb-preamble': 'no', 'auto-aof-rewrite-percentage': '0'})]
sizes = (100000, 500000, 1000000, 2000000)
print('== 一:重启到 loading=0 的耗时(进程启动 → 数据集加载完成),同样的 key(value 是 64 个随机十六进制字符)')
print(f'{"key 数":>9} | ' + ' | '.join(f'{nm:>16}' for nm, _ in cfgs))
R['t'] = {}; R['size'] = {}
port = 7270
for N in sizes:
    row = []
    for nm, conf in cfgs:
        n = Node(port, name=f'p67_{port}', conf=conf).start(); port += 1; c = n.c(); fill(c, N)
        if 'AOF' in nm:
            c.do('BGREWRITEAOF'); wait_done(c, 'aof_rewrite_in_progress'); time.sleep(0.3)
            d = n.dir / 'appendonlydir'; sz = sum(p.stat().st_size for p in d.iterdir())
        else:
            c.do('BGSAVE'); wait_done(c, 'rdb_bgsave_in_progress'); sz = (n.dir / 'dump.rdb').stat().st_size
        n.stop(); t0 = time.time(); n.start(rewrite=False); wait_loaded(n); w = time.time() - t0
        assert n.c().do('DBSIZE') == N
        row.append(w); R['t'].setdefault(nm, {})[N] = w; R['size'].setdefault(nm, {})[N] = sz
        cleanup([n])
    print(f'{N:>9} | ' + ' | '.join(f'{x:>14.2f} s' for x in row))
print()
print('== 二:磁盘上的大小(MB)')
print(f'{"key 数":>9} | ' + ' | '.join(f'{nm:>16}' for nm, _ in cfgs))
for N in sizes: print(f'{N:>9} | ' + ' | '.join(f'{R["size"][nm][N]/1e6:>16.1f}' for nm, _ in cfgs))
print()
print('== 三:AOF(RDB base)+ 未重写的增量:100 万个 key 的 base,之后又追加 X 条 SET,重启要回放多久')
R['incr'] = []
print(f'{"追加命令数":>10} {"incr 大小 MB":>12} {"重启总耗时":>10}')
for X in (0, 200000, 1000000, 3000000):
    n = Node(port, name=f'p67i_{port}', conf={'appendonly': 'yes', 'auto-aof-rewrite-percentage': '0'}).start(); port += 1; c = n.c(); fill(c, 1000000)
    c.do('BGREWRITEAOF'); wait_done(c, 'aof_rewrite_in_progress'); time.sleep(0.3)
    for i in range(0, X, 5000): c.pipeline([['SET', f'add:{i+j}', 'x' * 30] for j in range(5000)])
    time.sleep(1.2)
    incr = [p for p in (n.dir / 'appendonlydir').iterdir() if '.incr.' in p.name][0].stat().st_size
    n.stop(); t0 = time.time(); n.start(rewrite=False); wait_loaded(n); w = time.time() - t0
    print(f'{X:>10} {incr/1e6:>12.1f} {w:>8.2f} s'); R['incr'].append((X, incr, w))
    cleanup([n])
save('r67', R)
