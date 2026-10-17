import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z51'); R = {}
def ent(dn): i, q, ee, role, c = dn.dyn[-1]; return f'server.{i}=127.0.0.1:{q}:{ee}:{role};127.0.0.1:{c}'
e = DEnsemble('z51', 3, base=7300, xmx=256).start(); z = client(e.hosts(), timeout=20)
rs = [z.create_async(f'/d{i}', b'x' * 100) for i in range(20000)]; [r.get() for r in rs]
print('== 一:3 节点集群里有 20000 个 znode;扩容到 5 节点:一条 reconfig 同时加入 4、5 号节点,再启动它们')
n4, n5 = e.new_node(4), e.new_node(5); n4.start(wipe=True, wait=False); n5.start(wipe=True, wait=False); t0 = time.perf_counter()
o = cli(e.leader().cport, f'reconfig -add {ent(n4)},{ent(n5)}')[0]; print('  reconfig -add →', o.splitlines()[-1] if o else '(无输出)', '|', len([l for l in o.splitlines() if l.startswith("server.")]), '个成员')
while time.perf_counter() - t0 < 60 and not (n4.mode() == 'follower' and n5.mode() == 'follower' and n4.srvr().get('zxid') == e.leader().srvr().get('zxid') and n5.srvr().get('zxid') == e.leader().srvr().get('zxid')): time.sleep(0.1)
dt = (time.perf_counter() - t0) * 1000
kinds = [re.search(r'Sending (DIFF|snapshot|TRUNC)', l).group(1) for l in e.leader().log().splitlines() if re.search(r'Sending (DIFF|snapshot|TRUNC)', l)][-2:]
print(f'  两个新节点 {dt:.0f} ms 后追上;各节点 znode 数:', {n.name: kv(n.four("mntr")).get("zk_znode_count") for n in e.nodes}, '| 新节点的同步方式(leader 日志最近两条):', kinds); R['scale_up'] = dict(ms=dt, kinds=kinds, members=len([l for l in o.splitlines() if l.startswith('server.')]))
print()
print('== 二:5 节点后的容错:同时杀掉 2 个节点(含 leader),仍能写;(3 节点时杀 2 个就不能写了)')
ld = e.leader(); v = [n for n in e.nodes if n is not ld][0]; ld.kill(); v.kill(); time.sleep(1)
alive = [n for n in e.nodes if n.alive()]; t1 = time.perf_counter(); ok = False
while time.perf_counter() - t1 < 30:
    if can_write(e.hosts(), timeout=4, start_timeout=3): ok = True; break
print(f'  杀掉 {ld.name}(leader)和 {v.name} 后:{"能写" if ok else "不能写"}({(time.perf_counter() - t1):.1f} s 内恢复),存活 {len(alive)} 个'); R['tol5'] = ok
ld.start(wipe=False, wait=False); v.start(wipe=False, wait=False); time.sleep(6)
print()
print('== 三:缩容回 3 节点:reconfig -remove 4,5(被移除的节点进程不会自动退出)')
leader = e.leader(); o = cli(leader.cport, 'reconfig -remove 4,5')[0]; print('  reconfig -remove 4,5 →', len([l for l in o.splitlines() if l.startswith('server.')]), '个成员:', [l.split('=')[0] for l in o.splitlines() if l.startswith('server.')]); R['scale_down'] = [l.split('=')[0] for l in o.splitlines() if l.startswith('server.')]
n4.stop(); n5.stop(); time.sleep(3)
members = [n for n in e.nodes if n.myid <= 3]; ld = e.leader(); v = [n for n in members if n is not ld][0]; v.kill(); w = [n for n in members if n is not ld and n is not v][0]; w.kill(); time.sleep(5)
ok2 = can_write(f'127.0.0.1:{ld.cport}', timeout=4, start_timeout=5); print(f'  缩容后再杀掉 3 节点里的 2 个:{"还能写" if ok2 else "不能写"}(又回到容忍 1 个故障)'); R['tol3'] = ok2
z.stop(); e.stop(); save('z51', R)
