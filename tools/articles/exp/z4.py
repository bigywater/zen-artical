import sys, os, time, json, re, socket; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z4'); R = {}
KEY = [('Reading configuration', '读配置文件'), ('running in standalone mode', '没有 server.N → 单机模式'), ('Starting server', 'ZooKeeperServerMain 启动'), ('Created server with tickTime', '创建服务实例(带会话超时范围)'), ('binding to port', '绑定客户端端口'), ('Reading snapshot', '读快照'), ('Snapshot loaded', '快照加载完成'), ('Snapshot taken', '启动时写一份新快照'), ('PrepRequestProcessor', '请求处理链第一环启动'), ('ContainerManager', '容器节点清理线程启动')]
def milestones(log):
    lines = log.splitlines(); t = lambda l: sum(float(x) * m for x, m in zip(re.match(r'(\d+):(\d+):(\d+\.\d+)', l).groups(), (3600, 60, 1)))
    t0 = t(lines[0]); seen = set(); out = []
    for l in lines:
        for k, d in KEY:
            if k in l and k not in seen:
                seen.add(k); out.append((round((t(l) - t0) * 1000), d, re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:90])); break
    return out
print('== 一:第一次启动(空数据目录)的日志里程碑(相对第一行日志的毫秒数)')
n = Node('z4', 7300, conf={'snapCount': 1000}); t0 = time.perf_counter(); n.start(); ready1 = (time.perf_counter() - t0) * 1000
ms = milestones(n.log())
for t, d, m in ms: print(f'  +{t:>4} ms  {d:<26} {m}')
print(f'  从启动进程到 srvr 能响应(含 JVM 启动、我的轮询间隔):{ready1:.0f} ms'); R['first'] = dict(ms=ms, ready=ready1)
print()
print('== 二:写入 6000 个 znode 后重启:读快照 + 回放事务日志')
z = client('127.0.0.1:7300'); rs = [z.create_async(f'/n{i}', b'x' * 100) for i in range(6000)]; [r.get() for r in rs]; z.stop()
zx = n.srvr().get('zxid'); n.stop(); (n.dir / 'zk.log').rename(n.dir / 'zk1.log')
t0 = time.perf_counter(); n.start(wipe=False); ready2 = (time.perf_counter() - t0) * 1000
log = n.log(); ms2 = milestones(log)
for t, d, m in ms2: print(f'  +{t:>4} ms  {d:<26} {m}')
print(f'  重启前最大 zxid {zx};重启到能响应:{ready2:.0f} ms(第一次 {ready1:.0f} ms)'); R['second'] = dict(ms=ms2, ready=ready2, zxid=zx)
print('  重启后 znode 数:', kv(n.four('mntr')).get('zk_znode_count'))
print('  数据目录(version-2)里的文件:', sorted(p.name for p in (n.dir / 'data' / 'version-2').iterdir())); R['files'] = sorted(p.name for p in (n.dir / 'data' / 'version-2').iterdir())
n.stop()
print()
print('== 三:端口被占用时启动:进程退出,日志说什么')
sock = socket.socket(); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); sock.bind(('127.0.0.1', 7301)); sock.listen(1)
m = Node('z4b', 7301); m.prepare()
try:
    m.start(wait=False); code = m.p.wait(20); print('  进程退出码:', code)
except Exception as e: print('  进程没有退出:', type(e).__name__); code = None; m.kill()
lines = [re.sub(r'^\S+ \[.*?\] ', '', l)[:120] for l in m.log().splitlines() if 'Address already in use' in l or 'Unable to start' in l or 'ERROR' in l]
for l in lines[:3]: print('  日志:', l)
R['inuse'] = dict(code=code, lines=lines[:3]); sock.close(); save('z4', R)
