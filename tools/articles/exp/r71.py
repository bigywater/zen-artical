import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r71'); R = {}
cl = Cluster(7350, 3, 1, name='c71'); time.sleep(1)
ports = [7350, 7351, 7352]
rnd = random.Random(5)
gen = [f'g:{i}' for i in range(30000)]
w = CC([7350])
for k in gen: w.do(k, 'SET', k, 1)
mv = []
i = 0
while len(mv) < 2000:
    k = f'm:{i}'; i += 1
    if keyslot(k) < 1000: mv.append(k)
for k in mv: w.do(k, 'SET', k, 1)
print('== 一:三种客户端策略,同样的 30000 次 GET(集群稳定,3 个主库)')
print(f'{"策略":<32} {"请求数":>7} {"MOVED":>7} {"每请求往返数":>10} {"平均耗时 µs":>11}')
def run(name, cc, keys):
    t0 = time.perf_counter()
    for k in keys: cc.do(k, 'GET', k)
    dt = time.perf_counter() - t0
    row = dict(name=name, req=cc.requests, moved=cc.moved, rt=(cc.requests + cc.moved) / cc.requests, us=dt / cc.requests * 1e6)
    print(f'{name:<32} {row["req"]:>7} {row["moved"]:>7} {row["rt"]:>10.2f} {row["us"]:>11.1f}'); return row
keys = gen[:]; rnd.shuffle(keys)
R['a'] = run('没有槽位表,只会跟 MOVED,不学习', CC([7350], init_map=False, on_moved='none'), keys)
R['b'] = run('没有槽位表,每次 MOVED 学一个槽', CC([7350], init_map=False, on_moved='slot'), keys)
R['c'] = run('启动时 CLUSTER SLOTS 拉全表', CC([7350]), keys)
print()
print('== 二:在线迁移 1000 个槽(0–999)从第一个主库到第二个主库,期间集群一直可用')
nd = cluster_nodes(cl.nodes[0].c()); ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
stale_slot = CC([7350], on_moved='slot'); stale_full = CC([7350], on_moved='full')      # 迁移前拉的全表
t0 = time.time()
r = subprocess.run(['redis-cli', '--cluster', 'reshard', '127.0.0.1:7350', '--cluster-from', ms[0]['id'], '--cluster-to', ms[1]['id'], '--cluster-slots', '1000', '--cluster-yes'], capture_output=True, text=True, timeout=300)
dt = time.time() - t0
owner_now = slot_owner_map(cl.nodes[0].c())
moved_slots = sum(1 for s in range(1000) if owner_now[s] == ms[1]['port'])
print(f'reshard 耗时 {dt:.1f} s;槽 0–999 中现在属于第二个主库的:{moved_slots} 个')
R['reshard'] = dict(sec=dt, moved=moved_slots)
print()
print('== 三:迁移之后,两个手里还是旧槽位表的客户端,各读 20000 次落在这 1000 个槽里的 key')
reads = [mv[i % 2000] for i in range(20000)]
print(f'{"策略":<34} {"请求数":>7} {"MOVED":>7} {"每请求往返数":>10} {"平均耗时 µs":>11}')
R['d'] = run('旧表 + 每次 MOVED 只更新那一个槽', stale_slot, reads)
R['e'] = run('旧表 + 第一次 MOVED 就重新拉全表', stale_full, reads)
print(f'(2000 个 key 覆盖了 {len(set(keyslot(k) for k in mv))} 个不同的槽)')
R['distinct'] = len(set(keyslot(k) for k in mv))
save('r71', R); cl.cleanup()
