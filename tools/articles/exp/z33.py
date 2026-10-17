import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z33'); R = {}
e = Ensemble('z33', 5, base=7300).start()
def table(title):
    print(f'  [{title}]'); print(f'  {"节点":<7} {"端口":<5} {"角色":<9} {"zxid":<14} {"连接数":>5} {"outstanding":>11} {"synced_followers":>16} {"avg延迟ms":>9}')
    rows = []
    for nd in e.nodes:
        if not nd.alive(): print(f'  {nd.name:<7} {nd.cport:<5} {"已停止":<9}'); rows.append((nd.name, 'down')); continue
        s = nd.srvr(); m = kv(nd.four('mntr'))
        if not s.get('mode'): print(f'  {nd.name:<7} {nd.cport:<5} {"不服务":<9}'); rows.append((nd.name, 'notserving')); continue
        print(f'  {nd.name:<7} {nd.cport:<5} {s["mode"]:<9} {s["zxid"]:<14} {m.get("zk_num_alive_connections", "-"):>5} {m.get("zk_outstanding_requests", "-"):>11} {m.get("zk_synced_followers", "-"):>16} {m.get("zk_avg_latency", "-"):>9}'); rows.append((nd.name, s['mode'], s['zxid']))
    return rows
z = client(e.hosts()); [z.create(f'/n{i}', b'x') for i in range(100)]
print('== 一:5 节点健康时的检查表(每个节点各自的 srvr / mntr)')
R['healthy'] = table('健康')
print()
print('== 二:杀掉一个 follower 后:leader 的 synced_followers 减少,其它节点正常')
ld = e.leader(); f = e.followers()[0]; f.kill(); time.sleep(5); R['one_down'] = table('1 个 follower 停止')
print()
print('== 三:再杀掉 leader:选举期间的表')
ld.kill(); time.sleep(0.2); R['no_leader'] = table('leader 刚被杀')
time.sleep(6); print(); R['recovered'] = table('选举完成后')
print()
print('== 四:用 ruok / srvr 是否足以判断健康?对比 ruok 与 Mode(不服务的节点 ruok 仍回 imok)')
e2 = Ensemble('z33b', 3, base=7320); [nd.prepare() for nd in e2.nodes]; e2.nodes[0].start(wait=False); time.sleep(3)
print('  只起 1/3:ruok =', four(7320, 'ruok').strip(), '| srvr 首行 =', four(7320, 'srvr').strip().splitlines()[0][:70]); R['ruok'] = four(7320, 'ruok').strip()
e2.nodes[0].stop(); z.stop(); e.stop(); save('z33', R)
