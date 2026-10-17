import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z67'); R = {}
n = Node('z67', 7300).start(); z = client('127.0.0.1:7300'); z.create('/secret-config', b'db.password=hunter2'); z.create('/svc', b''); z.create('/svc/payments-prod', b'', ephemeral=True); z.get('/secret-config', watch=lambda e: None)
print('== 一:一个没有任何认证的连接,通过四字命令能看到什么(本机 127.0.0.1;白名单 *)——这是为什么要限制它')
for c, what in (('conf', '服务端配置(数据目录路径等)'), ('envi', '运行环境(Java 版本、用户名、工作目录、classpath)'), ('cons', '所有客户端连接(来源地址、会话 id)'), ('dump', '所有会话与它们持有的临时节点路径'), ('wchp', '被监听的路径与监听者')):
    o = four(7300, c).strip().splitlines(); keep = [l.strip() for l in o if any(k in l for k in ('dataDir', 'user.name', 'user.dir', 'java.version', 'os.name', 'sid=', '/svc', '/secret'))][:3]
    print(f'  {c:<5} 暴露:{what}'); [print('        ', l[:110]) for l in keep]; R[c] = keep
print('  注意:四字命令读不到 znode 的数据内容(上面 /secret-config 的 password 没有出现),但路径名、会话、客户端地址、环境信息都能看到。')
print()
print('== 二:四字命令不能改数据:尝试用它创建 znode(没有这样的命令)——只有少数命令会改变服务端的「统计」状态')
before = int(kv(four(7300, 'mntr'))['zk_packets_received']); four(7300, 'srst'); after = int(kv(four(7300, 'mntr'))['zk_packets_received']); print(f'  srst(重置统计)前后 zk_packets_received:{before} → {after}(监控数据被清零)'); R['srst'] = (before, after)
print('  znode 数据没有被任何四字命令改变:/secret-config =', z.get('/secret-config')[0])
z.stop(); n.stop()
print()
print('== 三:收紧白名单:4lw.commands.whitelist=ruok,srvr;被禁止的命令得到什么')
n = Node('z67b', 7301, conf={'4lw.commands.whitelist': 'ruok,srvr'}).start()
for c in ('ruok', 'srvr', 'envi', 'cons', 'dump', 'conf'):
    o = four(7301, c).strip(); print(f'  {c:<5} → {o.splitlines()[0][:100] if o else "(空)"}'); R['wl_' + c] = o.splitlines()[0][:100] if o else ''
print()
print('== 四:默认配置(不写白名单)的节点:只有 srvr 可用')
n.stop(); m = Node('z67c', 7302); m.prepare(); (m.dir / 'zoo.cfg').write_text((m.dir / 'zoo.cfg').read_text().replace('4lw.commands.whitelist=*\n', '')); m.keep_cfg = True; m.start(wipe=False)
ok = [c for c in ('ruok', 'srvr', 'stat', 'envi', 'mntr') if 'not executed because it is not in the whitelist' not in four(7302, c)]; print('  默认可用的命令(上面五个里):', ok); R['default_ok'] = ok
print('  被禁止时的提示:', four(7302, 'envi').strip()[:100]); R['blocked_msg'] = four(7302, 'envi').strip()[:100]
m.stop(); save('z67', R)
