import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z61'); R = {}
import uuid
def load(hosts, conc, secs, mode):
    tag = uuid.uuid4().hex[:6]; cl = [client(hosts, timeout=20) for _ in range(conc)]; cl[0].ensure_path(f'/l/{tag}')
    for i, c in enumerate(cl):
        if mode == 'read':
            try: c.create(f'/l/{tag}/r{i}', b'x' * 100)
            except Exception: pass
    lat = []; lock = threading.Lock(); stop = threading.Event(); cnt = [0]
    def w(i):
        c = cl[i]; k = 0; mine = []
        while not stop.is_set():
            t = time.perf_counter()
            if mode == 'write': c.create(f'/l/{tag}/w{i}-{k}', b'x' * 100)
            else: c.get(f'/l/{tag}/r{i}')
            mine.append((time.perf_counter() - t) * 1000); k += 1
        with lock: lat.extend(mine)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(conc)]; t0 = time.perf_counter(); [t.start() for t in ts]; time.sleep(secs); stop.set(); [t.join() for t in ts]; el = time.perf_counter() - t0
    [c.stop() for c in cl]; lat.sort(); return dict(ops=len(lat) / el, p50=lat[len(lat) // 2], p99=lat[int(len(lat) * 0.99)], n=len(lat))
def table(title, hosts):
    print(f'  [{title}]'); print(f'  {"并发客户端":>8} {"写 ops/s":>9} {"写 p50 ms":>10} {"写 p99 ms":>10} {"读 ops/s":>9} {"读 p50 ms":>10} {"读 p99 ms":>10}'); rows = []
    for conc in (1, 4, 16, 64):
        w = load(hosts, conc, 5, 'write'); r = load(hosts, conc, 5, 'read'); rows.append((conc, w, r)); print(f'  {conc:>8} {w["ops"]:>9.0f} {w["p50"]:>10.2f} {w["p99"]:>10.2f} {r["ops"]:>9.0f} {r["p50"]:>10.2f} {r["p99"]:>10.2f}')
    return rows
print('== 一:单机:并发客户端数增加时的吞吐与延迟(每个客户端同步地、一个请求接一个请求;写 100 字节)')
n = Node('z61a', 7300, xmx=256, conf={'maxClientCnxns': 1000}).start(); R['single'] = table('单机', '127.0.0.1:7300'); n.stop()
print()
print('== 二:3 节点集群(客户端均匀连到 3 个节点)')
e = Ensemble('z61b', 3, base=7310, xmx=256, conf={'maxClientCnxns': 1000}).start(); R['cluster'] = table('3 节点', e.hosts()); e.stop()
save('z61', R)
