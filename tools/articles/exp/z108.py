import sys, os, time, json, re, threading, subprocess, statistics, base64, http.client, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from etcdl import EtcdCluster, EtcdNode, b64
tee('z108'); R = {}
def pct(L, p): L = sorted(L); return L[min(len(L) - 1, int(len(L) * p))]
ze = Ensemble('z108', 3, base=7300, conf={'tickTime': 1000, 'maxClientCnxns': 500, 'forceSync': 'yes'}, xmx=256).start(); zh = ze.hosts()
ec = EtcdCluster('z108e', 3, base=7600).start()
class EC:   # 复用一条 keep-alive 连接的 etcd HTTP 客户端
    def __init__(self, node, timeout=3): self.n = node; self.to = timeout; self.c = http.client.HTTPConnection('127.0.0.1', node.cport, timeout=timeout)
    def call(self, path, body):
        self.c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = self.c.getresponse(); d = r.read(); return r.status, json.loads(d or b'{}')
    def put(self, k, v): return self.call('/v3/kv/put', {'key': b64(k), 'value': b64(v)})
ldr = ec.leader(); efol = [nd for nd in ec.nodes if nd is not ldr][0]; zl = ze.leader(); zfol = ze.followers()[0]
print('== 一:写延迟:对同一个 key / znode 顺序写 500 次(100 字节),客户端连着一个 follower,3 节点集群,都开 fsync(ZooKeeper forceSync=yes,etcd 默认)')
v = 'x' * 100; zc = client(f'127.0.0.1:{zfol.cport}'); zc.create('/k', b''); ecl = EC(efol); L1 = []
for i in range(50): zc.set('/k', v.encode()); ecl.put('/k', v)
for i in range(500): t = time.perf_counter(); zc.set('/k', v.encode()); L1.append((time.perf_counter() - t) * 1000)
L2 = []
for i in range(500): t = time.perf_counter(); ecl.put('/k', v); L2.append((time.perf_counter() - t) * 1000)
print(f'  ZooKeeper:中位 {statistics.median(L1):.2f} ms,p99 {pct(L1, .99):.2f} ms;etcd:中位 {statistics.median(L2):.2f} ms,p99 {pct(L2, .99):.2f} ms(etcd 走 HTTP/JSON 网关,每次请求多一点编解码开销;ZooKeeper 用 kazoo 的二进制协议)')
R['lat'] = dict(zk=[statistics.median(L1), pct(L1, .99)], etcd=[statistics.median(L2), pct(L2, .99)])
print()
print('== 二:并发写吞吐:32 个线程各自独立连接,每个线程连续写 150 次不同 key(100 字节)')
def bench_zk():
    cs = [client(f'127.0.0.1:{nd.cport}') for nd in ze.nodes for _ in range(11)][:32]; [c.ensure_path(f'/b{i}') for i, c in enumerate(cs[:1])]; cs[0].ensure_path('/bz')
    def w(i):
        for k in range(150): cs[i].create(f'/bz/n-{i}-{k}', v.encode())
    t = time.perf_counter(); ths = [threading.Thread(target=w, args=(i,)) for i in range(32)]; [x.start() for x in ths]; [x.join() for x in ths]; el = time.perf_counter() - t; [c.stop() for c in cs]; return 32 * 150 / el
def bench_etcd():
    nodes = ec.nodes; cs = [EC(nodes[i % 3]) for i in range(32)]
    def w(i):
        for k in range(150): cs[i].put(f'/bz/n-{i}-{k}', v)
    t = time.perf_counter(); ths = [threading.Thread(target=w, args=(i,)) for i in range(32)]; [x.start() for x in ths]; [x.join() for x in ths]; return 32 * 150 / (time.perf_counter() - t)
bz = bench_zk(); be = bench_etcd(); print(f'  ZooKeeper {bz:.0f} 次/s;etcd {be:.0f} 次/s(同一台机器、同一块磁盘、6 个服务端进程;客户端协议不同,数字只能粗略对比)'); R['tp'] = dict(zk=bz, etcd=be)
print()
print('== 三:watch 语义:一个 watcher 订阅一个 key,写入端快速连续写(ZooKeeper 异步 200 次;etcd 16 线程并发 208 次),统计收到多少个事件')
got_z = []; zw = client(f'127.0.0.1:{zfol.cport}'); zc.ensure_path('/w'); zc.create('/w/k', b'0')
from kazoo.recipe.watchers import DataWatch
DataWatch(zw, '/w/k', lambda d, s: got_z.append(d))
got_e = []; stop_e = threading.Event()
def etcd_watch():
  try:
    c = http.client.HTTPConnection('127.0.0.1', efol.cport, timeout=30); c.request('POST', '/v3/watch', json.dumps({'create_request': {'key': b64('/w/k')}}), {'Content-Type': 'application/json'}); r = c.getresponse()
    buf = b''
    while not stop_e.is_set():
        data = r.read1(65536)
        if not data: break
        buf += data
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            if not line.strip(): continue
            d = json.loads(line).get('result', {})
            for ev in d.get('events', []): got_e.append(base64.b64decode(ev['kv'].get('value', '')).decode())
  except Exception: pass
th = threading.Thread(target=etcd_watch, daemon=True); th.start(); time.sleep(1); got_z.clear(); wc = EC(efol); ecl.put('/w/k', '0'); time.sleep(0.3); got_e.clear()
[zc.set_async('/w/k', f'r{i}'.encode()) for i in range(200)]
time.sleep(2.5); got_z_n = len(got_z); got_z_last = got_z[-1].decode()
def burst(lo):
    c = EC(efol)
    for i in range(lo, lo + 13): c.put('/w/k', f'r{i}')
