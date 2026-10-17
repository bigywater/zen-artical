import sys, os, time, json, re, threading, subprocess, statistics, base64, http.client, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from cnl import *
tee('z110'); R = {}
def pct(L, p): L = sorted(L); return L[min(len(L) - 1, int(len(L) * p))]
cc = CCluster('z110', 3).start(); nodes = cc.nodes; ld = cc.leader(); fol = [x for x in nodes if x is not ld][0]
print(f'== 一:Consul 2.0.4 三个 server 的集群(leader = {ld.name}),写 KV 的延迟:客户端连 follower,顺序写 500 次 100 字节(与第 108 篇同一台机器,同样的方法)')
class C:
    def __init__(self, node, timeout=5): self.n = node; self.c = http.client.HTTPConnection('127.0.0.1', node.http, timeout=timeout)
    def req(self, m, p, body=None):
        self.c.request(m, p, body); r = self.c.getresponse(); d = r.read(); return r.status, d, dict(r.getheaders())
cl = C(fol); L = []
for i in range(50): cl.req('PUT', '/v1/kv/k', b'x' * 100)
for i in range(500): t = time.perf_counter(); cl.req('PUT', '/v1/kv/k', b'x' * 100); L.append((time.perf_counter() - t) * 1000)
print(f'  Consul:中位 {statistics.median(L):.2f} ms,p99 {pct(L, .99):.2f} ms'); R['lat'] = [statistics.median(L), pct(L, .99)]
print()
print('== 二:watch(阻塞查询):GET /v1/kv/w?index=<上次的 index> 会一直挂着直到有变化;写入端快速连续写 200 次(16 线程并发),watcher 循环发阻塞查询,统计它被唤醒的次数')
cl.req('PUT', '/v1/kv/w', b'0'); got = []; stop = threading.Event()
def watcher():
    c = C(fol, timeout=20); s, d, h = c.req('GET', '/v1/kv/w'); idx = h['X-Consul-Index']
    while not stop.is_set():
        try: s, d, h = c.req('GET', f'/v1/kv/w?index={idx}&wait=5s')
        except Exception: break
        if h['X-Consul-Index'] != idx: idx = h['X-Consul-Index']; got.append(base64.b64decode(json.loads(d)[0]['Value']).decode())
th = threading.Thread(target=watcher, daemon=True); th.start(); time.sleep(1)
def burst(lo):
    c = C(fol)
    for i in range(lo, lo + 13): c.req('PUT', '/v1/kv/w', f'r{i}'.encode())
ths = [threading.Thread(target=burst, args=(i * 13,)) for i in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]; time.sleep(1.5); stop.set()
print(f'  16 线程共写 208 次;阻塞查询的 watcher 被唤醒 {len(got)} 次(每次返回当时的最新值);最后看到的值 {got[-1]}。阻塞查询只返回「变化后的当前状态」,中间的更新会被合并,和 ZooKeeper 的 watch 类似(第 108 篇里 etcd 的 watch 流则每个 revision 一个事件)'); R['watch'] = len(got)
print()
print('== 三:session 与锁:持有者(独立子进程)创建 session(TTL 10 s,Consul 允许的最小值)并用 ?acquire= 获取锁 key,定期续约;B 每 200 ms 尝试获取;kill -9 持有者后 B 多久拿到锁?分别用默认 lock-delay(15 s)和 lock-delay=0 各 2 次')
hold = '''
import sys, time, json, http.client
port, ld, key = int(sys.argv[1]), sys.argv[2], sys.argv[3]
def req(m, p, b=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5); c.request(m, p, b); r = c.getresponse(); d = r.read(); c.close(); return r.status, d
sid = json.loads(req('PUT', '/v1/session/create', json.dumps({'TTL': '10s', 'Behavior': 'release', 'LockDelay': ld}))[1])['ID']
print(req('PUT', f'/v1/kv/{key}?acquire={sid}', b'A')[1], flush=True)
while True:
    req('PUT', f'/v1/session/renew/{sid}'); time.sleep(3)
'''
res = {}; inv = {}
for label, lds in (('default 15s', '15s'), ('0', '0s')):
    res[label] = []; inv[label] = []
    for trial in range(2):
        key = f'lock-{label.split()[0]}-{trial}'; p = subprocess.Popen([sys.executable, '-c', hold, str(fol.http), lds, key], stdout=subprocess.PIPE, text=True); first = p.stdout.readline(); time.sleep(1)
        sidA = json.loads(cl.req('GET', f'/v1/kv/{key}')[1])[0]['Session']
        sb = json.loads(cl.req('PUT', '/v1/session/create', json.dumps({'TTL': '10s', 'Behavior': 'release', 'LockDelay': lds}))[1])['ID']; tk = time.time(); p.kill(); got_b = None; t_inv = None; last_renew = 0
        while time.time() - tk < 90:
            if time.time() - last_renew > 3: cl.req('PUT', f'/v1/session/renew/{sb}'); last_renew = time.time()
            if t_inv is None and json.loads(cl.req('GET', f'/v1/kv/{key}')[1])[0].get('Session') != sidA: t_inv = time.time() - tk
            s, d, h = cl.req('PUT', f'/v1/kv/{key}?acquire={sb}', b'B')
            if d.strip() == b'true': got_b = time.time() - tk; break
            time.sleep(0.2)
        res[label].append(got_b); inv[label].append(t_inv); cl.req('PUT', f'/v1/session/destroy/{sb}')
        print(f'  lock-delay={label}(第 {trial + 1} 次):锁 key 上的 Session 在 kill -9 后 {round(t_inv, 1) if t_inv else None} s 被清掉(session 失效);B 在 {round(got_b, 1) if got_b else None} s 拿到锁')
