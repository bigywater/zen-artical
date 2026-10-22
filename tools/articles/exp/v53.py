import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import shutil, base64, urllib.parse
tee('v53'); reset()
print('Consul 的 KV 与 session 锁。Consul 2.0.4,3 个 server + 2 个 client agent(全部在 127.0.0.1)。KV 的版本号(ModifyIndex)与 CAS、阻塞查询,session(TTL、行为、lock-delay)与基于 session 的锁,以及持有者所在节点故障时锁什么时候能被别人拿到。用我自己的几行 Python 当客户端,不是 consul 的 lock 命令,也不是任何 SDK')
for n in ('v53c', 'v53a0', 'v53a1'):
    for i in range(3): shutil.rmtree(TT / f'{n}_{i}', ignore_errors=True)
    shutil.rmtree(TT / n, ignore_errors=True)
CC = ConsulCluster('v53c', 3).start()
A0 = ConsulAgent('v53a0', CC).start(); A1 = ConsulAgent('v53a1', CC).start(); time.sleep(2.0)
EOFS = collections.Counter()
def req(port, method, path, body=None, timeout=10.0):
    # 经 client agent 的请求偶尔会得到 HTTP 500 “rpc error making call: EOF”(agent 到 server 的复用连接已经被对端关了);重试一次,并计数
    for attempt in range(4):
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
        try:
            c.request(method, path, body=(body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode())); r = c.getresponse(); d = r.read()
            if r.status == 500 and b'EOF' in d and attempt < 3 and not path.startswith('/v1/kv/w?index'): EOFS[f'{method} 重试'] += 1; continue
            return r.status, dict(r.getheaders()), d
        finally: c.close()
def J(d):
    try: return json.loads(d)
    except Exception: return None
P0, P1 = A0.p['http'], A1.p['http']
def kget(port, key, timeout=10.0, **q):
    s, h, d = req(port, 'GET', f'/v1/kv/{key}' + ('?' + urllib.parse.urlencode(q) if q else ''), timeout=timeout)
    j = J(d) if s == 200 else None
    return s, h, (j[0] if j else None)
def kval(e): return base64.b64decode(e['Value']).decode() if e and e.get('Value') else None
def kput(port, key, val, **q):
    s, h, d = req(port, 'PUT', f'/v1/kv/{key}' + ('?' + urllib.parse.urlencode(q) if q else ''), val.encode() if isinstance(val, str) else val)
    return d.strip() == b'true'
def sess_create(port, **body):
    s, h, d = req(port, 'PUT', '/v1/session/create', body); assert s == 200, (s, d); return J(d)['ID']

# ============ 一 ============
print('== 一:KV 与 CAS。每个 key 有 CreateIndex / ModifyIndex(全局递增的 Raft 索引)。?cas=0 只在 key 不存在时写入;?cas=N 只在 ModifyIndex 等于 N 时写入。再比较 8 个线程各给同一个计数器加 50 次(应得 400):GET 后 PUT(没有保护)与 GET 后 PUT ?cas=ModifyIndex(失败就重读重试)')
rows = []
rows.append(('PUT cas=0(key 不存在)', kput(P0, 'a', 'v1', cas=0)))
rows.append(('PUT cas=0(key 已存在)', kput(P0, 'a', 'v2', cas=0)))
_, _, e = kget(P0, 'a'); ci, mi = e['CreateIndex'], e['ModifyIndex']
rows.append((f'PUT cas={mi + 1000}(不是当前 ModifyIndex)', kput(P0, 'a', 'v3', cas=mi + 1000)))
rows.append((f'PUT cas={mi}(当前 ModifyIndex)', kput(P0, 'a', 'v4', cas=mi)))
_, _, e2 = kget(P0, 'a')
table([(a, '成功' if b else '失败(返回 false)') for a, b in rows], ['操作', '结果'])
print(f'  CAS 成功之后 ModifyIndex 从 {mi} 变到 {e2["ModifyIndex"]},CreateIndex 保持 {e2["CreateIndex"]}(= {ci}),值 {kval(e2)!r}')
def run_counter(use_cas, workers=8, per=50):
    kput(P0, 'cnt', '0'); attempts = [0] * workers
    def w(i):
        for _ in range(per):
            while True:
                attempts[i] += 1
                _, _, e = kget(P0, 'cnt'); v = int(kval(e)) + 1
                if not use_cas: kput(P0, 'cnt', str(v)); break
                if kput(P0, 'cnt', str(v), cas=e['ModifyIndex']): break
    t0 = time.perf_counter(); par(w, list(range(workers)), workers); dt = time.perf_counter() - t0
    return int(kval(kget(P0, 'cnt')[2])), sum(attempts), dt
