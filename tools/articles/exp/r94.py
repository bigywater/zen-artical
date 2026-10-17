import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r94'); R = {}
def case(to_write, lag, freeze, label, base):
    M = Node(base, name=f'r94m{base}', conf={'min-replicas-to-write': to_write, 'min-replicas-max-lag': lag, 'repl-diskless-sync-delay': 0}).start()
    reps = [Node(base + 1 + i, name=f'r94r{base+i}', conf={'replicaof': f'127.0.0.1 {base}', 'repl-diskless-sync-delay': 0}).start() for i in range(2)]
    [wait_link(r.c()) for r in reps]
    c = M.c(); time.sleep(1.5)
    res = []; stop = threading.Event()
    def w():
        cc = M.c(); i = 0
        while not stop.is_set():
            t = time.perf_counter(); r = cc.do('SET', 'k', i, raise_err=False); res.append((t, 'OK' if r == 'OK' else str(r)[:60])); i += 1; time.sleep(0.01)
    th = threading.Thread(target=w); th.start(); time.sleep(1.0)
    t0 = time.perf_counter()
    for k in freeze: reps[k].p.send_signal(signal.SIGSTOP)
    good = []
    while time.perf_counter() - t0 < lag + 6:
        good.append((time.perf_counter() - t0, int(info(c, 'replication').get('min_slaves_good_slaves', -1))))
        time.sleep(0.1)
    rej = next((t for t, r in res if t >= t0 and r != 'OK'), None)
    ok_before = sum(1 for t, r in res if t0 <= t < (rej or 1e18) and r == 'OK')
    t1 = time.perf_counter()
    for k in freeze: reps[k].p.send_signal(signal.SIGCONT)
    time.sleep(lag + 3)
    stop.set(); th.join()
    back = next((t for t, r in res if t >= t1 and r == 'OK' and t > (rej or 0)), None)
    msg = next((r for t, r in res if r != 'OK'), None)
    out = dict(label=label, to_write=to_write, lag=lag, first_reject=(rej - t0) if rej else None, ok_before=ok_before, back=(back - t1) if back else None, msg=msg, good=good[::10][:8])
    cleanup([M] + reps); time.sleep(1); return out
cases = [(1, 3, [0, 1], '要求 1 个从库,冻结全部 2 个从库'), (1, 3, [0], '要求 1 个从库,只冻结 1 个从库'), (2, 3, [0], '要求 2 个从库,冻结 1 个从库'), (1, 6, [0, 1], '要求 1 个从库,max-lag 6,冻结全部')]
print(f'{"配置":<34} {"第一条被拒(ms)":>14} {"此前被接受":>9} {"解冻后恢复(ms)":>14}')
R['cases'] = []
for k, (tw, lag, fr, lb) in enumerate(cases):
    r = case(tw, lag, fr, lb, 7940 + k * 10); R['cases'].append(r)
    f = lambda v: f'{v*1000:.0f}' if v is not None else '未拒绝'
    print(f'{lb:<30} {f(r["first_reject"]):>14} {r["ok_before"]:>9} {f(r["back"]):>14}   to-write={tw} max-lag={lag}')
print('被拒时的错误:', R['cases'][0]['msg'])
print('冻结期间 INFO min_slaves_good_slaves 采样(相对冻结的秒, 值)—第 1 组:', [(round(t, 1), g) for t, g in R['cases'][0]['good']])
save('r94', R)
