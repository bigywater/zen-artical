import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r82'); R = {}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
cl = Cluster(7540, 3, 1, name='c82', conf={'enable-debug-command': 'yes'}); time.sleep(1)
nd = cluster_nodes(cl.nodes[0].c()); ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
cc = CC([7540])
pipes = collections.defaultdict(list)
for i in range(300000): pipes[cc.slots[keyslot(f'n:{i}')]].append(['SET', f'n:{i}', 'v' * 20])
for port, cmds in pipes.items():
    c = C(port)
    for j in range(0, len(cmds), 5000): c.pipeline(cmds[j:j + 5000])
big = 'bigkey:1'; owner = cc.slots[keyslot(big)]
C(owner).do('SET', big, 'x' * (200 * 1024 * 1024))
time.sleep(1)
def mem(p): return int(info(C(p), 'memory')['used_memory'])
print(f'== 一:3 个主库槽位数接近相等,数据库大小也接近相等——但内存不是。大 key {big}(200 MB)在槽 {keyslot(big)},主库 {owner}')
print(f'{"主库":>6} {"槽位数":>7} {"DBSIZE":>8} {"used_memory":>13}')
rows = []
for m in ms:
    c = C(m['port']); sl = sum(int(x.split('-')[-1]) - int(x.split('-')[0]) + 1 for x in m['slots'])
    r = dict(port=m['port'], slots=sl, dbsize=c.do('DBSIZE'), mem=mem(m['port'])); rows.append(r)
    print(f'{m["port"]:>6} {sl:>7} {r["dbsize"]:>8} {r["mem"]/1e6:>10.1f} MB' + ('   ← 大 key 所在' if m['port'] == owner else ''))
R['rows'] = rows
print()
print('== 二:redis-cli --cluster rebalance 认为需要调整吗?')
r = subprocess.run(['redis-cli', '--cluster', 'rebalance', '127.0.0.1:7540'], capture_output=True, text=True, timeout=120)
print('  ' + '\n  '.join(l for l in ANSI.sub('', r.stdout).splitlines() if l.strip() and '>>>' in l or 'balanced' in l.lower() or 'No rebalancing' in l))
R['rebalance'] = ANSI.sub('', r.stdout).strip().splitlines()[-1]
print()
print('== 三:迁移含大 key 的那个槽(手工 IMPORTING / MIGRATING / MIGRATE / SETSLOT NODE),量源节点上另一个连接的 PING 停顿')
S = keyslot(big); src = [m for m in ms if m['port'] == owner][0]; dst = [m for m in ms if m['port'] != owner][0]
sc, dc = C(src['port']), C(dst['port'])
stop = threading.Event(); out = []
def probe():
    c = C(src['port'])
    while not stop.is_set():
        t = time.perf_counter(); c.do('PING'); out.append((t, (time.perf_counter() - t) * 1000)); time.sleep(0.001)
th = threading.Thread(target=probe); th.start(); time.sleep(0.3)
dc.do('CLUSTER', 'SETSLOT', S, 'IMPORTING', src['id']); sc.do('CLUSTER', 'SETSLOT', S, 'MIGRATING', dst['id'])
keys = sc.do('CLUSTER', 'GETKEYSINSLOT', S, 100)
t0 = time.perf_counter(); r = sc.do('MIGRATE', '127.0.0.1', dst['port'], '', 0, 60000, 'KEYS', *keys); dt = (time.perf_counter() - t0) * 1000
for m in ms: C(m['port']).do('CLUSTER', 'SETSLOT', S, 'NODE', dst['id'])
time.sleep(0.3); stop.set(); th.join()
mx = max(d for t, d in out if t0 - 0.05 <= t <= t0 + dt / 1000 + 0.05)
print(f'  槽内 {len(keys)} 个 key(含大 key)MIGRATE → {r},耗时 {dt:.0f} ms;源节点 {src["port"]} 上另一个连接的 PING 最大停顿 {mx:.0f} ms(平时约 0.03 ms)')
R['migrate'] = dict(ms=dt, stall=mx)
print()
print('== 四:阻塞超过 cluster-node-timeout(3000 ms)会怎样:用 DEBUG SLEEP 5 模拟一次 5 秒的阻塞(比如删除/迁移超大 key)')
big2 = [m for m in ms if m['port'] != dst['port']][0]
victim = [m for m in ms if m['port'] not in (dst['port'],)][0]
rep = [x for x in nd if x['master'] == victim['id']][0]
obs = C(dst['port']); t0 = time.perf_counter()
th = threading.Thread(target=lambda: C(victim['port'], timeout=30).do('DEBUG', 'SLEEP', 5, raise_err=False)); th.start()
ev = {}
while time.perf_counter() - t0 < 14:
    for x in cluster_nodes(obs):
        if x['id'] == victim['id']:
            if 'fail?' in x['flags'] and 'pfail' not in ev: ev['pfail'] = time.perf_counter() - t0
            if 'fail' in x['flags'] and 'fail' not in ev: ev['fail'] = time.perf_counter() - t0
        if x['id'] == rep['id'] and 'master' in x['flags'] and 'promoted' not in ev: ev['promoted'] = time.perf_counter() - t0
    time.sleep(0.02)
th.join()
time.sleep(1)
roles = {x['port']: ','.join(f for f in x['flags'] if f in ('master', 'slave', 'fail', 'fail?')) for x in cluster_nodes(obs)}
f = lambda v: f'{v*1000:.0f} ms' if v is not None else '未发生'
print(f'  主库 {victim["port"]} 被阻塞 5 秒:其它节点 PFAIL {f(ev.get("pfail"))},FAIL {f(ev.get("fail"))},它的从库 {rep["port"]} 升主 {f(ev.get("promoted"))}')
print('  阻塞结束后各节点角色:', roles)
R['sleep'] = {k: v for k, v in ev.items()}
save('r82', R); cl.cleanup()