r1 = run_counter(False); r2 = run_counter(True)
table([('GET 后 PUT(没有保护)', r1[0], r1[1], f'{r1[2]:.2f}'), ('GET 后 PUT ?cas=ModifyIndex', r2[0], r2[1], f'{r2[2]:.2f}')], ['写法', '最终值(应得 400)', '一共读-写了多少次', '用时 s'])
print('  没有 CAS 时读-改-写互相覆盖,丢更新;CAS 保证了最终值正确,代价是冲突的线程要重试(读-写次数比 400 多的部分就是白做的)')

# ============ 二 ============
print('== 二:阻塞查询(watch 的基础)。GET /v1/kv/k?index=N&wait=W:没有变化就挂起到 W 到期,有变化立刻返回。测:无变化时实际挂起多久(wait=2s,5 次);写入发生在第 1 秒时多久返回;以及写得比 watcher 轮询快时,watcher 能看到多少个中间值')
kput(P0, 'w', 'v0'); _, h, e = kget(P0, 'w'); idx = int(h['X-Consul-Index'])
dts = []
for _ in range(5):
    t0 = time.perf_counter(); s, h2, d = req(P0, 'GET', f'/v1/kv/w?index={idx}&wait=2s'); dts.append(time.perf_counter() - t0)
print(f'  无变化:wait=2s,5 次实际返回用时 {", ".join(f"{x:.2f}" for x in dts)} s;返回的 X-Consul-Index {"与请求的相同" if int(h2["X-Consul-Index"]) == idx else "不同"}')
res = []
for _ in range(3):
    _, h, e = kget(P0, 'w'); idx = int(h['X-Consul-Index'])
    wres = []
    threading.Timer(1.0, lambda: wres.append(kput(P1, 'w', 'changed-' + str(time.time())))).start()
    t0 = time.perf_counter(); s, h2, d = req(P0, 'GET', f'/v1/kv/w?index={idx}&wait=10s', timeout=20.0); dt_ = time.perf_counter() - t0; time.sleep(0.3); res.append((dt_, int(h2['X-Consul-Index']) > idx and wres == [True]))
print(f'  写入发生在 1 s 之后(经另一个 agent 写):3 次返回用时 {", ".join(f"{x[0]:.2f}" for x in res)} s,索引都变大且写入成功:{all(x[1] for x in res)}')
kput(P0, 'wf', 'v0'); seen = []; stop = threading.Event(); _, h, e = kget(P0, 'wf'); last = int(h['X-Consul-Index'])
def watcher():
    global last
    while not stop.is_set():
        try: s, h, d = req(P0, 'GET', f'/v1/kv/wf?index={last}&wait=2s', timeout=5.0)
        except Exception: continue
        if s != 200: continue
        ni = int(h['X-Consul-Index']); 
        if ni != last: seen.append(kval(J(d)[0])); last = ni
