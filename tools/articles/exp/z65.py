import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z65'); R = {}
KEYS = ['zk_avg_latency', 'zk_max_latency', 'zk_outstanding_requests', 'zk_num_alive_connections', 'zk_watch_count', 'zk_znode_count', 'zk_ephemerals_count', 'zk_open_file_descriptor_count', 'zk_avg_fsynctime', 'zk_max_fsynctime', 'zk_packets_received', 'zk_last_client_response_size', 'zk_max_client_response_size']
n = Node('z65', 7300, xmx=256, conf={'maxClientCnxns': 1000}).start(); z = client('127.0.0.1:7300')
rs = [z.create_async(f'/n{i}', b'x' * 100) for i in range(2000)]; [r.get() for r in rs]
scen = {}
def snap(name): m = kv(n.four('mntr')); scen[name] = {k: m.get(k) for k in KEYS}
n.four('srst'); time.sleep(1); snap('空闲(只有 1 个连接)')
n.four('srst'); stop = threading.Event(); cnt = [0]
def w():
    while not stop.is_set(): z.create(f'/s{cnt[0]}', b'x' * 100); cnt[0] += 1
t = threading.Thread(target=w); t.start(); time.sleep(4); snap('稳定写入(串行同步写,约 300 次/秒)'); stop.set(); t.join()
n.four('srst'); rs = []; t0 = time.perf_counter()
def flood():
    global rs
    rs = [z.create_async(f'/f{i}', b'x' * 100) for i in range(30000)]
th = threading.Thread(target=flood); th.start(); time.sleep(0.5); mid = kv(n.four('mntr')).get('zk_outstanding_requests'); th.join(); [r.get() for r in rs]; snap('突发:异步 30000 个写')
scen['突发:异步 30000 个写']['zk_outstanding_requests'] = f'{mid}(洪峰中途采样)'
cl = [client('127.0.0.1:7300', timeout=30) for _ in range(300)]
for i, c in enumerate(cl):
    for j in range(20): c.get(f'/n{(i * 20 + j) % 2000}', watch=lambda e: None)
z.create('/eph', b'', ephemeral=True); n.four('srst'); big = z.get_children('/'); snap('300 个连接 + 6000 个 watch + 1 个读大目录')
print('== 一:同一个节点在四种状态下,值得盯的 mntr 指标(每种状态前先 srst 清零统计)')
names = list(scen.keys())
print(f'  {"指标":<32} ' + ' | '.join(f'{x[:14]:<14}' for x in names))
for k in KEYS: print(f'  {k:<32} ' + ' | '.join(f'{str(scen[x][k])[:14]:<14}' for x in names))
R['scen'] = scen
print()
print('== 二:读数时的几个注意点(都来自上面的数字)')
print('  · zk_max_latency 是「自上次 srst 以来」的最大值,要告警就必须定期 srst 或用差值;')
print('  · zk_outstanding_requests 是瞬时值,洪峰过去就回到 0,所以要高频采样(或看 max);')
print('  · zk_watch_count、zk_num_alive_connections 是状态量,随客户端行为变化,不会随时间自己恢复;')
print('  · zk_open_file_descriptor_count 要和 zk_max_file_descriptor_count 对照(连接数 + 日志 / 快照文件都占 fd)。')
[c.stop() for c in cl]; z.stop(); n.stop(); save('z65', R)
