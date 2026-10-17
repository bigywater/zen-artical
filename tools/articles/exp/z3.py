import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z3'); R = {}
print('== 一:没有写 tickTime / initLimit / syncLimit 等的最小配置,用四字命令 conf 看生效的值')
n = Node('z3a', 7300, conf={})
n.prepare(); (n.dir / 'zoo.cfg').write_text(f'dataDir={n.dir / "data"}\nclientPort=7300\nclientPortAddress=127.0.0.1\nadmin.enableServer=false\n4lw.commands.whitelist=*\n'); n.start(wipe=False)
c = kv(n.four('conf')); keys = ['tickTime', 'minSessionTimeout', 'maxSessionTimeout', 'maxClientCnxns', 'clientPort']
for k in keys: print(f'  {k:<18} = {c.get(k.lower())}')
R['defaults'] = {k: c.get(k.lower()) for k in keys}
print('  (单机模式的 conf 输出里没有 initLimit / syncLimit,它们只对集群起作用,见第三节的集群 conf)')
n.stop()
print()
print('== 二:会话超时的协商:minSessionTimeout 默认 = 2×tickTime,maxSessionTimeout 默认 = 20×tickTime;客户端请求的值被夹在这个区间内')
n = Node('z3b', 7301, conf={'tickTime': 1000}).start()
c = kv(n.four('conf')); print(f'  tickTime={c["ticktime"]}  minSessionTimeout={c["minsessiontimeout"]}  maxSessionTimeout={c["maxsessiontimeout"]}')
R['negot'] = {}
for req in (500, 2000, 8000, 60000):
    z = client('127.0.0.1:7301', timeout=req / 1000); neg = int(re.search(r'to=(\d+)', n.four('cons')).group(1)); z.stop(); R['negot'][req] = neg; print(f'  客户端请求 {req:>6} ms → 服务端协商为 {neg} ms')
n.stop()
print()
print('== 三:自己设置的值:tickTime=500、minSessionTimeout=1000、maxSessionTimeout=3000、maxClientCnxns=2')
n = Node('z3c', 7302, conf={'tickTime': 500, 'minSessionTimeout': 1000, 'maxSessionTimeout': 3000, 'maxClientCnxns': 2}).start()
c = kv(n.four('conf')); print('  conf →', {k: c.get(k.lower()) for k in ['tickTime', 'minSessionTimeout', 'maxSessionTimeout', 'maxClientCnxns']})
z = client('127.0.0.1:7302', timeout=20); print('  请求 20000 ms → 协商为', re.search(r'to=(\d+)', n.four('cons')).group(1), 'ms'); z.stop()
za = client('127.0.0.1:7302', timeout=5); zb = client('127.0.0.1:7302', timeout=5); res = 'OK'
try: zc = client('127.0.0.1:7302', timeout=5); zc.stop()
except Exception as e: res = type(e).__name__
print('  maxClientCnxns=2:同一个 IP 已有 2 个连接时,第 3 个客户端 →', res)
print('  此时再发四字命令 cons(也是一个连接)→', repr(n.four('cons')[:40]), '(空,也被拒绝)')
za.stop(); zb.stop(); n.stop()
e = Ensemble('z3e', 3, base=7330, conf={'initLimit': 3, 'syncLimit': 2}).start()
c = kv(e.nodes[0].four('conf')); print('  集群节点的 conf →', {k: c.get(k.lower()) for k in ['tickTime', 'initLimit', 'syncLimit']}); R['quorum_conf'] = {k: c.get(k.lower()) for k in ['initLimit', 'syncLimit']}; e.stop()
print()
print('== 四:写错的参数名会怎样:把 tickTime 拼成 tickTim=1000,服务照常启动,用的是默认值')
n = Node('z3d', 7303); n.prepare(); (n.dir / 'zoo.cfg').write_text(f'dataDir={n.dir / "data"}\nclientPort=7303\nclientPortAddress=127.0.0.1\nadmin.enableServer=false\n4lw.commands.whitelist=*\ntickTim=1000\n'); n.start(wipe=False)
c = kv(n.four('conf')); print('  启动成功:', n.mode(), '| conf 里的 tickTime =', c.get('ticktime'), '(没有变成 1000)')
warn = [l for l in n.log().splitlines() if re.search(r'tickTim(?!e)', l)]; print('  日志里提到 tickTim 的行数:', len(warn), warn[:1])
R['typo'] = dict(tick=c.get('ticktime'), warn=len(warn)); n.stop(); save('z3', R)