th = threading.Thread(target=watcher, daemon=True); th.start(); time.sleep(0.2)
for rate_ms, n in ((100, 20), (2, 200)):
    seen.clear()
    for i in range(n): kput(P1, 'wf', f'r{rate_ms}-{i}'); time.sleep(rate_ms / 1000)
    time.sleep(1.0); print(f'  顺序写,每 {rate_ms} ms 一次,共 {n} 次:watcher 看到 {len(seen)} 次变化,最后看到的值 {seen[-1] if seen else None!r}(最后写入的是 r{rate_ms}-{n - 1})')
seen.clear(); W, PER = 8, 50
def wr(i):
    for k in range(PER): kput(P1, 'wf', f'c{i}-{k}')
par(wr, list(range(W)), W); time.sleep(1.0)
print(f'  {W} 个线程并发写,每个 {PER} 次,共 {W * PER} 次:watcher 看到 {len(seen)} 次变化(写入 {W * PER} 次),最后看到的值是 key 里最终的值:{seen[-1] == kval(kget(P0, "wf")[2])}')
seen.clear()
ops = [{'KV': {'Verb': 'set', 'Key': 'wf', 'Value': base64.b64encode(f'txn-{k}'.encode()).decode()}} for k in range(10)]
s_, h_, d_ = req(P1, 'PUT', '/v1/txn', ops); time.sleep(1.0)
print(f'  一个事务(/v1/txn)里对同一个 key 连续 set 10 次:HTTP {s_},watcher 看到 {len(seen)} 次变化,值 {seen!r}')
stop.set()
print('  阻塞查询返回的是“返回那一刻的最新值和索引”,不是变化的流水:能不能看到每个中间值,取决于写入和 watcher 重新发起查询的相对速度(etcd 的 watch 是事件流,见第 42 篇)')

# ============ 三 ============
print('== 三:session 锁的基本规则。session A、B、C(TTL 15s,行为 release,lock-delay 0s):PUT /v1/kv/lock?acquire=<session> 成功返回 true,别人持有时返回 false;持有者 ?release 之后别人可以立刻拿;LockIndex 每次被拿到都加 1;再看行为 delete 与 release 在 session 销毁后 key 的去向')
sA = sess_create(P0, Name='A', TTL='15s', LockDelay='0s'); sB = sess_create(P0, Name='B', TTL='15s', LockDelay='0s'); sC = sess_create(P0, Name='C', TTL='15s', LockDelay='0s')
rows = []
rows.append(('A acquire', kput(P0, 'lock', 'A', acquire=sA)))
rows.append(('B acquire(A 持有时)', kput(P0, 'lock', 'B', acquire=sB)))
_, _, e = kget(P0, 'lock'); rows.append(('GET lock', f'Session 是 A: {e["Session"] == sA},LockIndex {e["LockIndex"]},值 {kval(e)!r}'))
rows.append(('B release(不是持有者)', kput(P0, 'lock', 'B', release=sB)))
rows.append(('A release', kput(P0, 'lock', 'A', release=sA)))
_, _, e = kget(P0, 'lock'); rows.append(('GET lock', f'Session {e.get("Session")!r},LockIndex {e["LockIndex"]}'))
rows.append(('B acquire(释放之后)', kput(P0, 'lock', 'B', acquire=sB)))
kput(P0, 'lock', 'B', release=sB); rows.append(('C acquire', kput(P0, 'lock', 'C', acquire=sC)))
_, _, e = kget(P0, 'lock'); rows.append(('GET lock', f'LockIndex {e["LockIndex"]}'))
table([(a, '成功' if b is True else ('失败(返回 false)' if b is False else b)) for a, b in rows], ['操作', '结果'])
kput(P0, 'lock', 'C', release=sC)
class Resource:
    def __init__(s): s.max, s.log = 0, []
    def write(s, token, who):
        ok = token >= s.max
        if ok: s.max = token
        s.log.append((who, token, ok)); return ok