ths = [threading.Thread(target=burst, args=(i * 13,)) for i in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]
time.sleep(1.5)
print(f'  ZooKeeper(DataWatch;用 set_async 一次性发出 200 次写):收到 {got_z_n} 次回调,最后值 {got_z_last};etcd(watch 流;16 个线程并发共写 208 次):收到 {len(got_e)} 个事件(应为 208,每个 revision 一个)'); R['watch'] = dict(zk=got_z_n, etcd=len(got_e))
stop_e.set()
print()
print('== 四:发现客户端崩溃:客户端是独立子进程,持有一个会话 / 租约(TTL 3 s)和一个绑定它的 key,kill -9 之后 key 多久消失(各 3 次)')
cz = '''
import sys, time, os
sys.path.insert(0, %r)
from zkl import client
c = client(%r, timeout=3); c.create('/lease-key', b'x', ephemeral=True); print('UP', flush=True); time.sleep(300)
''' % (str(HERE), f'127.0.0.1:{zfol.cport}')
ce = '''
import sys, time, json, base64, http.client
def call(c, path, body):
    c.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'}); r = c.getresponse(); return json.loads(r.read() or b'{}')
b64 = lambda s: base64.b64encode(s.encode()).decode()
c = http.client.HTTPConnection('127.0.0.1', %d, timeout=3); lid = call(c, '/v3/lease/grant', {'TTL': 3})['ID']
call(c, '/v3/kv/put', {'key': b64('/lease-key'), 'value': b64('x'), 'lease': lid}); print('UP', flush=True)
while True:
    call(c, '/v3/lease/keepalive', {'ID': lid}); time.sleep(1)
''' % efol.cport
def gone_zk(): return zc.exists('/lease-key') is None
def gone_e():
    s, d = ecl.call('/v3/kv/range', {'key': b64('/lease-key')}); return not d.get('kvs')
res = {'zk': [], 'etcd': []}
for kind, code, gone in (('zk', cz, gone_zk), ('etcd', ce, gone_e)):
    for k in range(3):
        p = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(1.5); tk = time.time(); p.kill()
        while time.time() - tk < 30 and not gone(): time.sleep(0.02)
        res[kind].append(time.time() - tk); time.sleep(1)
print(f'  ZooKeeper(会话超时 3 s):{[round(x, 1) for x in res["zk"]]} s;etcd(租约 TTL 3 s):{[round(x, 1) for x in res["etcd"]]} s'); R['detect'] = {k: [round(x, 1) for x in v_] for k, v_ in res.items()}
print()
print('== 五:杀掉 leader 之后写入不可用的时间窗:一个线程每 10 ms 写一次(连着一个 follower),杀 leader,再把它重新启动;各重复 4 次')
def gaps_for(ts, tk):
    oks = [t for t, o in ts if o and t > tk]; return max((b - a for a, b in zip([tk] + oks[:-1], oks)), default=None)
def outage_zk():
    out_ = []
    for k in range(4):
        ld = [nd for nd in ze.nodes if nd.alive() and nd.mode() == 'leader'][0]; fo = [nd for nd in ze.nodes if nd is not ld and nd.alive()][0]
        zc2 = client(f'127.0.0.1:{fo.cport}', timeout=6); zc2.ensure_path('/o'); stop = threading.Event(); ts = []
        def w():
            while not stop.is_set():
                t = time.time()
                try: zc2.set('/o', b'x'); ts.append((t, True))
                except Exception: ts.append((t, False))
                time.sleep(0.01)
        th = threading.Thread(target=w); th.start(); time.sleep(1.5); tk = time.time(); ld.kill(); time.sleep(5); stop.set(); th.join(); out_.append(gaps_for(ts, tk)); zc2.stop(); ld.start(wipe=False, wait=True); time.sleep(3)
    return out_
def outage_etcd():
    out_ = []
    for k in range(4):
        ld = ec.leader(); fo = [nd for nd in ec.nodes if nd is not ld and nd.alive()][0]; stop = threading.Event(); ts = []
        def w():
            c = EC(fo, 0.25)
            while not stop.is_set():
                t = time.time()
                try: c.put('/o', 'x'); ts.append((t, True))
                except Exception: ts.append((t, False)); c = EC(fo, 0.25)
                time.sleep(0.01)
        th = threading.Thread(target=w); th.start(); time.sleep(1.5); tk = time.time(); ld.kill(); time.sleep(5); stop.set(); th.join(); out_.append(gaps_for(ts, tk)); ld.start(wipe=False, state='existing'); time.sleep(4)
    return out_
oz = outage_zk(); oe = outage_etcd()
print(f'  ZooKeeper(tickTime=1000):{[round(x * 1000) for x in oz if x]} ms;etcd(默认 heartbeat 100 ms / election 1000 ms,客户端单次请求超时 0.25 s,所以时间窗的精度约 0.25 s):{[round(x * 1000) for x in oe if x]} ms'); R['outage'] = dict(zk=[round(x * 1000) for x in oz if x], etcd=[round(x * 1000) for x in oe if x])
print()
print('== 六:单个值的大小上限:etcd 写 1 MiB、1.4 MiB、2 MiB 的值(ZooKeeper 的 1 MiB 上限见第 1 篇与第 24 篇)')
for sz in (1 << 20, int(1.4 * (1 << 20)), 2 << 20):
    try: s, d = EC(efol, 10).put('/big', 'x' * sz); r = 'OK' if s == 200 else f'HTTP {s} {d.get("message", "")[:60]}'
    except Exception as e: r = type(e).__name__
    print(f'  etcd 写 {sz / (1 << 20):.1f} MiB → {r}')
R['big'] = 'done'
for x in (zc, zw): x.stop()
ze.stop(); ec.stop(); save('z108', R); os._exit(0)
