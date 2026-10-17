import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r93'); R = {'trials': []}
def trial(mode, k):
    st = SentinelSet(7840, 2, 7860, 3, quorum=2, down_after=1000, name=f's93{mode}{k}')
    M = st.nodes[0]; acked = []; stop = threading.Event()
    def w():
        c = M.c(timeout=2); i = 0
        while not stop.is_set():
            try:
                if mode == 'sync':
                    c.do('SET', f'k:{i}', i); acked.append(i); i += 1
                else:
                    r = c.pipeline([['SET', f'k:{i + j}', i + j] for j in range(100)]); acked.extend(range(i, i + 100)); i += 100
            except Exception: break
    th = threading.Thread(target=w); th.start(); time.sleep(2.0)
    lag = None
    try: lag = [int(x.split('offset=')[1].split(',')[0]) for x in (info(M.c(), 'replication')['slave0'], info(M.c(), 'replication')['slave1'])]; mo = int(info(M.c(), 'replication')['master_repl_offset'])
    except Exception: pass
    M.kill9(); th.join(); n_acked = len(acked)
    t0 = time.time()
    while time.time() - t0 < 30 and st.addr(0) == ('127.0.0.1', 7840): time.sleep(0.05)
    time.sleep(1.5)
    newp = st.addr(0)[1]; nc = C(newp)
    have = nc.pipeline([['EXISTS', f'k:{i}'] for i in acked]) if acked else []
    lost = sum(1 for x in have if x == 0)
    last_lost = [i for i, x in zip(acked, have) if x == 0]
    rec = dict(mode=mode, acked=n_acked, lost=lost, first_lost=(min(last_lost) if last_lost else None), last_acked=(acked[-1] if acked else None))
    st.cleanup(); time.sleep(1); return rec
print('== kill -9 主库时,正在被持续写入:已回复 OK 的写入在新主库上还有多少?(每种写法 4 次)')
print(f'{"写法":<28} {"次":>2} {"已确认":>8} {"丢失":>6} {"丢失占比":>9}  丢失的是最后几条?')
for mode, lb in (('sync', '同步 SET(一条一条等回复)'), ('pipe', '管道 100 条一批')):
    for k in range(4):
        r = trial(mode, k); R['trials'].append(r)
        tail = (r['last_acked'] - r['first_lost'] + 1) if r['first_lost'] is not None else 0
        print(f'{lb:<24} {k+1:>2} {r["acked"]:>8} {r["lost"]:>6} {r["lost"]/max(r["acked"],1)*100:>8.3f}%  {"是,从第 %d 条起连续到最后(%d 条区间)" % (r["first_lost"], tail) if r["first_lost"] is not None else "无丢失"}')
save('r93', R)