R = Resource(); R.write(1, 'A'); R.write(2, 'B'); R.write(1, 'A(已经被换掉)')
print(f'  LockIndex 当围栏令牌用的演示(资源自己记住见过的最大令牌,我写的几行,不是 Consul 的功能):{R.log}')
sD = sess_create(P0, Name='D', TTL='15s', Behavior='delete', LockDelay='0s'); sR = sess_create(P0, Name='R', TTL='15s', Behavior='release', LockDelay='0s')
kput(P0, 'k-del', 'x', acquire=sD); kput(P0, 'k-rel', 'x', acquire=sR)
req(P0, 'PUT', f'/v1/session/destroy/{sD}'); req(P0, 'PUT', f'/v1/session/destroy/{sR}'); time.sleep(0.3)
sd, _, ed = kget(P0, 'k-del'); sr, _, er = kget(P0, 'k-rel')
table([('Behavior=delete', f'GET 返回 HTTP {sd}(key 被删除)' if ed is None else f'key 还在,Session={ed.get("Session")!r}'), ('Behavior=release', f'GET 返回 HTTP {sr}(key 被删除)' if er is None else f'key 还在,Session={er.get("Session")!r},LockIndex {er["LockIndex"]},值 {kval(er)!r}')], ['session 被销毁后', 'key 的去向'])

# ============ 四 ============
print('== 四:session 的 TTL。session 的 TTL 是 10 s(最小值):(a)创建后不续约;(b)每 3 s 续约(PUT /v1/session/renew);(c)没有 TTL(只靠节点的 serfHealth 检查)且持有者“死了”(不续约也不释放)。各自持有一把锁(lock-delay 0s),每 0.1 s 看一次 session 还在不在,最多 45 s')
sa = sess_create(P0, Name='a', TTL='10s', LockDelay='0s'); sb = sess_create(P0, Name='b', TTL='10s', LockDelay='0s'); sc = sess_create(P0, Name='c', LockDelay='0s')
for k, sid in (('ka', sa), ('kb', sb), ('kc', sc)): kput(P0, k, 'x', acquire=sid)
t0 = time.perf_counter(); gone = {}; nxt = t0 + 3
while time.perf_counter() - t0 < 45:
    now = time.perf_counter()
    if now >= nxt:
        if 'b' not in gone: req(P0, 'PUT', f'/v1/session/renew/{sb}')
        nxt += 3
    for nm, sid in (('a', sa), ('b', sb), ('c', sc)):
        if nm in gone: continue
        s, h, d = req(P0, 'GET', f'/v1/session/info/{sid}')
        if not J(d): gone[nm] = time.perf_counter() - t0
    if 'a' in gone: break
    time.sleep(0.1)
t_a = gone.get('a'); 
while time.perf_counter() - t0 < 45:
    now = time.perf_counter()
    if now >= nxt: req(P0, 'PUT', f'/v1/session/renew/{sb}'); nxt += 3
    for nm, sid in (('b', sb), ('c', sc)):
        if nm in gone: continue
        s, h, d = req(P0, 'GET', f'/v1/session/info/{sid}')
        if not J(d): gone[nm] = time.perf_counter() - t0
    time.sleep(0.1)
_, _, ea = kget(P0, 'ka'); _, _, eb = kget(P0, 'kb'); _, _, ec = kget(P0, 'kc')
table([('(a)TTL 10 s,不续约', f'{gone["a"]:.1f} s 后 session 消失' if 'a' in gone else '45 s 内没消失', f'锁 Session={ea.get("Session")!r}'), ('(b)TTL 10 s,每 3 s 续约', f'{gone["b"]:.1f} s 后消失' if 'b' in gone else '45 s 内一直在', f'锁仍被持有:{eb.get("Session") == sb}'), ('(c)没有 TTL,持有者死了', f'{gone["c"]:.1f} s 后消失' if 'c' in gone else '45 s 内一直在', f'锁仍被持有:{ec.get("Session") == sc}')], ['session', '结果', '锁'])
print('  不设 TTL 的 session 只和节点的存活挂钩:持有者进程死了而 agent 还活着,锁就一直占着;所以要用锁的话应该设 TTL 并让持有者续约')

