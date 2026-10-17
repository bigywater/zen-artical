import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r84'); R = {}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
NK = 30000
def stat(c):
    d = {}
    for l in c.do('CLUSTER', 'INFO').splitlines():
        if ':' in l:
            k, v = l.strip().split(':', 1); d[k] = v
    return d
def setup(base, name, conf):
    cl = Cluster(base, 3, 1, name=name, conf=conf); time.sleep(1)
    nd = cluster_nodes(cl.nodes[0].c())
    ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
    X = ms[0]; rep = [x for x in nd if x['master'] == X['id']][0]
    cc = CC([m['port'] for m in ms])
    pipes = collections.defaultdict(list)
    for i in range(NK): pipes[cc.slots[keyslot(f'k:{i}')]].append(['SET', f'k:{i}', i])
    for port, cmds in pipes.items():
        c = C(port)
        for j in range(0, len(cmds), 5000): c.pipeline(cmds[j:j + 5000])
    time.sleep(1.2)
    byp = {n.port: n for n in cl.nodes}
    return cl, ms, X, rep, byp
def count_missing(ports, n=NK):
    cc = CC(ports); miss = 0; err = 0
    for i in range(n):
        try:
            v = cc.do(f'k:{i}', 'GET', f'k:{i}')
            if v is None or int(v) != i: miss += 1
        except Exception: err += 1
    return miss, err
def kill_pair(byp, X, rep):
    byp[X['port']].kill9(); byp[rep['port']].kill9()
def watch(obs, secs, cond_key='cluster_state'):
    t0 = time.perf_counter(); first = {}
    while time.perf_counter() - t0 < secs:
        try:
            s = stat(obs)['cluster_state']
            if s not in first: first[s] = time.perf_counter() - t0
        except Exception: pass
        time.sleep(0.02)
    return first
print('== 一:AOF 开启(appendfsync always)、cluster-require-full-coverage yes(默认):同时杀掉一个主库和它的从库')
cl, ms, X, rep, byp = setup(7560, 'c84a', {'appendonly': 'yes', 'appendfsync': 'always'})
others = [m['port'] for m in ms if m['port'] != X['port']]
t0 = time.perf_counter(); kill_pair(byp, X, rep)
obs = C(others[0]); first = watch(obs, 8)
print(f'  被杀:主 {X["port"]} + 从 {rep["port"]};幸存节点上 cluster_state 变化(相对 kill 的秒数):{ {k: round(v, 2) for k, v in first.items()} }')
try: r = C(others[0]).do('SET', 'x', 1, raise_err=False)
except Exception as e: r = e
own = slot_owner_map(obs)
k_ok = next(f'k:{i}' for i in range(NK) if own[keyslot(f'k:{i}')] == others[0])
k_lost = next(f'k:{i}' for i in range(NK) if own[keyslot(f'k:{i}')] == X['port'])
print(f'  在幸存主库 {others[0]} 上写它自己负责的槽里的 key:', C(others[0]).do('SET', k_ok, 'w', raise_err=False), ' 读 key:', C(others[0]).do('GET', k_ok, raise_err=False))
print(f'  向幸存主库请求已丢失分片的 key {k_lost}:', C(others[0]).do('GET', k_lost, raise_err=False))
R['a_first'] = first; R['a_write_ok_shard'] = str(C(others[0]).do('SET', k_ok, 'w', raise_err=False))
# 恢复:先起主库,再起从库
t1 = time.perf_counter(); byp[X['port']].start(rewrite=False)
while time.perf_counter() - t1 < 60:
    try:
        if stat(C(others[0]))['cluster_state'] == 'ok' and all(stat(C(p))['cluster_state'] == 'ok' for p in [X['port']] + others): break
    except Exception: pass
    time.sleep(0.05)
