import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from concurrent.futures import ThreadPoolExecutor
tee('z17'); R = {}
N = 300
n = Node('z17', 7300, xmx=256, conf={'maxClientCnxns': 1000}).start()
w = client('127.0.0.1:7300'); w.create('/hot', b'v0')
clients = []; lock = threading.Lock()
def mk(i):
    z = client('127.0.0.1:7300', timeout=20)
    with lock: clients.append(z)
with ThreadPoolExecutor(30) as ex: list(ex.map(mk, range(N)))
arrive = {}; t0 = [0.0]
def reg(i):
    def cb(e): arrive[i] = time.perf_counter() - t0[0]
    clients[i].get('/hot', watch=cb)
for i in range(N): reg(i)
print('== 一:%d 个客户端都对 /hot 注册了 data watch;服务端的 wchs / wchc 统计' % N)
print('  wchs:', ' '.join(n.four('wchs').split()))
m = kv(n.four('mntr')); print('  mntr zk_watch_count =', m.get('zk_watch_count'), '| zk_num_alive_connections =', m.get('zk_num_alive_connections')); R['watch_count'] = m.get('zk_watch_count')
print()
print('== 二:一次 set 触发全部 watcher:从 set 返回开始计,各客户端收到通知的时间')
t0[0] = time.perf_counter(); w.set('/hot', b'v1'); tset = time.perf_counter() - t0[0]
for _ in range(100):
    if len(arrive) >= N: break
    time.sleep(0.05)
ts = sorted(arrive.values())
print(f'  set 调用自己用时 {tset * 1000:.1f} ms;{len(arrive)}/{N} 个收到通知:第一个 {ts[0] * 1000:.0f} ms、中位 {statistics.median(ts) * 1000:.0f} ms、最后一个 {ts[-1] * 1000:.0f} ms')
R['notify'] = dict(n=len(arrive), first=ts[0] * 1000, med=statistics.median(ts) * 1000, last=ts[-1] * 1000, set_ms=tset * 1000)
print()
print('== 三:惊群:收到通知后所有客户端立刻重新 get + 重新注册(典型写法),服务端在这一瞬间的负载')
arrive2 = {}; lat = []
n.four('srst'); t0[0] = time.perf_counter(); done = threading.Event()
def reread(i):
    t = time.perf_counter(); clients[i].get('/hot', watch=lambda e: None); lat.append((time.perf_counter() - t) * 1000)
with ThreadPoolExecutor(60) as ex: list(ex.map(reread, range(N)))
tt = time.perf_counter() - t0[0]
mx = kv(n.four('mntr'))
print(f'  {N} 个客户端并发重新读取 + 注册 watch 共用 {tt * 1000:.0f} ms;单次 get 延迟(客户端侧)中位 {statistics.median(lat):.1f} ms、最大 {max(lat):.1f} ms;服务端 zk_max_latency = {mx.get("zk_max_latency")} ms')
R['herd'] = dict(total=tt * 1000, med=statistics.median(lat), mx=max(lat), srv_max=mx.get('zk_max_latency'))
print()
print('== 四:对照:只有 1 个客户端 watch 时,同样的 set 到通知的时间')
for z in clients: z.stop()
time.sleep(1)
one = client('127.0.0.1:7300'); got = []; one.get('/hot', watch=lambda e: got.append(time.perf_counter())); t = time.perf_counter(); w.set('/hot', b'v2')
for _ in range(100):
    if got: break
    time.sleep(0.005)
print(f'  1 个 watcher:通知在 set 开始后 {(got[0] - t) * 1000:.1f} ms 到达'); R['one'] = (got[0] - t) * 1000
one.stop(); w.stop(); n.stop(); save('z17', R)
