import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z27'); R = {}
e = Ensemble('z27', 3, base=7300).start(); ld = e.leader(); fo = e.followers()
print('== 一:三个节点的角色与各自能看到的集群指标(mntr 里 zk_synced_followers / zk_learners 只有 leader 才有)')
for nd in e.nodes:
    m = kv(nd.four('mntr')); print(f'  {nd.name} {nd.srvr().get("mode"):<9} zk_server_state={m.get("zk_server_state")}  zk_followers={m.get("zk_followers")}  zk_synced_followers={m.get("zk_synced_followers")}  zk_learners={m.get("zk_learners")}')
R['roles'] = {nd.name: nd.srvr().get('mode') for nd in e.nodes}
print()
print('== 二:写请求的路径:连在 leader 与连在 follower 上的客户端,同步 create 的延迟(各 300 次,中位数)')
def lat(nd):
    z = client(f'127.0.0.1:{nd.cport}'); z.ensure_path(f'/lat{nd.cport}'); xs = []
    for i in range(300): t0 = time.perf_counter(); z.create(f'/lat{nd.cport}/n{i}', b'x'); xs.append((time.perf_counter() - t0) * 1000)
    z.stop(); return statistics.median(xs)
l_ld, l_fo = lat(ld), lat(fo[0]); print(f'  连 leader:{l_ld:.2f} ms;连 follower:{l_fo:.2f} ms(follower 要多转发一跳,但差别被 fsync 的耗时淹没)'); R['lat'] = dict(leader=l_ld, follower=l_fo)
print()
print('== 三:读请求的路径:连在 follower 上读,leader 收到的包数几乎不变;连在 leader 上读,leader 收到的包增加')
def pk(nd): return int(kv(nd.four('mntr'))['zk_packets_received'])
z = client(f'127.0.0.1:{fo[0].cport}'); z.create('/r', b'x'); p0 = pk(ld); [z.get('/r') for _ in range(2000)]; p1 = pk(ld); z.stop()
z = client(f'127.0.0.1:{ld.cport}'); p2 = pk(ld); [z.get('/r') for _ in range(2000)]; p3 = pk(ld); z.stop()
print(f'  连 follower 读 2000 次:leader 收到包 +{p1 - p0};连 leader 读 2000 次:leader 收到包 +{p3 - p2}'); R['read'] = dict(via_follower=p1 - p0, via_leader=p3 - p2)
print()
print('== 四:写通过 follower 进来,最终每个节点的 zxid 一致(srvr 的 Zxid)')
time.sleep(0.5); print('  各节点 Zxid:', {nd.name: nd.srvr().get('zxid') for nd in e.nodes}); R['zxids'] = {nd.name: nd.srvr().get('zxid') for nd in e.nodes}
e.stop(); save('z27', R)