R['lock'] = {k: [round(x, 1) if x else None for x in v] for k, v in res.items()}; R['lock_inv'] = {k: [round(x, 1) if x else None for x in v] for k, v in inv.items()}
print()
print('== 四:服务注册 + TTL 健康检查:服务 svc 带一个 TTL=3s 的检查,客户端(独立子进程)每秒更新一次检查为 passing;kill -9 之后 /v1/health/service/svc?passing 多久不再返回该实例(3 次)')
beat = '''
import sys, time, json, http.client
port = int(sys.argv[1])
def req(m, p, b=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5); c.request(m, p, b); r = c.getresponse(); d = r.read(); c.close(); return r.status, d
req('PUT', '/v1/agent/service/register', json.dumps({'ID': 'svc1', 'Name': 'svc', 'Port': 9999, 'Check': {'CheckID': 'ttl1', 'TTL': '3s'}}))
print('UP', flush=True)
while True:
    req('PUT', '/v1/agent/check/pass/ttl1'); time.sleep(1)
'''
d4 = []
for trial in range(3):
    p = subprocess.Popen([sys.executable, '-c', beat, str(fol.http)], stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(2)
    n_ok = len(json.loads(cl.req('GET', '/v1/health/service/svc?passing')[1])); tk = time.time(); p.kill()
    while time.time() - tk < 60 and len(json.loads(cl.req('GET', '/v1/health/service/svc?passing')[1])) > 0: time.sleep(0.1)
    d4.append(time.time() - tk)
    if d4[-1] > 30: print('    (超时,此刻 health 返回:', cl.req('GET', '/v1/health/service/svc')[1][:300], ')')
    cl.req('PUT', '/v1/agent/service/deregister/svc1'); time.sleep(1)
print(f'  kill -9 之前 passing 实例数 {n_ok};之后消失用时 {[round(x, 1) for x in d4]} s(TTL 3 s)'); R['health'] = [round(x, 1) for x in d4]
print()
print('== 五:杀掉 leader 之后写入不可用的时间窗(每 10 ms 写一次连 follower,请求超时 0.25 s):默认 raft 参数 与 performance.raft_multiplier=1,各重复 3 次')
def window(ts, tk):
    before = [t for t, o in ts if o and t < tk]; after = [t for t, o in ts if o and t > tk]
    return (min(after) - max(before)) if before and after else None
def outage(cluster, rounds=3):
    nodes_ = cluster.nodes; res_ = []
    for k in range(rounds):
        ld_ = cluster.leader(); fo = [nd for nd in nodes_ if nd is not ld_ and nd.alive()][0]; stop_ = threading.Event(); ts = []
        def w():
            c = C(fo, 0.25)
            while not stop_.is_set():
                t = time.time()
                try:
                    s_, d_, h_ = c.req('PUT', '/v1/kv/o', b'x'); ts.append((t, s_ == 200))
                except Exception: ts.append((t, False)); c = C(fo, 0.25)
                time.sleep(0.01)
        th_ = threading.Thread(target=w); th_.start(); time.sleep(1.5); tk = time.time(); ld_.kill()
        t0_ = time.time()
        while time.time() - t0_ < 40 and not any(o and t > tk for t, o in ts): time.sleep(0.1)
        time.sleep(1); stop_.set(); th_.join(); res_.append(window(ts, tk)); ld_.start(wipe=False); time.sleep(8)
    return res_
o_def = outage(cc); cc.stop(); time.sleep(2)
cc2 = CCluster('z110f', 3, mult=1).start(); o_fast = outage(cc2); cc2.stop()
print(f'  默认参数:{[round(x * 1000) if x else None for x in o_def]} ms;raft_multiplier=1:{[round(x * 1000) if x else None for x in o_fast]} ms'); R['outage'] = dict(default=[round(x * 1000) if x else None for x in o_def], fast=[round(x * 1000) if x else None for x in o_fast])
print()
print()
print('== 六:KV 单值大小上限:写 512 KiB 与 513 KiB 的值(HTTP 状态码)')
cc2 = CCluster('z110g', 3).start(); fol2 = [x for x in cc2.nodes if x is not cc2.leader()][0]; cl = C(fol2)
for sz in (512 * 1024, 512 * 1024 + 1):
    s_, d_, h_ = C(fol2, 20).req('PUT', '/v1/kv/big', b'x' * sz); print(f'  写 {sz} 字节 → HTTP {s_} {d_[:90].decode("latin1") if s_ != 200 else ""}')
R['big'] = 'done'
cc2.stop(); save('z110', R); os._exit(0)