# ============ 五 ============
print('== 五:lock-delay。持有者的 session 被销毁(这是“非自愿”释放,和持有者自己 release 不同),在 lock-delay 之内别人拿不到这把锁。session 创建时 lock-delay 分别为 0s、3s、不写(默认);session 销毁之后 B 每 0.1 s 尝试 acquire,记录 B 第一次成功的时间')
rows = []
for nm, ld in (('0s', '0s'), ('3s', '3s'), ('default', None)):
    body = dict(Name='holder', TTL='15s'); 
    if ld: body['LockDelay'] = ld
    sh_ = sess_create(P0, **body); sb_ = sess_create(P0, Name='b', TTL='60s', LockDelay='0s'); key = 'ld-' + nm
    assert kput(P0, key, 'x', acquire=sh_)
    req(P0, 'PUT', f'/v1/session/destroy/{sh_}'); t0 = time.perf_counter(); ok = None
    while time.perf_counter() - t0 < 30:
        if kput(P0, key, 'y', acquire=sb_): ok = time.perf_counter() - t0; break
        time.sleep(0.1)
    rows.append((nm if ld else '不写(默认)', f'{ok:.2f} s' if ok is not None else '30 s 内没拿到'))
    req(P0, 'PUT', f'/v1/session/destroy/{sb_}')
table(rows, ['持有者 session 的 lock-delay', '销毁后 B 第一次拿到锁的时间'])
print('  lock-delay 是给“前任持有者可能还没发现自己失效”留的缓冲:没有它,新持有者和前任可能同时认为自己在持锁。它保护的是前任,代价是切换变慢')

# ============ 六 ============
print('== 六:持有者所在节点故障时的切换。A 的 session 建在 client agent v53a1 上(TTL 10s),持有 leader 锁;B 在 v53a0 上每 0.1 s 尝试 acquire。SIGKILL v53a1:记录从杀掉到 session 消失(锁被释放)的时间,和 B 拿到锁的时间。做两种 lock-delay:默认(不写)和 1s。每种之后重启 v53a1')
rows = []
for nm, ld in (('default', None), ('1s', '1s')):
    body = dict(Name='A', TTL='10s'); 
    if ld: body['LockDelay'] = ld
    sa_ = sess_create(P1, **body); sb_ = sess_create(P0, Name='B', TTL='60s', LockDelay='0s'); key = 'leader-' + nm
    assert kput(P1, key, 'A', acquire=sa_); assert not kput(P0, key, 'B', acquire=sb_)
    t0 = time.perf_counter(); A1.kill(); t_gone = None; t_b = None
    while time.perf_counter() - t0 < 90:
        if t_gone is None:
            _, _, e = kget(P0, key)
            if e and not e.get('Session'): t_gone = time.perf_counter() - t0
        if kput(P0, key, 'B', acquire=sb_): t_b = time.perf_counter() - t0; break
        time.sleep(0.1)
    rows.append((nm if ld else '不写(默认)', f'{t_gone:.1f} s' if t_gone is not None else '-', f'{t_b:.1f} s' if t_b is not None else '90 s 内没拿到'))
    req(P0, 'PUT', f'/v1/session/destroy/{sb_}'); A1.start(); time.sleep(3.0)
table(rows, ['A 的 lock-delay', '杀掉节点到 A 的锁被释放', '杀掉节点到 B 拿到锁'])
print('  节点被杀之后要先等 gossip 判它 failed(serfHealth 变 critical,第 52 篇量过),session 才被作废、锁才释放,然后还要等 lock-delay;总时间 = 这两段相加')

A0.kill(); A1.kill(); CC.stop_all()
print(f'  (附注)经 client agent 的请求遇到 HTTP 500 “rpc error making call: EOF” 并重试的次数:{sum(EOFS.values())}(重试后都成功了才继续;没有成功的会让实验直接中止)')
print('ERRORS', dict(ERRORS))
