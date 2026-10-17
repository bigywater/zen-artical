import sys, os, time, json, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z2'); R = {}
def lat(hosts, n=300):
    z = client(hosts); v = b'v' * 100; xs = []
    for i in range(n):
        t0 = time.perf_counter(); z.create(f'/l{i}', v); xs.append((time.perf_counter() - t0) * 1000)
    z.stop(); return statistics.median(xs)
print('== 一:单机模式(standalone):没有 server.N 配置,srvr 里 Mode: standalone')
s = Node('z2s', 7300).start()
print('  Mode:', s.srvr().get('mode'), '| 节点数 / quorum:', '1 / 无');  R['standalone_mode'] = s.srvr().get('mode')
R['lat_standalone'] = lat('127.0.0.1:7300'); print(f'  写延迟(中位数,300 次同步 create):{R["lat_standalone"]:.2f} ms'); s.stop()
print()
print('== 二:伪集群(3 个进程同一台机器、不同端口)的配置与角色:每个节点的 zoo.cfg 里 server.N 与 myid')
e = Ensemble('z2e', 3, base=7310).start()
for nd in e.nodes: print(f'  {nd.name}: client {nd.cport}  myid {nd.myid}  Mode: {nd.srvr().get("mode")}')
print('  zoo.cfg 里的集群部分:', [l for l in (e.nodes[0].dir / 'zoo.cfg').read_text().splitlines() if l.startswith('server.')])
R['roles'] = {nd.name: nd.srvr().get('mode') for nd in e.nodes}
R['lat_cluster'] = lat(e.hosts()); print(f'  写延迟(中位数,300 次同步 create,连接到集群):{R["lat_cluster"]:.2f} ms(对比单机 {R["lat_standalone"]:.2f} ms)')
e.stop()
print()
print('== 三:集群只起 1 个 / 2 个节点(共 3 个):多数派不满足时能不能服务')
e = Ensemble('z2q', 3, base=7320)
for nd in e.nodes: nd.prepare()
e.nodes[0].start(wait=False); time.sleep(4)
nd = e.nodes[0]; print('  只起 1/3:ruok →', four(nd.cport, 'ruok').strip(), '| srvr →', four(nd.cport, 'srvr').strip().splitlines()[0][:80])
try:
    z = client(f'127.0.0.1:{nd.cport}', timeout=4); z.create('/x', b'1'); print('  客户端 create → 成功')
except Exception as ex: print('  客户端连接 / create →', type(ex).__name__)
e.nodes[1].start(wait=False); e.wait_quorum()
print('  起到 2/3 后:', {x.name: x.mode() for x in e.nodes if x.alive()})
z = client(e.hosts().split(',')[0] + ',' + e.hosts().split(',')[1]); z.create('/x', b'1'); print('  客户端 create → 成功(2/3 够多数派)'); z.stop()
R['quorum'] = {x.name: x.mode() for x in e.nodes if x.alive()}
e.stop(); save('z2', R)
