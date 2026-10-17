import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z29'); R = {}
e = Ensemble('z29', 3, base=7300, observers=2).start(); obs = e.nodes[3:]; hosts_v = ','.join(f'127.0.0.1:{n.cport}' for n in e.nodes[:3])
print('== 一:读请求可以由 observer 提供:连在 observer 上读 2000 次,leader 收到的包数几乎不变')
z = client(f'127.0.0.1:{obs[0].cport}'); z.create('/r', b'x'); ld = e.leader(); p0 = int(kv(ld.four('mntr'))['zk_packets_received']); [z.get('/r') for _ in range(2000)]; p1 = int(kv(ld.four('mntr'))['zk_packets_received']); z.stop()
print(f'  leader 的 zk_packets_received 增加 {p1 - p0}'); R['read'] = p1 - p0
print()
print('== 二:同时停掉 2 个 observer:写入不受影响(它们不在多数派里)')
for o in obs: o.stop()
t0 = time.perf_counter(); ok = can_write(hosts_v); print(f'  停掉 2 个 observer 后通过投票节点写入:{"成功" if ok else "失败"}({(time.perf_counter() - t0) * 1000:.0f} ms 内完成)'); R['write_ok'] = ok
print()
print('== 三:observer 离线期间写了 2000 个 znode,重启后追上的时间')
z = client(hosts_v); rs = [z.create_async(f'/gap{i}', b'x') for i in range(2000)]; [r.get() for r in rs]; target = e.leader().srvr().get('zxid')
t0 = time.perf_counter(); obs[0].start(wipe=False, wait=False)
while True:
    try:
        if obs[0].srvr().get('zxid') == e.leader().srvr().get('zxid'): break
    except Exception: pass
    time.sleep(0.05)
    if time.perf_counter() - t0 > 30: break
dt = (time.perf_counter() - t0) * 1000
print(f'  observer 重启后 {dt:.0f} ms 内 Zxid 追上 leader({obs[0].srvr().get("zxid")}),Mode = {obs[0].mode()}'); R['catchup'] = dt
lg = log_lines(e.leader(), ['Sending DIFF', 'Sending TRUNC', 'Sending SNAP']); print('  leader 日志里发给它的同步方式:', [re.sub(r'\S+ ', '', l, 1)[:80] for l in lg[-2:]]); R['sync_kind'] = [l[:100] for l in lg[-2:]]
z.stop(); e.stop(); save('z29', R)
