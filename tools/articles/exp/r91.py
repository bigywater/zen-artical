import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r91'); R = {}
def build(master_conf=None, name='s91'):
    nc = {'repl-diskless-sync-delay': '0'}
    M = Node(7910, name=f'{name}m', conf=dict(nc, **(master_conf or {})))
    reps = [Node(7911 + i, name=f'{name}r{i}', conf=dict(nc, replicaof='127.0.0.1 7910')) for i in range(2)]
    M.start(); [r.start() for r in reps]; [wait_link(r.c()) for r in reps]
    px = Proxy(7900, 7910)     # sentinel 通过 7900 访问主库
    sents = [Node(7920 + i, name=f'{name}s{i}', conf={'sentinel monitor': 'mymaster 127.0.0.1 7900 2', 'sentinel down-after-milliseconds': 'mymaster 3000', 'sentinel failover-timeout': 'mymaster 10000', 'sentinel parallel-syncs': 'mymaster 1'}, sentinel=True) for i in range(3)]
    [s.start() for s in sents]
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            if all(int(sentinel_master(s.c())['num-slaves']) == 2 and int(sentinel_master(s.c())['num-other-sentinels']) == 2 for s in sents): break
        except Exception: pass
        time.sleep(0.2)
    return M, reps, px, sents
def run(master_conf, label):
    M, reps, px, sents = build(master_conf)
    stop = threading.Event(); A = []; B = []
    def wa():   # 不知情的客户端:一直写旧主库
        c = C(7910, timeout=2); i = 0
        while not stop.is_set():
            t = time.perf_counter()
            try: r = c.do('SET', f'a:{i}', i, raise_err=False); A.append((t, 'OK' if r == 'OK' else str(r)[:40], i))
            except Exception as e: A.append((t, type(e).__name__, i))
            i += 1; time.sleep(0.01)
    def wb():   # 通过 sentinel 找主库
        i = 0
        while not stop.is_set():
            t = time.perf_counter()
            try:
                a = sents[1].c().do('SENTINEL', 'GET-MASTER-ADDR-BY-NAME', 'mymaster'); port = int(a[1])
                if port == 7900: port = 7910
                r = C(port, timeout=1).do('SET', f'b:{i}', i, raise_err=False); B.append((t, 'OK' if r == 'OK' else str(r)[:40], port))
            except Exception as e: B.append((t, type(e).__name__, None))
            i += 1; time.sleep(0.02)
    ta, tb = threading.Thread(target=wa), threading.Thread(target=wb); ta.start(); tb.start(); time.sleep(1.0)
    t0 = time.perf_counter(); px.cut()
    sw = None
    while time.perf_counter() - t0 < 25:
        try:
            a = sents[1].c().do('SENTINEL', 'GET-MASTER-ADDR-BY-NAME', 'mymaster')
            if int(a[1]) not in (7900, 7910): sw = time.perf_counter() - t0; newp = int(a[1]); break
        except Exception: pass
        time.sleep(0.05)
    time.sleep(6.0)          # 分裂期:两个主库同时存活
    t_heal = time.perf_counter(); px.resume(); heal_from = t_heal - t0
    # 等旧主库被降级
    dem = None
    while time.perf_counter() - t_heal < 40:
        try:
            if info(C(7910), 'replication')['role'] == 'slave': dem = time.perf_counter() - t_heal; break
        except Exception: pass
        time.sleep(0.05)
    time.sleep(4.0); stop.set(); ta.join(); tb.join()
    okA = [x for x in A if x[1] == 'OK']; errA = [x for x in A if x[1] != 'OK']
    okA_split = [x for x in okA if t0 <= x[0] <= t_heal]
    newc = C(newp)
    kept = sum(1 for x in okA if newc.do('EXISTS', f'a:{x[2]}'))
    res = dict(label=label, switch=sw, heal_at=heal_from, demote=dem, okA=len(okA), okA_split=len(okA_split), errA=len(errA), errs=collections.Counter(x[1] for x in errA).most_common(2), kept=kept, lost=len(okA) - kept, okB=sum(1 for x in B if x[1] == 'OK' and x[0] > t0 + (sw or 0)))
    cleanup(sents + [M] + reps); px.cut(); time.sleep(1); return res
print('== 主库通过一个可切断的代理被 sentinel 访问;切断代理 = sentinel 与主库之间「分区」,但客户端 A(不知情)仍直连旧主库并一直写')
r = run(None, '默认'); R['a'] = r
print(f'  sentinel 完成主库切换:{r["switch"]:.1f} s(切断后);分区持续到 {r["heal_at"]:.1f} s 后恢复代理')
print(f'  客户端 A(直连旧主库)整个过程共 {r["okA"]} 次写入被回复 OK,其中「分区期间(切断 → 恢复)」内的 {r["okA_split"]} 次;失败 {r["errA"]} 次 {r["errs"]}')
print(f'  恢复后旧主库被 sentinel 降级为从库,用了 {r["demote"]:.1f} s' if r['demote'] else '  旧主库未被降级')
print(f'  这 {r["okA"]} 条被 OK 的写入,最终在新主库上还在的有 {r["kept"]} 条,丢失 {r["lost"]} 条')
save('r91', R)
