import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from concurrent.futures import ThreadPoolExecutor
tee('z14'); R = {}
N = 300
n = Node('z14', 7300, xmx=256, conf={'maxClientCnxns': 1000}).start()
zx0 = int(n.srvr()['zxid'], 16)
print(f'== 一:同时建立 {N} 个会话(每个客户端一个):每个新会话都是一个写事务(createSession),zxid 会增加')
clients = []; lock = threading.Lock()
def mk(i):
    z = client('127.0.0.1:7300', timeout=10)
    with lock: clients.append(z)
t0 = time.perf_counter()
with ThreadPoolExecutor(30) as ex: list(ex.map(mk, range(N)))
t1 = time.perf_counter() - t0; zx1 = int(n.srvr()['zxid'], 16)
print(f'  {N} 个会话建立用时 {t1 * 1000:.0f} ms({N / t1:.0f} 个/秒);zxid 增加了 {zx1 - zx0}(= 会话数);服务端连接数 zk_num_alive_connections =', kv(n.four('mntr')).get('zk_num_alive_connections'))
R['create'] = dict(ms=t1 * 1000, dz=zx1 - zx0)
print()
print('== 二:服务端重启(stop + start,数据保留):所有客户端同时重连,看恢复的时间分布')
ev = {}; t0 = [None]
def listen(i, z):
    def f(s):
        if str(s) == 'CONNECTED' and t0[0] is not None and i not in ev: ev[i] = time.perf_counter() - t0[0]
    z.add_listener(f)
for i, z in enumerate(clients): listen(i, z)
sids = {z.client_id[0] for z in clients}
n.stop(); time.sleep(1); t0[0] = time.perf_counter(); n.start(wipe=False)
t_ready = time.perf_counter() - t0[0]
for _ in range(300):
    if len(ev) >= N: break
    time.sleep(0.1)
ts = sorted(ev.values()); m = kv(n.four('mntr'))
print(f'  服务端重启后能响应用时 {t_ready * 1000:.0f} ms;{len(ev)}/{N} 个客户端重新 CONNECTED:第一个 {ts[0] * 1000:.0f} ms、中位 {statistics.median(ts) * 1000:.0f} ms、最后一个 {ts[-1] * 1000:.0f} ms(相对服务端开始启动)')
print('  会话保持不变(会话 id 集合相同):', sids == {z.client_id[0] for z in clients}, '| 重启后 zk_global_sessions / alive connections =', m.get('zk_global_sessions'), '/', m.get('zk_num_alive_connections'))
R['reconnect'] = dict(ready=t_ready * 1000, first=ts[0] * 1000, med=statistics.median(ts) * 1000, last=ts[-1] * 1000, n=len(ev), same=sids == {z.client_id[0] for z in clients})
print()
print('== 三:同样的重启,但客户端的会话超时只有 4 秒(最小值)而服务端停了 6 秒:会话已经过期,每个客户端都要建新会话')
for z in clients: z.stop(); z.close()
clients = []
def mk2(i):
    z = client('127.0.0.1:7300', timeout=4)
    with lock: clients.append(z)
with ThreadPoolExecutor(30) as ex: list(ex.map(mk2, range(N)))
st = {}; 
def listen2(i, z):
    z.add_listener(lambda s: st.setdefault(i, []).append(str(s)))
for i, z in enumerate(clients): listen2(i, z)
sids = {z.client_id[0] for z in clients}; zxa = int(n.srvr()['zxid'], 16)
n.stop(); time.sleep(6); n.start(wipe=False); time.sleep(8)
lost = sum(1 for v in st.values() if 'LOST' in v); back = sum(1 for z in clients if z.connected); newsids = len(sids - {z.client_id[0] for z in clients if z.connected})
zxb = int(n.srvr()['zxid'], 16)
print(f'  重启后 {back}/{N} 个客户端已连上,其中状态出现过 LOST(会话过期)的 {lost} 个,换了新会话 id 的 {newsids} 个;重启后 zxid 增加 {zxb - zxa}(新会话 + 过期会话的 closeSession 事务)')
R['expired'] = dict(back=back, lost=lost, newsids=newsids, dz=zxb - zxa)
for z in clients: z.stop()
n.stop(); save('z14', R)
