import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r68'); R = {}
cl = Cluster(7300, 3, 1, name='c68'); time.sleep(1)
ANSI = re.compile(r'\x1b\[[0-9;]*m')
print('== 一:redis-cli --cluster create 的输出(节选)')
for l in ANSI.sub('', cl.create_out).splitlines():
    if any(k in l for k in ('Master[', 'Adding replica', 'All 16384')) and 'Waiting' not in l: print('  ', l.strip()[:110])
print()
print('== 二:CLUSTER NODES(节点 ID 缩短为前 8 位)')
c0 = cl.nodes[0].c()
for nd in sorted(cluster_nodes(c0), key=lambda x: x['port']): print(f'  {nd["id"][:8]} {nd["addr"]:<16} {",".join(nd["flags"]):<14} 主={nd["master"][:8] if nd["master"] != "-" else "-":<8} epoch={nd["epoch"]} 槽={" ".join(nd["slots"]) or "-"}')
print()
print('== 三:写入 10 万个 key(用 CRC16 自己算槽位并路由),各主库上有多少 key')
cc = CC([7300])
for i in range(100000): cc.do(f'user:{i}', 'SET', f'user:{i}', i)
print(f'客户端总重定向次数:MOVED {cc.moved}(客户端从一开始就有完整槽位表)')
per = {}
for n in cl.nodes:
    c = n.c()
    if 'master' in c.do('ROLE')[0]: per[n.port] = c.do('DBSIZE')
print('各主库 DBSIZE:', per, ' 合计', sum(per.values()))
R['per'] = per
time.sleep(2)
print()
print('== 四:有数据流过之后,CLUSTER SLOTS 与 CLUSTER SHARDS')
c0 = cl.nodes[0].c()
sl = c0.do('CLUSTER', 'SLOTS')
for start, end, master, *rest in sl:
    print(f'  CLUSTER SLOTS  槽 {start:>5}–{end:<5} 共 {end-start+1} 个  主 {master[0]}:{master[1]}  从 {[x[1] for x in rest]}')
R['slots'] = [(s_, e, m[1], [x[1] for x in r]) for s_, e, m, *r in sl]
for sh_ in sorted(c0.do('CLUSTER', 'SHARDS'), key=lambda d: kv(d)['slots'][0]):
    d = kv(sh_); nodes = [kv(x) for x in d['nodes']]
    print(f'  CLUSTER SHARDS 槽 {d["slots"][0]}–{d["slots"][1]}:' + '  '.join(f'{x["role"]}@{x["port"]}({x["health"]})' for x in nodes))
print()
print('== 五:每个槽里有多少 key(用自己实现的 CRC16 计算,再和 CLUSTER COUNTKEYSINSLOT 抽查对照)')
own = slot_owner_map(c0)
byslot = collections.Counter(keyslot(f'user:{i}') for i in range(100000))
vals = [byslot.get(s, 0) for s in range(16384)]
print(f'平均 {statistics.mean(vals):.2f} 个/槽,最小 {min(vals)},最大 {max(vals)},标准差 {statistics.pstdev(vals):.2f}(若是完全随机的泊松分布,标准差应约 {statistics.mean(vals)**.5:.2f})')
print('抽查 5 个槽(槽号, 自己算的 key 数, CLUSTER COUNTKEYSINSLOT):', [(s, byslot.get(s, 0), cl.nodes[[n.port for n in cl.nodes].index(own[s])].c().do('CLUSTER', 'COUNTKEYSINSLOT', s)) for s in (0, 5460, 5461, 10922, 16383)])
R['slotstat'] = dict(mean=statistics.mean(vals), mn=min(vals), mx=max(vals), sd=statistics.pstdev(vals))
print()
print('== 六:redis-cli --cluster check')
r = subprocess.run(['redis-cli', '--cluster', 'check', '127.0.0.1:7300'], capture_output=True, text=True, timeout=60)
print('\n'.join('  ' + l for l in ANSI.sub('', r.stdout).strip().splitlines() if l.strip())[:1200])
save('r68', R); cl.cleanup()