t_ok = time.perf_counter() - t1
print(f'  只重启被杀的主库(AOF 加载):{t_ok:.2f} s 后整个集群 cluster_state = ok')
byp[rep['port']].start(rewrite=False)
miss, err = count_missing([m['port'] for m in ms])
print(f'  数据校验(30000 个 key):读不到/值不对 {miss} 个,出错 {err} 个')
R['a'] = dict(ok=t_ok, miss=miss, err=err)
cl.cleanup(); time.sleep(1)
print()
print('== 二:同样的事故,但没有任何持久化(appendonly no,没有 RDB):主库重启后')
cl, ms, X, rep, byp = setup(7570, 'c84b', {})
others = [m['port'] for m in ms if m['port'] != X['port']]
kill_pair(byp, X, rep); time.sleep(0.5)
t1 = time.perf_counter(); byp[X['port']].start(rewrite=False)
while time.perf_counter() - t1 < 60:
    try:
        if all(stat(C(p))['cluster_state'] == 'ok' for p in [X['port']] + others): break
    except Exception: pass
    time.sleep(0.05)
t_ok = time.perf_counter() - t1
miss, err = count_missing([m['port'] for m in ms])
print(f'  重启主库后 {t_ok:.2f} s cluster_state = ok(nodes.conf 还在,槽位归属恢复)')
print(f'  数据校验(30000 个 key):读不到 {miss} 个({miss/NK*100:.1f}%),出错 {err} 个——集群「恢复正常」,但这一片数据没了')
R['b'] = dict(ok=t_ok, miss=miss, err=err)
cl.cleanup(); time.sleep(1)
print()
print('== 三:cluster-require-full-coverage no:丢了一个分片,其它分片继续服务')
cl, ms, X, rep, byp = setup(7580, 'c84c', {'cluster-require-full-coverage': 'no'})
others = [m['port'] for m in ms if m['port'] != X['port']]
kill_pair(byp, X, rep); obs = C(others[0]); first = watch(obs, 6)
own = slot_owner_map(obs)
k_ok = next(f'k:{i}' for i in range(NK) if own[keyslot(f'k:{i}')] == others[0]); k_lost = next(f'k:{i}' for i in range(NK) if own[keyslot(f'k:{i}')] == X['port'])
print(f'  幸存节点 cluster_state 变化:{ {k: round(v, 2) for k, v in first.items()} };CLUSTER INFO 里 cluster_slots_ok / fail:', stat(obs)['cluster_slots_ok'], '/', stat(obs)['cluster_slots_fail'], '  cluster_state =', stat(obs)['cluster_state'])
print(f'  写幸存分片的 key:', C(others[0]).do('SET', k_ok, 'w', raise_err=False), ' 读:', C(others[0]).do('GET', k_ok, raise_err=False))
tgt = [p for p in others if own[keyslot(k_lost)] == X['port']]
print(f'  请求已丢失分片里的 key {k_lost}:', C(others[0]).do('GET', k_lost, raise_err=False))
R['c'] = dict(state=stat(obs)['cluster_state'], ok=stat(obs)['cluster_slots_ok'], fail=stat(obs)['cluster_slots_fail'], lost=str(C(others[0]).do('GET', k_lost, raise_err=False)))
print()
print('== 四:决定放弃这一片数据:redis-cli --cluster fix 把没人负责的槽位分给存活的节点')
r = subprocess.run(['redis-cli', '--cluster', 'fix', f'127.0.0.1:{others[0]}', '--cluster-fix-with-unreachable-masters'], capture_output=True, text=True, timeout=180, input='yes\n')
out_ = ANSI.sub('', r.stdout)
print('  fix 输出(关键行):'); [print('   ', l[:200]) for l in [l for l in out_.splitlines() if any(k in l for k in ('uncovered', 'Covering', 'Assign', 'assign', 'slots covered', 'OK', 'Fixing', 'error', 'ERR', 'dangerous'))][:10]]
time.sleep(1.5)
print('  之后 cluster_state =', stat(C(others[0]))['cluster_state'], ' cluster_slots_ok =', stat(C(others[0]))['cluster_slots_ok'])
miss, err = count_missing(others, 6000)
print(f'  数据校验(前 6000 个 key):读不到 {miss} 个,出错 {err} 个(那一片数据永久丢失,槽位被分配给了存活的主库)')
R['d'] = dict(state=stat(C(others[0]))['cluster_state'], miss=miss, err=err)
save('r84', R); cl.cleanup()
