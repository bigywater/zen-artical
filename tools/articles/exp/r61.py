import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r61'); R = {}
N = 500000
def fill(c):
    rnd = random.Random(1)
    for i in range(0, N, 5000):
        c.pipeline([['SET', f'user:{i+j}', '%032x%032x' % (rnd.getrandbits(128), rnd.getrandbits(128))] for j in range(5000)])
def wait_done(c, key='aof_rewrite_in_progress'):
    time.sleep(0.1)
    while info(c, 'persistence')[key] == '1': time.sleep(0.05)
def loadline(n):
    L = [l for l in n.log().splitlines() if 'loaded from' in l]
    return L[-1].split('* ', 1)[-1] if L else '(无)'
cfgs = [
    ('AOF + RDB preamble(默认)', 7210, {'appendonly': 'yes', 'aof-use-rdb-preamble': 'yes', 'auto-aof-rewrite-percentage': '0'}, 'aof'),
    ('AOF,无 preamble(纯命令)', 7211, {'appendonly': 'yes', 'aof-use-rdb-preamble': 'no', 'auto-aof-rewrite-percentage': '0'}, 'aof'),
    ('只有 RDB', 7212, {'appendonly': 'no'}, 'rdb'),
]
print(f'== 一:同样的 {N} 个 key(value 是 64 个随机十六进制字符),三种持久化格式的文件与重启加载')
print(f'{"配置":<26} {"文件":<28} {"大小(MB)":>9} {"文件头":<26} {"重启加载耗时":>10}')
rows = []
for name, port, conf, kind in cfgs:
    n = Node(port, name=f'p61_{port}', conf=conf).start(); c = n.c(); fill(c)
    if kind == 'aof':
        c.do('BGREWRITEAOF'); wait_done(c); time.sleep(0.3)
        d = n.dir / 'appendonlydir'; base = [p for p in d.iterdir() if '.base.' in p.name][0]
    else:
        c.do('BGSAVE'); wait_done(c, 'rdb_bgsave_in_progress'); base = n.dir / 'dump.rdb'
    raw = base.open('rb').read(40)
    n.stop(); t0 = time.time(); n.start(rewrite=False); wait_loaded(n); c = n.c(); wall = time.time() - t0
    assert c.do('DBSIZE') == N
    ll = loadline(n)
    m = re.search(r'([\d.]+) seconds', ll)
    print(f'{name:<26} {base.name:<28} {base.stat().st_size/1e6:>9.1f} {raw[:26]!r:<26} {wall:>8.2f} s   (日志: {ll})')
    rows.append(dict(name=name, file=base.name, size=base.stat().st_size, head=repr(raw[:26]), wall=wall, log=ll))
    cleanup([n])
R['rows'] = rows
print()
print('== 二:混合持久化 = 「RDB 快照 + 之后的增量命令」。重写后再写 20 万个新 key,重启时先加载 base 再回放 incr')
n = Node(7213, name='p61_mix', conf={'appendonly': 'yes', 'auto-aof-rewrite-percentage': '0'}).start(); c = n.c(); fill(c)
c.do('BGREWRITEAOF'); wait_done(c); time.sleep(0.3)
for i in range(0, 200000, 5000): c.pipeline([['SET', f'new:{i+j}', 'v' * 20] for j in range(5000)])
time.sleep(1.2)
d = n.dir / 'appendonlydir'
for p in sorted(d.iterdir()): print(f'{p.stat().st_size:>10}  {p.name}')
incr = [p for p in d.iterdir() if '.incr.' in p.name][0]
print('incr 文件开头:', incr.open('rb').read(60))
n.stop(); t0 = time.time(); n.start(rewrite=False); wait_loaded(n); c = n.c(); wall = time.time() - t0
print(f'重启后 DBSIZE = {c.do("DBSIZE")}(应为 {N + 200000});加载耗时约 {wall:.2f} s')
for l in n.log().splitlines():
    if 'loaded' in l.lower() or 'Reading' in l or 'AOF' in l and 'Creating' not in l: print(' ', l.split('* ', 1)[-1][:130])
R['mix'] = dict(wall=wall, db=c.do('DBSIZE'), incr=incr.stat().st_size)
save('r61', R); cleanup([n])
