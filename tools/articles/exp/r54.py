import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
import re, datetime
tee('r54'); R = {}
M = Node(7168, name='m54', conf={'repl-diskless-sync': 'no'}).start(); m = M.c()
N = 1000000
for i in range(0, N, 5000): m.pipeline([['SET', f'key:{i+j}', 'v' * 100] for j in range(5000)])
print(f'主库:{m.do("DBSIZE")} 个 key,used_memory {int(info(m, "memory")["used_memory"])/1e6:.0f} MB')
Rp = Node(7169, name='r54', conf={}).start(); r = Rp.c()
stop = threading.Event(); wr = []
def writer():
    c = M.c(); i = 0
    while not stop.is_set():
        c.do('SET', f'live:{i}', i); i += 1; wr.append(time.time()); time.sleep(0.002)
th = threading.Thread(target=writer)
samples = []
t0 = time.time()
r.do('REPLICAOF', '127.0.0.1', 7168)
th.start()
while True:
    ir, ip = info(r, 'replication'), info(r, 'persistence')
    samples.append((time.time() - t0, ir.get('master_link_status'), ir.get('master_sync_in_progress'), int(ir.get('master_sync_read_bytes', 0)), int(ir.get('master_sync_total_bytes', 0)), ip.get('loading'), int(ip.get('loading_loaded_bytes', 0)), int(ip.get('loading_total_bytes', 0))))
    if ir.get('master_link_status') == 'up' and ir.get('master_sync_in_progress') == '0': break
    time.sleep(0.05)
stop.set(); th.join(); time.sleep(0.5)
print()
print('== 一:每 50 ms 采样从库 INFO,看同步的三个阶段')
print(f'{"t(s)":>6} {"link":>5} {"sync中":>6} {"已接收":>12} {"总量":>12} {"loading":>7} {"已加载":>12}')
last = None; rows = []
for s in samples:
    key = (s[2], s[5])
    show = last is None or key != last or s is samples[-1] or int(s[0]*20) % 6 == 0
    if show: print(f'{s[0]:>6.2f} {s[1]:>5} {s[2]:>6} {s[3]:>12} {s[4]:>12} {s[5]:>7} {s[6]:>12}'); rows.append(s)
    last = key
R['samples'] = [list(s) for s in samples]
print()
print('== 二:主库、从库日志里的阶段(时间相对「REPLICAOF」)')
def ts(l):
    m_ = re.search(r'(\d+ \w+ \d{4} \d+:\d+:\d+\.\d+)', l)
    return datetime.datetime.strptime(m_.group(1), '%d %b %Y %H:%M:%S.%f').timestamp() if m_ else None
keys = [('主', M, 'asks for synchronization'), ('主', M, 'Starting BGSAVE for SYNC'), ('主', M, 'Background saving terminated with success'), ('主', M, 'Synchronization with replica'), ('从', Rp, 'MASTER <-> REPLICA sync started'), ('从', Rp, 'receiving'), ('从', Rp, 'Flushing old data'), ('从', Rp, 'Loading DB in memory'), ('从', Rp, 'Done loading RDB'), ('从', Rp, 'Finished with success')]
ev = []
for who, node, pat in keys:
    L = [l for l in node.log().splitlines() if pat in l]
    if L: ev.append((ts(L[-1]), who, L[-1].split('* ', 1)[-1].strip()[:110]))
ev.sort(); base = ev[0][0]
for t, who, l in ev: print(f'+{t-base:6.3f}s [{who}] {l}')
R['events'] = [(t - base, w, l) for t, w, l in ev]
print()
print('== 三:主库磁盘上的 RDB 文件,和同步期间写入的数据')
p = M.dir / 'dump.rdb'; print(f'dump.rdb: {p.stat().st_size/1e6:.1f} MB(主库 dir 里真实存在)'); R['rdb'] = p.stat().st_size
print(f'同步期间主库写入了 {len(wr)} 个 live:* key;同步结束后 dbsize 主/从 = {m.do("DBSIZE")} / {r.do("DBSIZE")}')
mm = m.do('DBSIZE'); rr = r.do('DBSIZE'); R['db'] = [mm, rr, len(wr)]
im = info(m, 'stats'); print('主库 stats: sync_full =', im['sync_full'])
print('主库 client_recent_max_output_buffer =', info(m, 'clients')['client_recent_max_output_buffer'], '字节(同步期间给从库缓冲的增量命令)')
R['maxbuf'] = int(info(m, 'clients')['client_recent_max_output_buffer'])
save('r54', R); cleanup([M, Rp])
