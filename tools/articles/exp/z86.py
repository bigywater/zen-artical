import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.watchers import DataWatch
from kazoo.exceptions import BadVersionError
tee('z86'); R = {}
n = Node('z86', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); adm = client('127.0.0.1:7300')
print('== 一:版本号与乐观锁:两个人都读到 version=0,先后各改一次,带 version 写')
adm.create('/app', json.dumps({'timeout': 30, 'retries': 3}).encode())
d1, s1 = adm.get('/app'); d2, s2 = adm.get('/app'); print(f'  A、B 都读到 version = {s1.version}')
adm.set('/app', json.dumps({'timeout': 60, 'retries': 3}).encode(), version=s1.version); print('  A 带 version=0 写入成功')
try: adm.set('/app', json.dumps({'timeout': 30, 'retries': 9}).encode(), version=s2.version); r = '成功'
except BadVersionError: r = 'BadVersionError(被拒绝)'
print('  B 也带 version=0 写入:', r); st = adm.get('/app')[1]; print(f'  现在 version = {st.version},内容 = {adm.get("/app")[0].decode()}(B 的修改没有悄悄覆盖 A)')
R['cas_reject'] = r.startswith('BadVersion')
print()
print('== 二:10 个客户端各做 20 次「读 JSON → n 加 1 → 写回」:不带 version vs 带 version 重试')
def rmw(use_cas):
    adm.set('/ctr', json.dumps({'n': 0}).encode()) if adm.exists('/ctr') else adm.create('/ctr', json.dumps({'n': 0}).encode())
    cl = [client('127.0.0.1:7300') for _ in range(10)]; retries = [0] * 10
    def w(i):
        c = cl[i]
        for _ in range(20):
            while True:
                d, s = c.get('/ctr'); v = json.loads(d)['n'] + 1
                try: c.set('/ctr', json.dumps({'n': v}).encode(), version=s.version if use_cas else -1); break
                except BadVersionError: retries[i] += 1
                if not use_cas: break
    ths = [threading.Thread(target=w, args=(i,)) for i in range(10)]; [t.start() for t in ths]; [t.join() for t in ths]
    [c.stop() for c in cl]; return json.loads(adm.get('/ctr')[0])['n'], sum(retries)
a = rmw(False); b = rmw(True)
print(f'  不带 version:最终 {a[0]} / 200(丢 {200 - a[0]});带 version 重试:最终 {b[0]} / 200,为此重试了 {b[1]} 次')
R['rmw'] = dict(nocas=a[0], cas=b[0], retries=b[1])
print()
print('== 三:ZooKeeper 只保留当前值,没有历史:想回滚就要自己存历史')
adm.create('/hist/app', b'', makepath=True)
vers = [{'timeout': 30}, {'timeout': 60}, {'timeout': 5}]
for v in vers: adm.create('/hist/app/ver-', json.dumps(v).encode(), sequence=True); adm.set('/app', json.dumps(v).encode())
print('  /hist/app 子节点:', sorted(adm.get_children('/hist/app')))
print(f'  /app 的当前 stat.version = {adm.get("/app")[1].version};它只有当前内容:{adm.get("/app")[0].decode()}')
N = 50; cl = [client('127.0.0.1:7300') for _ in range(N)]; got = [[] for _ in range(N)]
for i in range(N): DataWatch(cl[i], '/app', (lambda i: lambda d, s: got[i].append((time.perf_counter(), d)))(i))
time.sleep(0.5)
for g in got: g.clear()
old = adm.get('/hist/app/ver-0000000001')[0]; t0 = time.perf_counter(); adm.set('/app', old); t1 = time.perf_counter()
time.sleep(0.5); lat = [(g[-1][0] - t0) * 1000 for g in got if g and g[-1][1] == old]
print(f'  回滚(把 ver-0000000001 的内容写回 /app):写入耗时 {(t1-t0)*1000:.1f} ms;{len(lat)} / {N} 个实例收到旧值,最晚 {max(lat):.1f} ms')
R['rollback'] = dict(ok=len(lat), n=N, last=max(lat), write=(t1 - t0) * 1000)
print()
print('== 四:一次改两个配置项:拆成两个节点(multi 原子提交)vs 同一个 JSON 节点;读者分两次读两个节点,会不会读到「半新半旧」')
for p in ('/a', '/b', '/j'): adm.create(p, b'0')
stop = threading.Event(); tc = threading.Thread(target=lambda: None)
def writer():
    k = 0
    while not stop.is_set():
        k += 1; t = adm.transaction(); t.set_data('/a', str(k).encode()); t.set_data('/b', str(k).encode()); t.commit(); adm.set('/j', json.dumps({'a': k, 'b': k}).encode())
wt = threading.Thread(target=writer); rc = client('127.0.0.1:7300'); wt.start(); tear = 0; two = 0; t_end = time.time() + 5
while time.time() < t_end:
    a_ = rc.get('/a')[0]; b_ = rc.get('/b')[0]; two += 1
    if a_ != b_: tear += 1
stop.set(); wt.join()
jt = 0; jn = 0; stop.clear(); wt = threading.Thread(target=writer); wt.start(); t_end = time.time() + 3
while time.time() < t_end:
    d = json.loads(rc.get('/j')[0]); jn += 1
    if d['a'] != d['b']: jt += 1
stop.set(); wt.join()
print(f'  两个节点(写入用 multi 原子提交)、读者分两次 get:{two} 次读取里有 {tear} 次读到 a≠b;单个 JSON 节点:{jn} 次读取里 {jt} 次不一致')
R['torn'] = dict(reads=two, torn=tear, jreads=jn, jtorn=jt)
for x in cl + [rc]: x.stop()
adm.stop(); n.stop(); save('z86', R); os._exit(0)
