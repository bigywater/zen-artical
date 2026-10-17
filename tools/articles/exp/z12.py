import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z12'); R = {}
e = Ensemble('z12', 3, base=7300).start()
print('== 一:会话 id 的高位字节是创建它的服务端的 myid(分别通过 1 / 2 / 3 号节点建立会话)')
sids = {}
for nd in e.nodes:
    z = client(f'127.0.0.1:{nd.cport}'); sids[nd.myid] = z.client_id[0]; print(f'  连 {nd.myid} 号节点({nd.mode()})→ 会话 id {z.client_id[0]:#018x}'); z.stop()
R['sids'] = {str(k): hex(v) for k, v in sids.items()}
print()
print('== 二:客户端空闲时靠 ping 保持会话:请求超时 6 s,空闲 12 s,数服务端统计的该连接发送包数 sent')
z = client(f'127.0.0.1:{e.nodes[0].cport}', timeout=6); time.sleep(0.5)
def cons():
    l = next(l for l in e.nodes[0].four('cons').splitlines() if f'sid={z.client_id[0]:#x}' in l); return int(re.search(r'sent=(\d+)', l).group(1))
s0 = cons(); time.sleep(12); s1 = cons()
print(f'  空闲 12 秒:连接发送包数 {s0} → {s1}(多了 {s1 - s0} 个,都是 ping 的响应);6 秒超时 ÷ 3 = 2 秒一个 ping → 约 6 个'); R['ping'] = dict(delta=s1 - s0)
print()
print('== 三:dump 命令:leader 与 follower 各自返回什么')
ld = e.leader(); fo = e.followers()[0]
z2 = client(f'127.0.0.1:{fo.cport}', timeout=8); z2.create('/e1', b'', ephemeral=True); time.sleep(0.5)
for who, nd in (('leader', ld), ('follower', fo)):
    d = nd.four('dump').strip().splitlines(); print(f'  {who}({nd.name}):dump 共 {len(d)} 行,前几行:', [l.strip() for l in d[:4]])
R['dump_leader'] = ld.four('dump').strip().splitlines()[:6]
print('  leader 的 dump 里含该会话与临时节点:', hex(z2.client_id[0]) in ld.four('dump'))
print()
print('== 四:会话是「集群级」的:连在 follower 上的会话,在 leader 的 zk_global_sessions 里')
print('  leader 的 zk_global_sessions =', kv(ld.four('mntr')).get('zk_global_sessions'), '| zk_local_sessions =', kv(ld.four('mntr')).get('zk_local_sessions'), '| follower 的 zk_global_sessions =', kv(fo.four('mntr')).get('zk_global_sessions'))
R['gs'] = kv(ld.four('mntr')).get('zk_global_sessions')
z.stop(); z2.stop(); e.stop(); save('z12', R)
