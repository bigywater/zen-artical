import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.protocol.states import KazooState
tee('z11'); R = {}
e = Ensemble('z11', 3, base=7300).start()
print('== 一:连接串里写了 3 个地址:客户端随机挑一个连(kazoo 会打乱顺序)。连续 12 个客户端各连到哪个节点')
cnt = {}
for i in range(12):
    z = client(e.hosts()); peer = z._connection._socket.getpeername()[1] if z._connection._socket else None; cnt[peer] = cnt.get(peer, 0) + 1; z.stop()
print('  连到的客户端端口 → 次数:', dict(sorted(cnt.items()))); R['spread'] = cnt
print()
print('== 二:握手后双方确认的东西:会话 id、协商后的超时(用服务端的 cons 命令看这个连接)')
z = client(e.hosts(), timeout=8); peer = z._connection._socket.getpeername()[1]; node = next(n for n in e.nodes if n.cport == peer)
time.sleep(0.5); line = next(l for l in node.four('cons').splitlines() if f'sid={z.client_id[0]:#x}' in l)
print(f'  客户端会话 id {z.client_id[0]:#x},连在端口 {peer}(服务端 {node.name},{node.mode()})')
print('  该节点的 cons:', re.sub(r'^\s*/', '', line)[:150])
R['session'] = dict(sid=z.client_id[0], peer=peer, cons=line[:150])
print()
print('== 三:连接的服务端被 kill:客户端的状态变化与重连用时(同一个会话继续用)')
states = []; t0 = [time.perf_counter()]
z.add_listener(lambda s: states.append((round((time.perf_counter() - t0[0]) * 1000), str(s))))
z.create('/mine', b'1', ephemeral=True); sid = z.client_id[0]
t0[0] = time.perf_counter(); node.kill()
for _ in range(100):
    if any(s == 'CONNECTED' for _, s in states): break
    time.sleep(0.1)
peer2 = z._connection._socket.getpeername()[1] if z._connection._socket else None
print('  状态变化(相对 kill 的毫秒):', states); print(f'  重连到端口 {peer2}(原来 {peer});会话 id 不变:{z.client_id[0] == sid};临时节点还在:{z.exists("/mine") is not None}')
R['failover'] = dict(states=states, same=z.client_id[0] == sid, peer2=peer2)
print()
print('== 四:连接串里只有一个地址,而这个节点挂了:客户端一直重试,恢复后自动连上')
z.stop(); z.close()
one = client(f'127.0.0.1:{e.nodes[0].cport}' if e.nodes[0].alive() else f'127.0.0.1:{e.nodes[1].cport}')
tgt = e.nodes[0] if e.nodes[0].alive() else e.nodes[1]
st2 = []; one.add_listener(lambda s: st2.append(str(s))); tgt.stop(); time.sleep(3)
print('  单地址客户端在节点停止 3 秒后的状态:', st2, '| 连接状态 connected =', one.connected)
tgt.start(wipe=False); time.sleep(4); print('  节点重新启动后:', st2, '| connected =', one.connected); R['single'] = dict(states=st2, back=one.connected)
one.stop(); e.stop(); save('z11', R)
