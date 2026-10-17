import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r80'); R = {}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
cl = Cluster(7500, 3, 1, name='c80'); time.sleep(1)
nd = cluster_nodes(cl.nodes[0].c())
ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
S = keyslot('{t1}'); own = slot_owner_map(cl.nodes[0].c())
src = [m for m in ms if m['port'] == own[S]][0]; dst = [m for m in ms if m['port'] != src['port']][0]
sc, dc = C(src['port']), C(dst['port'])
K = 2000
for i in range(K): sc.do('SET', f'{{t1}}:{i}', i)
sc.do('SET', '{t1}counter', 0)
print(f'槽 {S}({{t1}} 的槽)在 {src["port"]},要搬到 {dst["port"]};槽里有 {sc.do("CLUSTER", "COUNTKEYSINSLOT", S)} 个 key')
# 后台客户端:每次 INCR 计数器 + 读一个 key
phase = ['前']; stop = threading.Event(); log = collections.defaultdict(lambda: dict(n=0, ask=0, moved=0, tryagain=0, err=0, lat=[]))
acked = [0]
def client():
    cc = CC([7500], on_moved='full'); rnd = random.Random(3)
    ask0 = mv0 = 0
    while not stop.is_set():
        ph = phase[0]; t = time.perf_counter()
        try:
            cc.do('{t1}counter', 'INCR', '{t1}counter'); acked[0] += 1
            k = f'{{t1}}:{rnd.randrange(K)}'; v = cc.do(k, 'GET', k)
            if v is None or int(v) != int(k.split(':')[1]): log[ph]['err'] += 1
            log[ph]['n'] += 1
        except Exception as e:
            log[ph]['err'] += 1
        log[ph]['lat'].append((time.perf_counter() - t) * 1e6)
        log[ph]['ask'] += cc.ask - ask0; log[ph]['moved'] += cc.moved - mv0; ask0, mv0 = cc.ask, cc.moved
        time.sleep(0.002)
th = threading.Thread(target=client); th.start(); time.sleep(1.0)
print()
print('== 一:手工迁移这个槽(与 redis-cli --cluster reshard 做的事一样),后台客户端一直在读写')
phase[0] = '设置状态'
sh(dc, 'CLUSTER', 'SETSLOT', S, 'IMPORTING', src['id']); sh(sc, 'CLUSTER', 'SETSLOT', S, 'MIGRATING', dst['id'])
time.sleep(0.5)
phase[0] = '搬 key 中'
moved_batches = []
while True:
    keys = sc.do('CLUSTER', 'GETKEYSINSLOT', S, 200)
    if not keys: break
    t = time.perf_counter(); r = sc.do('MIGRATE', '127.0.0.1', dst['port'], '', 0, 5000, 'KEYS', *keys)
    moved_batches.append((len(keys), (time.perf_counter() - t) * 1000, sc.do('CLUSTER', 'COUNTKEYSINSLOT', S)))
    print(f'  GETKEYSINSLOT → {len(keys)} 个 key → MIGRATE {r} 用时 {moved_batches[-1][1]:.1f} ms,源上槽里还剩 {moved_batches[-1][2]} 个,目标上 {dc.do("CLUSTER", "COUNTKEYSINSLOT", S)} 个')
    time.sleep(0.3)
phase[0] = '收尾'
time.sleep(0.5)
sh(dc, 'CLUSTER', 'SETSLOT', S, 'NODE', dst['id']); sh(sc, 'CLUSTER', 'SETSLOT', S, 'NODE', dst['id'])
for m in ms:
    if m['port'] not in (src['port'], dst['port']): C(m['port']).do('CLUSTER', 'SETSLOT', S, 'NODE', dst['id'])
phase[0] = '后'
time.sleep(1.5); stop.set(); th.join()
final = int(dc.do('GET', '{t1}counter'))
print()
print(f'  计数器:客户端确认的 INCR 次数 = {acked[0]},槽里最终的 counter = {final}({"一致" if final == acked[0] else "不一致!"})')
R['counter'] = [acked[0], final]
print()
print('== 二:各阶段客户端看到的:操作数、ASK / MOVED 次数、错误、延迟')
print(f'  {"阶段":<8} {"操作数":>7} {"ASK":>6} {"MOVED":>6} {"错误":>5} {"p50 µs":>8} {"p99 µs":>9} {"max µs":>9}')
R['ph'] = {}
for ph in ('前', '设置状态', '搬 key 中', '收尾', '后'):
    d = log[ph]; L = sorted(d['lat']) or [0]
    print(f'  {ph:<8} {d["n"]:>7} {d["ask"]:>6} {d["moved"]:>6} {d["err"]:>5} {statistics.median(L):>8.0f} {L[int(len(L)*.99)]:>9.0f} {L[-1]:>9.0f}')
    R['ph'][ph] = dict(n=d['n'], ask=d['ask'], moved=d['moved'], err=d['err'], p50=statistics.median(L), p99=L[int(len(L) * .99)], mx=L[-1])
