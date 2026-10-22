import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v46'); reset()
print('服务实例下线的几种方式对客户端错误的影响。3 个实例(本进程里的 Python 服务,每个请求处理 0.2 s),一个注册中心(我写的几十行 Python:登记带 TTL 的实例,过期的惰性剔除),client 侧负载均衡:每 R 秒从注册中心拉一次实例列表并缓存,请求轮询缓存里的实例。client 以 60 个请求/秒的开环速率发 8 秒,第 3 秒让其中一个实例下线,统计错误请求(连接被拒、连接被断开或超时)')
class Reg:
    def __init__(s): s.d = {}; s.lk = threading.Lock()
    def register(s, iid, port, ttl): 
        with s.lk: s.d[iid] = (port, time.perf_counter() + ttl, ttl)
    def beat(s, iid):
        with s.lk:
            if iid in s.d: p, e, ttl = s.d[iid]; s.d[iid] = (p, time.perf_counter() + ttl, ttl)
    def dereg(s, iid):
        with s.lk: s.d.pop(iid, None)
    def list(s):
        now = time.perf_counter()
        with s.lk: return [(i, p) for i, (p, e, t) in s.d.items() if e > now]
class Inst:
    def __init__(s, reg, iid, ttl):
        s.reg, s.iid, s.ttl = reg, iid, ttl; s.inflight = 0; s.lk = threading.Lock(); s.alive = True
        def app(h):
            with s.lk: s.inflight += 1
            try: time.sleep(0.2); h.reply(200, iid.encode())
            finally:
                with s.lk: s.inflight -= 1
        s.svc = Svc(app, backlog=64); reg.register(iid, s.svc.port, ttl); threading.Thread(target=s._hb, daemon=True).start()
    def _hb(s):
        while s.alive: s.reg.beat(s.iid); time.sleep(s.ttl / 3)
    def crash(s): s.alive = False; s.svc.stop()                      # 进程直接没了:心跳停止,监听和已建立的连接全部断开,没有注销
    def graceful(s):                                                 # 优雅退出:关监听口(不再接新连接),等在途请求处理完再退
        s.svc.srv.shutdown(); s.svc.srv.server_close(); t0 = time.perf_counter()
        while s.inflight and time.perf_counter() - t0 < 5: time.sleep(0.01)
        s.alive = False
def run(mode, ttl=2.0, R=1.0, drain=0.0, retry=False, rate=60, dur=8.0):
    reg = Reg(); ins = [Inst(reg, f'i{k}', ttl) for k in range(3)]; cache = [reg.list()]; stop = threading.Event(); rr = [0]; lk = threading.Lock()
    def refresher():
        while not stop.is_set(): cache[0] = reg.list(); time.sleep(R)
    threading.Thread(target=refresher, daemon=True).start(); time.sleep(0.1)
    def offline():
        time.sleep(3.0); t = ins[0]
        if mode == 'crash': t.crash()
        elif mode == 'dereg_stop': reg.dereg('i0'); time.sleep(drain); t.crash()
        elif mode == 'dereg_graceful': reg.dereg('i0'); time.sleep(drain); t.graceful()
    threading.Thread(target=offline, daemon=True).start()
    attempts = [0]
    def one(i):
        n = 0
        for tries in range(2 if retry else 1):
            lst = cache[0]
            if not lst: break
            with lk: rr[0] += 1; k = rr[0]
            iid, port = lst[k % len(lst)]; n += 1; st, b, dt = rpc(port, '/', 1.0, keepalive=False)
            if st == 200: attempts[0] += n; return 'ok'
        attempts[0] += n; return 'err'
    res = openloop(one, rate, dur, workers=200); stop.set()
    for t in ins:
        try: t.alive = False; t.svc.stop()
        except Exception: pass
    errs = sum(1 for ts, r in res if r == 'err'); times = [ts for ts, r in res if r == 'err']
    return errs, len(res), (min(times), max(times)) if times else None, attempts[0] / max(1, len(res))
def fmt(r): return f'{r[0]} / {r[1]}', (f'{r[2][0]:.1f} ~ {r[2][1]:.1f} s' if r[2] else '-'), f'{r[3]:.2f}'

# ============ 一 ============
print('== 一:不注销直接崩溃(kill 进程)。实例的 TTL 和 client 拉取列表的间隔 R 决定了 client 还会把请求发给死实例多久。TTL 分别是 1 / 2 / 4 s,R 分别是 0.5 / 1 s;client 不重试。第 3 秒崩溃,看错误请求数和它们发生的时间范围')
rows = []
for ttl in (1.0, 2.0, 4.0):
    for R in (0.5, 1.0):
        r = run('crash', ttl=ttl, R=R); rows.append((f'TTL {ttl:g} s · R {R:g} s',) + fmt(r))
table(rows, ['配置', '错误请求 / 总数', '错误发生的时间范围', '平均每个请求尝试几次'])
print('  死实例在 client 缓存里存在的时间 ≈ 注册中心发现它(TTL 内)加上下一次拉取(≤ R):TTL 和 R 越大,错误越多;每秒 60 个请求、轮询 3 个实例,发给死实例的约 20 个/秒,错误数 ≈ 20 × (从崩溃到缓存更新的秒数)')

# ============ 二 ============
print('== 二:先注销再停。实例先从注册中心注销,等 drain 秒之后再停(a:直接 kill;b:优雅退出——关监听、等在途请求处理完)。TTL 2 s,R = 1 s,client 不重试。drain 取 0 / 1.2 / 2.5 s(R 的 0 / 约 1 / 约 2.5 倍)。在途请求 0.2 s,看错误数')
rows = []
for mode, mname in (('dereg_stop', '注销后 kill'), ('dereg_graceful', '注销后优雅退出')):
    for drain in (0.0, 1.2, 2.5):
        r = run(mode, ttl=2.0, R=1.0, drain=drain); rows.append((f'{mname} · 等待 {drain:g} s',) + fmt(r))
table(rows, ['做法', '错误请求 / 总数', '错误发生的时间范围', '平均每个请求尝试几次'])
print('  注销之后 client 的缓存里还有这个实例,最长 R 秒:drain 小于 R 时,这段时间里发给它的请求落在已经停掉的实例上;drain 大于 R 之后(client 的缓存已更新)再停,就不会有请求发给它。优雅退出还解决另一件事:在途请求(0.2 s)是被处理完还是被掐断——kill 会让注销瞬间在途的请求失败')

# ============ 三 ============
print('== 三:client 重试能补多少。同样的崩溃(TTL 2 s,R 1 s),client 遇到连接错误就换列表里下一个实例重试一次,对比不重试。再看先注销再优雅退出(drain = 2.5 s)的错误,两者结合')
rows = []
for name, kw in (('崩溃 · 不重试', dict(mode='crash')), ('崩溃 · 重试一次', dict(mode='crash', retry=True)), ('注销后立刻 kill · 不重试', dict(mode='dereg_stop', drain=0.0)), ('注销后立刻 kill · 重试一次', dict(mode='dereg_stop', drain=0.0, retry=True)), ('注销 + 等 2.5 s + 优雅退出 · 不重试', dict(mode='dereg_graceful', drain=2.5))):
    r = run(ttl=2.0, R=1.0, **kw); rows.append((name,) + fmt(r))
table(rows, ['做法', '错误请求 / 总数', '错误发生的时间范围', '平均每个请求尝试几次'])
print('  重试把用户可见的错误降到很低,代价是对死实例多发的那些尝试(右列);最彻底的是不让请求去到死实例:先注销、等 client 缓存更新、再优雅退出,错误为 0 而且不需要重试')
