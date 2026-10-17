import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.watchers import DataWatch
tee('z85'); R = {}
n = Node('z85', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); adm = client('127.0.0.1:7300')
adm.create('/cfg', b'v0')
def pct(L, p): L = sorted(L); return L[min(len(L) - 1, int(len(L) * p))]
print('== 一:50 个应用实例各 watch /cfg;配置中心每 100 ms 更新一次,共 30 次:从 set 返回到各实例回调执行的延迟')
N = 50; cl = [client('127.0.0.1:7300') for _ in range(N)]; got = [[] for _ in range(N)]; ready = threading.Event()
def mk(i):
    def cb(data, stat):
        got[i].append((time.perf_counter(), data))
    return cb
for i in range(N): DataWatch(cl[i], '/cfg', mk(i))
time.sleep(0.5); base = [len(g) for g in got]; lat = []; sent = {}
for k in range(30):
    v = f'v{k+1}'.encode(); adm.set('/cfg', v); sent[v] = time.perf_counter(); time.sleep(0.1)
time.sleep(0.5)
miss = 0
for i in range(N):
    seen = {d: t for t, d in got[i]}
    for v, ts in sent.items():
        if v in seen: lat.append((seen[v] - ts) * 1000)
        else: miss += 1
print(f'  {N} 个实例 × 30 次更新 = {N*30} 次推送:收到 {len(lat)},漏掉 {miss};延迟(ms)中位 {statistics.median(lat):.1f},p99 {pct(lat, .99):.1f},最大 {max(lat):.1f}')
R['lat'] = dict(n=len(lat), miss=miss, med=statistics.median(lat), p99=pct(lat, .99), mx=max(lat))
print()
print('== 二:连续快速更新 200 次(不等待):每个实例的回调次数与最终值')
for g in got: g.clear()
fin = None
for k in range(200): fin = f'r{k}'.encode(); adm.set('/cfg', fin)   # 同步调用,尽可能快
time.sleep(1.0)
cnt = [len(g) for g in got]; last = [g[-1][1] for g in got]
print(f'  200 次更新;各实例回调次数:最少 {min(cnt)},中位 {statistics.median(cnt):.0f},最多 {max(cnt)};最终值都是 {fin.decode()}:{all(x == fin for x in last)}')
R['rapid'] = dict(min=min(cnt), med=statistics.median(cnt), mx=max(cnt), same=all(x == fin for x in last))
print()
print('== 三:一个实例与服务端断开(代理关闭连接并拒绝重连,约 4.4 秒),这期间配置更新 3 次;恢复后它看到什么')
px = Proxy(7310, 7300).start(); c = client('127.0.0.1:7310'); seen = []; DataWatch(c, '/cfg', lambda d, s: seen.append(d)); time.sleep(0.5); seen.clear()
px.close_all(); px.blocked = True
for v in (b'during-1', b'during-2', b'during-3'): adm.set('/cfg', v); time.sleep(0.3)
time.sleep(3.5); print('  断网期间该实例收到的回调:', [x.decode() for x in seen])
px.blocked = False; t0 = time.perf_counter()
while not seen and time.perf_counter() - t0 < 20: time.sleep(0.05)
print(f'  恢复后 {time.perf_counter() - t0:.1f} s 内收到:', [x.decode() for x in seen], '(只有最新值 during-3,中间两次更新对它不可见)')
R['part'] = dict(seen=[x.decode() for x in seen])
print()
print('== 四:新实例启动时读到当前值')
t0 = time.perf_counter(); c2 = client('127.0.0.1:7300'); v = c2.get('/cfg')[0]; print(f'  连接 + 读取 = {(time.perf_counter()-t0)*1000:.0f} ms,读到 {v.decode()}'); R['newc'] = (time.perf_counter() - t0) * 1000
print()
print('== 五:整份 JSON 放一个节点 vs 每个配置项一个节点:改 1 项,一个已订阅的实例收到多少字节')
cfg = {f'key{i:03d}': 'x' * 40 for i in range(100)}
adm.create('/j', json.dumps(cfg).encode()); adm.create('/k'); [adm.create(f'/k/{k}', v.encode()) for k, v in cfg.items()]
def measure(kind):
    px = Proxy(7320 if kind == 'j' else 7321, 7300).start(); c = client(f'127.0.0.1:{px.listen}')
    if kind == 'j': DataWatch(c, '/j', lambda d, s: None)
    else:
        for k in cfg: DataWatch(c, f'/k/{k}', lambda d, s: None)
    time.sleep(1.0); b0 = px.bytes_down
    if kind == 'j': c2 = dict(cfg); c2['key050'] = 'y' * 40; adm.set('/j', json.dumps(c2).encode())
    else: adm.set('/k/key050', b'y' * 40)
    time.sleep(1.0); r = px.bytes_down - b0; c.stop(); return r
bj, bk = measure('j'), measure('k')
print(f'  整份 JSON({len(json.dumps(cfg))} 字节):改 1 项后服务端发给该实例 {bj} 字节;每项一个节点(100 个节点):{bk} 字节')
R['bytes'] = dict(json=bj, per_key=bk, size=len(json.dumps(cfg)))
for x in cl + [c, c2 if False else c2]:
    try: x.stop()
    except Exception: pass
adm.stop(); n.stop(); save('z85', R); os._exit(0)
