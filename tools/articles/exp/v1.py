import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import functools; rpc = functools.partial(rpc, keepalive=False)      # 本篇沿用每次调用新建一条连接的写法(连接总数只有几千,不会用光临时端口)
import zlib, queue
tee('v1'); reset()
print('一条调用链 client → A → B → C,全部是本进程里起的小 HTTP 服务(Python http.server,线程化);下游的“耗时”用 sleep 模拟,哪些请求慢由请求编号的 crc32 决定,所以对照的两种策略面对完全相同的慢请求;client 的总预算是 1000 ms;“传播截止时间”= 每一跳把剩余预算放进 X-Remaining-Ms 请求头传给下一跳(和 gRPC 的 grpc-timeout 头一个意思)')

def qid(h): return int(h.path.split('id=')[1].split('&')[0])
def h100(i, salt): return zlib.crc32(f'{i}|{salt}'.encode()) % 100
def remaining(h):
    v = h.headers.get('X-Remaining-Ms'); return float(v) / 1000 if v is not None else None

def hop(next_port, fixed_to, propagate):
    """中间一跳:调用下游。fixed:自己固定的超时;propagate:min(自己的超时, 剩余预算 - 20 ms),并把新的剩余预算传下去。"""
    def app(h):
        t0 = time.perf_counter(); rem = remaining(h); i = qid(h); to = fixed_to; hd = {}
        if propagate and rem is not None:
            to = min(fixed_to, rem - 0.02)
            if to <= 0: return h.reply(504, b'budget')
            hd = {'X-Remaining-Ms': f'{(rem - 0.02) * 1000:.0f}'}
        st, body, dt = rpc(next_port, f'/?id={i}', to, hd); h.reply(200 if st == 200 else 504, b'ok' if st == 200 else str(st).encode())
    return app

# ============ 一:固定超时 vs 传播截止时间 ============
print('== 一:固定超时 vs 传播截止时间。C 有 30% 的请求要 1500 ms(其余 100 ms)。200 个请求、20 个并发。比较:每一跳各自固定 1000 ms 超时(互不知情)与每一跳传播剩余预算(C 干活时每 10 ms 看一眼剩余预算,没了就停)')
def run1(propagate):
    stats = {'work_ms': 0.0, 'late_done': 0, 'full': 0}; lk = threading.Lock(); starts = {}
    def c_app(h):
        i = qid(h); rem = remaining(h); work = 1.5 if h100(i, 'c') < 30 else 0.1; t0 = time.time(); done = 0.0
        if propagate and rem is not None:
            if rem <= 0: return h.reply(504, b'budget')
            while done < work and (time.time() - t0) < rem: time.sleep(0.01); done += 0.01
            with lk: stats['work_ms'] += done * 1000
            if done < work: return h.reply(504, b'budget')
        else:
            time.sleep(work); done = work
            with lk: stats['work_ms'] += done * 1000
        with lk:
            stats['full'] += 1
            if time.time() > starts[i] + 1.0: stats['late_done'] += 1
        h.reply(200, b'ok')
    C = Svc(c_app); B = Svc(hop(C.port, 1.0, propagate)); A = Svc(hop(B.port, 1.0, propagate))
    def one(i):
        starts[i] = time.time(); hd = {'X-Remaining-Ms': '1000'} if propagate else {}
        st, _, dt = rpc(A.port, f'/?id={i}', 1.0, hd); return st, dt
    t0 = time.perf_counter(); res = par(one, list(range(200)), 20); wall = time.perf_counter() - t0
    time.sleep(1.8)
    ok = sum(1 for st, _ in res if st == 200); to = sum(1 for st, _ in res if st == 'timeout'); other = 200 - ok - to
    for s in (A, B, C): s.stop()
    return ok, to, other, stats
rows = []
for name, prop in (('每一跳固定 1000 ms 超时', False), ('传播剩余预算', True)):
    ok, to, other, st = run1(prop)
    slow = sum(1 for i in range(200) if h100(i, 'c') < 30)
    rows.append((name, ok, to, other, f"{st['work_ms'] / 1000:.1f} s", st['full'], st['late_done']))
table(rows, ['策略', 'client 1 s 内拿到结果', 'client 超时', '拿到 504', 'C 花在干活上的总时间', 'C 把活干完的次数', '干完时 client 早已放弃的次数'])
print(f'  这 200 个请求里按随机数事先数出来有 {slow} 个会让 C 慢(1500 ms);1500 ms 的活在 1000 ms 的预算里本来就做不完,所以不论什么策略,这 {slow} 个都拿不到结果;区别是 C 要不要把它们干完')

# ============ 二:B 重试 C ============
print('== 二:重试吃掉预算。C 一直很慢(1500 ms),B 最多对 C 试 3 次、每次 500 ms 超时。client 总预算 1000 ms。比较固定的每次 500 ms 与“每次不超过剩余预算”;40 个请求、10 个并发')
def run2(propagate):
    att = []; lk = threading.Lock(); starts = {}
    def c_app(h):
        i = qid(h)
        with lk: att.append(time.time() - starts[i])
        time.sleep(1.5); h.reply(200, b'ok')
    def b_app(h):
        t0 = time.perf_counter(); i = qid(h); rem = remaining(h) if propagate else None
        for k in range(3):
            to = 0.5; hd = {}
            if propagate:
                left = rem - (time.perf_counter() - t0)
                if left < 0.05: break
                to = min(0.5, left - 0.02); hd = {'X-Remaining-Ms': f'{(left - 0.02) * 1000:.0f}'}
            st, _, _ = rpc(C.port, f'/?id={i}', to, hd)
            if st == 200: return h.reply(200, b'ok')
        h.reply(504, b'gave up')
    C = Svc(c_app); B = Svc(b_app)
    def one(i):
        starts[i] = time.time(); hd = {'X-Remaining-Ms': '1000'} if propagate else {}
        return rpc(B.port, f'/?id={i}', 1.0, hd)[::2]
    res = par(one, list(range(40)), 10); time.sleep(1.8)
    got = sum(1 for st, _ in res if st == 504); to = sum(1 for st, _ in res if st == 'timeout')
    lat = [dt for st, dt in res]; late = sum(1 for a in att if a > 1.0)
    for s in (B, C): s.stop()
    return got, to, pct(lat, 50), len(att), late