R['batches'] = moved_batches
print()
print('== 三:中途放弃(CLUSTER SETSLOT STABLE)会留下什么?换一个槽,搬到一半(400/1000)就停')
S2 = keyslot('{t2}'); own = slot_owner_map(cl.nodes[0].c()); src2 = [m for m in ms if m['port'] == own[S2]][0]; dst2 = [m for m in ms if m['port'] != src2['port']][0]
s2, d2 = C(src2['port']), C(dst2['port'])
for i in range(1000): s2.do('SET', f'{{t2}}:{i}', i)
d2.do('CLUSTER', 'SETSLOT', S2, 'IMPORTING', src2['id']); s2.do('CLUSTER', 'SETSLOT', S2, 'MIGRATING', dst2['id'])
keys = s2.do('CLUSTER', 'GETKEYSINSLOT', S2, 400); s2.do('MIGRATE', '127.0.0.1', dst2['port'], '', 0, 5000, 'KEYS', *keys)
print(f'  迁移到一半:源 {src2["port"]} 槽内 {s2.do("CLUSTER", "COUNTKEYSINSLOT", S2)} 个,目标 {dst2["port"]} 槽内 {d2.do("CLUSTER", "COUNTKEYSINSLOT", S2)} 个')
s2.do('CLUSTER', 'SETSLOT', S2, 'STABLE'); d2.do('CLUSTER', 'SETSLOT', S2, 'STABLE')
def miss():
    cc = CC([7500]); return sum(1 for i in range(1000) if cc.do(f'{{t2}}:{i}', 'GET', f'{{t2}}:{i}') is None)
m0 = miss()
print(f'  两端都 STABLE(放弃)之后,槽仍归 {src2["port"]}:通过集群读 1000 个 key,读不到的有 {m0} 个')
print(f'  在目标节点 {dst2["port"]} 上看:DBSIZE = {d2.do("DBSIZE")};KEYS * 返回 {len(d2.do("KEYS", "*"))} 个;SCAN 返回 {len(d2.do("SCAN", 0, "COUNT", 1000)[1])} 个;CLUSTER COUNTKEYSINSLOT {S2} = {d2.do("CLUSTER", "COUNTKEYSINSLOT", S2)};EXISTS {keys[0]} → {d2.do("EXISTS", keys[0], raise_err=False)}')
R['abort'] = dict(moved=len(keys), missing=m0, dbsize=d2.do('DBSIZE'), keys_len=len(d2.do('KEYS', '*')), scan=len(d2.do('SCAN', 0, 'COUNT', 1000)[1]), cnt=d2.do('CLUSTER', 'COUNTKEYSINSLOT', S2))
print()
print('== 四:redis-cli --cluster check / fix 能发现并修复吗?')
r = subprocess.run(['redis-cli', '--cluster', 'check', '127.0.0.1:7500'], capture_output=True, text=True, timeout=60)
print('  check 的输出(关键行):'); [print('   ', l) for l in ANSI.sub('', r.stdout).splitlines() if l.startswith('[') or '>>>' in l or 'keys in' in l]
r = subprocess.run(['redis-cli', '--cluster', 'fix', '127.0.0.1:7500', '--cluster-search-multiple-owners'], capture_output=True, text=True, timeout=120, input='yes\n')
print('  fix --cluster-search-multiple-owners 的输出(关键行):'); [print('   ', l) for l in ANSI.sub('', r.stdout).splitlines() if l.startswith('[') or '>>>' in l or 'keys in' in l]
m1 = miss(); print(f'  fix 之后:读不到的 key 仍有 {m1} 个')
R['fix'] = dict(missing=m1)
print()
print('== 五:手工恢复:重新把目标节点设成 IMPORTING(它的 400 个 key 又变得可见),然后把迁移做完')
sh(d2, 'CLUSTER', 'SETSLOT', S2, 'IMPORTING', src2['id'])
print(f'  再次 IMPORTING 后:目标 CLUSTER COUNTKEYSINSLOT = {d2.do("CLUSTER", "COUNTKEYSINSLOT", S2)},KEYS * = {len(d2.do("KEYS", "*"))},EXISTS {keys[0]}(先 ASKING)→ {(d2.do("ASKING"), d2.do("EXISTS", keys[0], raise_err=False))[1]}')
sh(s2, 'CLUSTER', 'SETSLOT', S2, 'MIGRATING', dst2['id'])
left = s2.do('CLUSTER', 'GETKEYSINSLOT', S2, 1000); print(f'  源上还剩 {len(left)} 个,MIGRATE →', s2.do('MIGRATE', '127.0.0.1', dst2['port'], '', 0, 5000, 'REPLACE', 'KEYS', *left))
for m in ms:
    C(m['port']).do('CLUSTER', 'SETSLOT', S2, 'NODE', dst2['id'])
time.sleep(1)
m2 = miss(); print(f'  SETSLOT NODE 之后:读不到的 key {m2} 个;槽 {S2} 归属 {slot_owner_map(cl.nodes[0].c())[S2]}(目标 {dst2["port"]});各主库 DBSIZE', {n.port: n.c().do('DBSIZE') for n in cl.nodes if 'master' in n.c().do('ROLE')[0]})
R['recover'] = dict(missing=m2)
save('r80', R); cl.cleanup()
