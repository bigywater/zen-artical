import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z50'); R = {}
def ent(dn): i, q, ee, role, c = dn.dyn[-1]; return f'server.{i}=127.0.0.1:{q}:{ee}:{role};127.0.0.1:{c}'
print('== 一:没有开启 reconfigEnabled(默认关闭)的集群上执行 reconfig')
e0 = Ensemble('z50x', 3, base=7380).start(); o = cli(e0.leader().cport, 'reconfig -remove 3')[0]; print('  reconfig -remove 3 →', o.splitlines()[0] if o else '(无输出)'); R['disabled'] = o.splitlines()[0] if o else ''; e0.stop()
print()
e = DEnsemble('z50', 3, base=7300).start(); ld = e.leader(); z = client(e.hosts()); [z.create(f'/d{i}', b'x') for i in range(50)]
print('== 二:开启动态配置(standaloneEnabled=false、reconfigEnabled=true、dynamicConfigFile)的 3 节点集群:config 命令')
o = cli(ld.cport, 'config')[0]; print('  ' + o.replace('\n', '\n  ')); R['config0'] = o
print()
print('== 三:加入节点:reconfig -add 一个新节点,再启动它')
n4 = e.new_node(4); n4.start(wipe=True, wait=False); t0 = time.perf_counter()
o = cli(ld.cport, f'reconfig -add {ent(n4)}')[0]; print('  reconfig -add →', '\n  ' + o.replace('\n', '\n  ')); R['add'] = o
while time.perf_counter() - t0 < 30 and not (n4.mode() == 'follower'): time.sleep(0.1)
print(f'  新节点 {n4.name} Mode = {n4.mode()}({(time.perf_counter() - t0) * 1000:.0f} ms 后);znode 数 =', kv(n4.four('mntr')).get('zk_znode_count'), '| 其它节点 znode 数 =', kv(ld.four('mntr')).get('zk_znode_count')); R['n4'] = dict(mode=n4.mode(), ms=(time.perf_counter() - t0) * 1000)
print('  现在的成员(config):', cli(ld.cport, 'config -c')[0].replace('\n', ' | ')[:300]); R['members4'] = cli(ld.cport, 'config -c')[0]
print()
print('== 四:移除节点:reconfig -remove 1(被移除的节点自己会怎样)')
victim = e.nodes[0]; ld = e.leader() if e.leader() is not victim else e.nodes[1]
o = cli(e.leader().cport if e.leader() is not victim else e.nodes[1].cport, 'reconfig -remove 1')[0]; print('  reconfig -remove 1 →', '\n  ' + o.replace('\n', '\n  ')); R['remove'] = o
time.sleep(4); print('  被移除的 1 号节点 Mode =', victim.mode() or '不服务', '| 进程还在:', victim.alive()); print('  其它节点:', {n.name: n.mode() for n in e.nodes if n is not victim}); print('  leader 的 zk_synced_followers =', kv(e.leader().four('mntr')).get('zk_synced_followers'), '| 被移除节点自己看到的 config:', cli(victim.cport, 'config')[0].replace(chr(10), ' | ')[:200]); R['victim'] = dict(mode=victim.mode() or '不服务', alive=victim.alive())
z.stop(); e.stop(); save('z50', R)