rows = []
for name, prop in (('固定:每次 500 ms,最多 3 次', False), ('每次 ≤ 剩余预算', True)):
    got, to, p50, n_att, late = run2(prop)
    rows.append((name, got, to, f'{p50 * 1000:.0f} ms', n_att, late))
table(rows, ['B 的策略', 'client 在 1 s 内得到 B 的回复(504)', 'client 超时(什么也没等到)', 'client 看到的延迟中位数', 'C 一共收到的调用', '其中 client 放弃之后才发来的'])

# ============ 三:逐跳分预算 ============
print('== 三:三个串行的下游 S1、S2、S3(A 依次调用),每个正常 100 ms、5% 的请求在这一跳要 600 ms;总预算 1000 ms。比较:把预算平分(每跳 333 ms 超时)与整条链共用剩余预算。400 个请求、40 个并发')
def run3(shared):
    def s_app(salt):
        def app(h):
            i = qid(h); time.sleep(0.6 if h100(i, salt) < 5 else 0.1); h.reply(200, b'ok')
        return app
    S = [Svc(s_app(f's{k}')) for k in range(3)]
    def a_app(i):
        t0 = time.perf_counter()
        for k in range(3):
            to = (1.0 - (time.perf_counter() - t0)) if shared else 1.0 / 3
            if to <= 0: return 'budget'
            st, _, _ = rpc(S[k].port, f'/?id={i}', to)
            if st != 200: return f'fail@{k + 1}'
        return 'ok'
    def one(i):
        t0 = time.perf_counter(); r = a_app(i); return r, time.perf_counter() - t0
    res = par(one, list(range(400)), 40); [s.stop() for s in S]
    ok = [dt for r, dt in res if r == 'ok' and dt <= 1.0]
    return len(ok), pct(ok, 50), pct(ok, 99)
slow1 = sum(1 for i in range(400) if any(h100(i, f's{k}') < 5 for k in range(3)))
slow2 = sum(1 for i in range(400) if sum(h100(i, f's{k}') < 5 for k in range(3)) >= 2)
rows = []
for name, sh_ in (('预算平分:每跳 333 ms', False), ('共用剩余预算:每跳最多用掉剩下的', True)):
    n, p50, p99 = run3(sh_); rows.append((name, f'{n} / 400', f'{n / 4:.1f}%', f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms'))
table(rows, ['策略', '1 s 内成功', '成功率', '成功请求延迟中位数', '成功请求延迟 p99'])
print(f'  按随机数事先数出来:至少一跳慢的请求 {slow1} 个(平分必败),至少两跳慢的请求 {slow2} 个(共用预算也会超过 1000 ms:600 + 600 > 1000)')

# ============ 四:排队 ============
print('== 四:排队里的请求超过截止时间就别处理。一个服务只有一个 worker、每个请求要 20 ms(容量 50/s),到达率 80/s 持续 5 秒共 400 个请求;每个请求的截止时间是 400 ms(client 超时也是 400 ms;为了让“处理完时 client 是否已经放弃”算得准,这一节把绝对截止时刻放进 X-Deadline 头,client 和服务在同一台机器上所以时钟一致,真实系统里传的是剩余时间)。比较:来者不拒(排到了就处理)与出队时发现剩余时间不够 20 ms 就直接丢掉')
def run4(drop_expired):
    Q = queue.Queue(); proc = {'n': 0, 'late': 0, 'skipped': 0}; stop = threading.Event()
    def worker():
        while not stop.is_set():
            try: ev, dl = Q.get(timeout=0.1)
            except queue.Empty: continue
            if drop_expired and dl - time.time() < 0.02: proc['skipped'] += 1; ev['code'] = 504; ev['e'].set(); continue
            time.sleep(0.02); proc['n'] += 1
            if time.time() > dl: proc['late'] += 1
            ev['code'] = 200; ev['e'].set()
    threading.Thread(target=worker, daemon=True).start()
    def app(h):
        ev = {'e': threading.Event(), 'code': None}; Q.put((ev, float(h.headers['X-Deadline']))); ev['e'].wait(); h.reply(ev['code'], b'x')
    S = Svc(app, backlog=1024)
    res = openloop(lambda i: rpc(S.port, '/', 0.4, {'X-Deadline': repr(time.time() + 0.4)}), 80, 5.0, workers=400)
    time.sleep(2.0); stop.set()
    ok = sum(1 for _, (st, _b, dt) in res if st == 200 and dt <= 0.4); r504 = sum(1 for _, (st, _b, dt) in res if st == 504); to = len(res) - ok - r504
    S.stop(); return ok, to, r504, proc
rows = []
for name, d in (('来者不拒', False), ('出队时丢掉已过期的', True)):
    ok, to, r504, p = run4(d)
    rows.append((name, ok, to, r504, p['n'], p['late'], p['skipped']))
table(rows, ['策略', '400 ms 内成功', 'client 超时(或晚于 400 ms)', '收到 504', 'worker 实际处理的请求', '处理完时已超过截止时刻的', '直接丢掉的'])
print('  来者不拒时,队列越排越长,排到的请求已经过了截止时间,worker 白干;出队时检查截止时间,把时间花在还有人在等的请求上')
