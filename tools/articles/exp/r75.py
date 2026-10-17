import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r75'); R = {'trials': []}
BASE = 7390
def trial(k):
    cl = Cluster(BASE, 3, 1, name=f'c75_{k}'); time.sleep(1)
    ports = [n.port for n in cl.nodes]
    nd = cluster_nodes(cl.nodes[0].c())
    masters = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
    X = masters[1]; Y = masters[2]
    rep = [x for x in nd if x['master'] == X['id']][0]
    own = slot_owner_map(cl.nodes[0].c())
    def keys_of(port, n=2000):
        out = []; i = 0
        while len(out) < n:
            kk = f'w:{i}'; i += 1
            if own[keyslot(kk)] == port: out.append(kk)
        return out
    kx, ky = keys_of(X['port']), keys_of(Y['port'])
    stop = threading.Event(); res = {'x': dict(ok=[], err=[]), 'y': dict(ok=[], err=[])}
    def writer(name, ks):
        cc = CC([p for p in ports if p != X['port']][:2])
        i = 0
        while not stop.is_set():
            key = ks[i % len(ks)]; t = time.perf_counter()
            try:
                cc.do(key, 'SET', key, i); res[name]['ok'].append((time.perf_counter(), key, i))
            except Exception as e:
                res[name]['err'].append((time.perf_counter(), type(e).__name__))
                time.sleep(0.02)
            i += 1
            time.sleep(0.003)
    ths = [threading.Thread(target=writer, args=('x', kx)), threading.Thread(target=writer, args=('y', ky))]
    [t.start() for t in ths]; time.sleep(1.0)
    surv = [p for p in ports if p != X['port']]
    obs = [C(p) for p in surv[:3]]
    t_kill = time.perf_counter(); cl.nodes[[n.port for n in cl.nodes].index(X['port'])].kill9()
    ev = {}
    while time.perf_counter() - t_kill < 20:
        for c in obs:
            try:
                for x in cluster_nodes(c):
                    if x['id'] == X['id']:
                        if 'fail?' in x['flags'] and 'pfail' not in ev: ev['pfail'] = time.perf_counter() - t_kill
                        if 'fail' in x['flags'] and 'fail' not in ev: ev['fail'] = time.perf_counter() - t_kill
                    if x['id'] == rep['id'] and 'master' in x['flags'] and 'promoted' not in ev: ev['promoted'] = time.perf_counter() - t_kill
            except Exception: pass
        if 'promoted' in ev and time.perf_counter() - t_kill > ev['promoted'] + 1.0: break
        time.sleep(0.01)
    stop.set(); [t.join() for t in ths]
    okx_after = [t for t, k_, i in res['x']['ok'] if t > t_kill]
    errx = [t for t, _ in res['x']['err'] if t > t_kill]
    first_ok_after_err = min((t for t in okx_after if errx and t > max(errx)), default=None) if errx else None
    last_ok_before = max((t for t, k_, i in res['x']['ok'] if t <= t_kill), default=None)
    win = (min(t for t in okx_after if t > (min(errx) if errx else t_kill)) - t_kill) if okx_after else None
    fail_win = (max(errx) - min(errx)) if errx else 0
    # 已确认的写入,新主库上还在吗
    acked = {k_: i for t, k_, i in res['x']['ok']}
    cc = CC([p for p in ports if p != X['port']][:2])
    lost = 0; stale = 0
    for k_, i in acked.items():
        try:
            v = cc.do(k_, 'GET', k_)
        except Exception:
            v = None
        if v is None: lost += 1
        elif int(v) < i: stale += 1
    rec = dict(pfail=ev.get('pfail'), fail=ev.get('fail'), promoted=ev.get('promoted'), gap=(min(t for t in okx_after if errx and t > min(errx)) - t_kill) if okx_after and errx else None,
               errs_x=len(res['x']['err']), errs_y=len(res['y']['err']), ok_x=len(res['x']['ok']), ok_y=len(res['y']['ok']), acked=len(acked), lost=lost, stale=stale)
    # 恢复(最后一次错误之后第一次成功)
    if errx:
        after = [t for t, k_, i in res['x']['ok'] if t > max(errx)]
        rec['recovered'] = (min(after) - t_kill) if after else None
        rec['first_err'] = min(errx) - t_kill
    logs = {p: [l for l in cl.nodes[[n.port for n in cl.nodes].index(p)].log().splitlines() if any(s in l for s in ('Failover', 'failing', 'FAIL message', 'election', 'Failover auth', 'Marking node'))] for p in [rep['port']]}
    rec['replog'] = [l.split('* ', 1)[-1].split('# ', 1)[-1][:150] for l in logs[rep['port']]][:8]
    cl.cleanup(); time.sleep(1.0)
    return rec
for k in range(3):
    r = trial(k); R['trials'].append(r)
    f = lambda v: f'{v*1000:7.0f}' if v is not None else '      -'
    print(f'第 {k+1} 次:kill 后  PFAIL {f(r["pfail"])} ms  FAIL {f(r["fail"])} ms  从库升主 {f(r["promoted"])} ms  写入恢复 {f(r.get("recovered"))} ms   |  X 槽写入错误 {r["errs_x"]} 次  其它槽写入错误 {r["errs_y"]} 次  |  已确认写入 {r["acked"]},新主库上丢失 {r["lost"]},落后(旧值){r["stale"]}')
print()
print('从库的日志(第 3 次):')
for l in R['trials'][-1]['replog']: print('  ', l)
save('r75', R)
