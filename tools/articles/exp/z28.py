import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z28'); R = {}
e = Ensemble('z28', 3, base=7300, observers=2).start()
print('== 一:3 个投票节点(participant)+ 2 个 observer:角色(srvr 的 Mode)')
for nd in e.nodes: print(f'  {nd.name} myid {nd.myid} → {nd.srvr().get("mode")}')
print('  配置里 observer 的写法:', [l for l in (e.nodes[3].dir / 'zoo.cfg').read_text().splitlines() if 'observer' in l or l.startswith('peerType')])
ld = e.leader(); m = kv(ld.four('mntr')); print('  leader 的 zk_followers =', m.get('zk_followers'), ' zk_synced_followers =', m.get('zk_synced_followers'), ' zk_synced_observers =', m.get('zk_synced_observers'))
R['roles'] = {nd.name: nd.srvr().get('mode') for nd in e.nodes}; R['leader_m'] = {k: m.get(k) for k in ('zk_followers', 'zk_synced_followers', 'zk_synced_observers')}
print()
print('== 二:observer 不投票、不参与多数派:停掉 2 个投票节点(只剩 1 个投票节点 + 2 个 observer),还能写吗?')
voters = [nd for nd in e.nodes[:3]]; alive_voter = ld
for nd in voters:
    if nd is not ld and nd.alive(): nd.stop()
    if sum(1 for x in voters if not x.alive()) >= 2: break
time.sleep(4)
print('  存活节点的 Mode:', {nd.name: nd.mode() or "(不服务)" for nd in e.nodes if nd.alive()})
ok = can_write(f'127.0.0.1:{e.nodes[3].cport},127.0.0.1:{e.nodes[4].cport}'); print('  通过 observer 写入:', '成功' if ok else '失败(没有多数派)'); R['no_quorum_with_obs'] = ok
print()
print('== 三:恢复一个投票节点(2/3 投票节点 + 2 个 observer)后恢复服务;读请求可以由 observer 提供')
down = [nd for nd in voters if not nd.alive()][0]; down.start(wipe=False, wait=False); e.wait_quorum(); time.sleep(1)
print('  各节点 Mode:', {nd.name: nd.mode() for nd in e.nodes if nd.alive()})
z = client(f'127.0.0.1:{e.nodes[3].cport}'); z.create('/viaobs', b'v'); print('  通过 observer 写入:成功(observer 把写请求转给 leader),读回', z.get('/viaobs')[0]); z.stop()
print()
print('== 四:observer 对写延迟的影响:3 投票节点 vs 3 投票 + 2 observer 的同步写延迟(5 个 JVM 在同一台机器上)(各 300 次,中位数)')
e.stop()
def lat(ens):
    z = client(f'127.0.0.1:{ens.leader().cport}'); xs = []
    for i in range(300): t0 = time.perf_counter(); z.create(f'/l{i}', b'x'); xs.append((time.perf_counter() - t0) * 1000)
    z.stop(); return statistics.median(xs)
A_, B_ = [], []
for rd in range(3):
    e1 = Ensemble('z28a', 3, base=7310).start(); A_.append(lat(e1)); e1.stop()
    e2 = Ensemble('z28b', 3, base=7320, observers=2).start(); B_.append(lat(e2)); e2.stop()
a, b = statistics.median(A_), statistics.median(B_)
print('  各轮(3 轮交替):3 投票 =', [f'{x:.2f}' for x in A_], '| 3 投票 + 2 observer =', [f'{x:.2f}' for x in B_])
print(f'  中位数:3 个投票节点 {a:.2f} ms;3 投票 + 2 observer {b:.2f} ms'); R['lat'] = dict(plain=a, with_obs=b, rounds_a=A_, rounds_b=B_); save('z28', R)
