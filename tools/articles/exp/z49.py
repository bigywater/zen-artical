import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z49'); R = {}
print('== 一:静态配置的 3 节点集群:每个节点的 conf 里的成员列表一致(server.N 与 myid)')
e = Ensemble('z49', 3, base=7300).start()
for nd in e.nodes:
    c = nd.four('conf'); mem = [l for l in c.splitlines() if l.startswith('server.')]; print(f'  {nd.name} myid={nd.myid}:{mem}')
R['members'] = [l for l in e.nodes[0].four('conf').splitlines() if l.startswith('server.')]
print()
print('== 二:myid 不在 server 列表里:节点启动失败(退出码与日志)')
bad = Node('z49bad', 7330, myid=9, servers=[(1, '127.0.0.1', 7430, 7530, False), (2, '127.0.0.1', 7431, 7531, False), (3, '127.0.0.1', 7432, 7532, False)])
bad.prepare(); bad.start(wait=False); code = bad.p.wait(20); lg = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:150] for l in bad.log().splitlines() if 'ERROR' in l or 'Exception' in l or 'myid' in l.lower()][:4]
print('  退出码:', code); [print('  日志:', l) for l in lg]; R['badid'] = dict(code=code, log=lg)
print()
print('== 三:有一个节点的成员列表比别人少(节点 3 的配置里没有 server.1):它能加入集群吗?')
e.stop()
srv = [(1, '127.0.0.1', 7400, 7500, False), (2, '127.0.0.1', 7401, 7501, False), (3, '127.0.0.1', 7402, 7502, False)]
nodes = [Node('z49m-1', 7300, myid=1, servers=srv), Node('z49m-2', 7301, myid=2, servers=srv), Node('z49m-3', 7302, myid=3, servers=[x for x in srv if x[0] != 1])]
for nd in nodes: nd.start(wait=False)
time.sleep(10); print('  各节点 Mode:', {nd.name: nd.mode() or '不服务' for nd in nodes})
print('  节点 3 的 conf 成员:', [l for l in nodes[2].four('conf').splitlines() if l.startswith('server.')]); R['partial'] = {nd.name: nd.mode() or '不服务' for nd in nodes}
for nd in nodes: nd.stop()
print()
print('== 四:一个不在别人成员列表里的新节点(myid=4,自己的配置里有 4 个成员)启动后:能加入吗?')
e = Ensemble('z49n', 3, base=7340).start()
srv4 = [(i + 1, '127.0.0.1', 7440 + 100 + i, 7540 + 100 + i, False) for i in range(3)] + [(4, '127.0.0.1', 7450, 7550, False)]
srv4 = [(1, '127.0.0.1', 7440, 7540, False), (2, '127.0.0.1', 7441, 7541, False), (3, '127.0.0.1', 7442, 7542, False), (4, '127.0.0.1', 7443, 7543, False)]
n4 = Node('z49n-4', 7343, myid=4, servers=srv4); n4.start(wait=False); time.sleep(8)
print('  原 3 个节点 Mode:', {nd.name: nd.mode() for nd in e.nodes}); print('  新节点(myid=4)Mode:', n4.mode() or '不服务'); print('  原节点 leader 的 zk_synced_followers =', kv(e.leader().four('mntr')).get('zk_synced_followers'))
print('  新节点 conf 里的 server 数:', len([l for l in n4.four('conf').splitlines() if l.startswith('server.')]), '| 原节点 conf 里的 server 数:', len([l for l in e.leader().four('conf').splitlines() if l.startswith('server.')]))
lead = e.leader(); others = [n for n in e.nodes if n is not lead]
for n in others: n.stop()
time.sleep(4); ok = can_write(f'127.0.0.1:{lead.cport},127.0.0.1:{n4.cport}', timeout=6, start_timeout=6)
print('  停掉原来的两个 follower,只剩原 leader + 这个「不在名单里」的新节点(2/3 个名单内成员里只剩 1 个):写入', '成功(它被算进了多数派)' if ok else '失败(它没有被算进多数派)'); print('  此时各节点 Mode:', {nd.name: nd.mode() or '不服务' for nd in [lead, n4]})
R['unknown'] = dict(mode=n4.mode() or '不服务', synced=kv(lead.four('mntr')).get('zk_synced_followers'), write_ok=ok)
n4.stop(); e.stop(); save('z49', R)
