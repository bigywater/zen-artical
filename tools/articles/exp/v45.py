import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from concurrent.futures import ThreadPoolExecutor
tee('v45'); reset()
print('服务注册中心感知实例不健康的两种方式:(1) 主动探测——注册中心(或旁边的检查器)定期向实例的 /health 发请求,连续失败 K 次就摘除;(2) 实例上报——实例定期向注册中心发心跳,超过 TTL 没收到就摘除。实例是本进程里的 Python 服务:一个“工作线程池”处理业务请求(/work 和 /health 都走它),另有一个独立的心跳线程。故障有两种:crash(整个进程不见了:监听关闭、心跳停止)和 hang(工作线程池全部卡死,但进程还活着、心跳线程照常发心跳)')
class Instance:
    def __init__(self, hb_cb=None, hb_iv=0.5):
        self.hung = False; self.crashed = False; self.hb_cb = hb_cb; self.hb_iv = hb_iv
        def app(h):
            if self.hung: time.sleep(30)                 # 工作线程卡死
            h.reply(200, b'ok')
        self.svc = Svc(app, backlog=64); self.port = self.svc.port
        if hb_cb: threading.Thread(target=self._hb, daemon=True).start()
    def _hb(self):
        while not self.crashed:
            self.hb_cb(self); time.sleep(self.hb_iv)
    def crash(self): self.crashed = True; self.svc.stop()
    def hang(self): self.hung = True

# ============ 一 ============
print('== 一:主动探测:探测间隔 I、连续失败阈值 K 与摘除延迟。探测超时 0.3 s。实例在一个随机时刻(探测周期内均匀随机)出故障,分别是 crash 和 hang;“摘除延迟”= 从故障发生到注册中心把它标记为不健康。每个组合重复 15 次')
def probe_once(port, to=0.3):
    st, _, _ = rpc(port, '/health', to, keepalive=False); return st == 200
def run_probe(I, K, fault):
    inst = Instance(); fails = [0]; marked = [None]; stop = threading.Event(); t_fault = [None]
    def prober():
        t_next = time.perf_counter() + random.uniform(0, I)
        while not stop.is_set():
            d = t_next - time.perf_counter()
            if d > 0: time.sleep(d)
            t_next += I
            if probe_once(inst.port): fails[0] = 0
            else:
                fails[0] += 1
                if fails[0] >= K and marked[0] is None and t_fault[0]: marked[0] = time.perf_counter(); return
    th = threading.Thread(target=prober, daemon=True); th.start(); time.sleep(random.uniform(0.3, 0.3 + I))
    t_fault[0] = time.perf_counter()
    if fault == 'crash': inst.crash()
    else: inst.hang()
    th.join(I * K + 5); stop.set(); d = (marked[0] - t_fault[0]) if marked[0] else None
    try: inst.svc.stop()
    except Exception: pass
    return d
random.seed(11); rows = []
for I in (0.5, 1.0):
    for K in (1, 3):
        row = [f'I = {I} s · K = {K}']
        for fault in ('crash', 'hang'):
            ds = [run_probe(I, K, fault) for _ in range(15)]; ds = [x for x in ds if x is not None]
            row.append(f'{min(ds):.2f} / {statistics.median(ds):.2f} / {max(ds):.2f} s')
        rows.append(tuple(row))
table(rows, ['探测间隔 · 失败阈值', 'crash:摘除延迟 最短 / 中位数 / 最长', 'hang:摘除延迟 最短 / 中位数 / 最长'])
print('  摘除延迟大致在 (K−1)×I 到 K×I 加上探测超时之间:crash 时连接立刻被拒,每次探测立刻失败;hang 时每次探测要等满 0.3 s 的超时才算失败,所以多出一个超时')

# ============ 二 ============
print('== 二:实例上报(心跳 + TTL)。实例每 0.5 s 向注册中心上报一次心跳,TTL 1.5 s(惰性过期)。故障:crash(心跳线程随进程一起停)和 hang(业务线程池卡死,但心跳线程仍在发)。同时有一个探测方(I = 0.5 s,K = 3)在探测 /health。看两种机制各自多久把实例标记为不健康——hang 时心跳机制会“一直认为它健康”')
def run_hb(fault):
    last = [time.perf_counter()]; inst = Instance(hb_cb=lambda i: last.__setitem__(0, time.perf_counter()), hb_iv=0.5)
    probe_fail = [0]; probe_marked = [None]; hb_marked = [None]; stop = threading.Event(); t_fault = [None]
    def prober():
        while not stop.is_set():
            time.sleep(0.5)
            if probe_once(inst.port): probe_fail[0] = 0
            else:
                probe_fail[0] += 1
                if probe_fail[0] >= 3 and probe_marked[0] is None and t_fault[0]: probe_marked[0] = time.perf_counter()
    def watcher():
        while not stop.is_set():
            if t_fault[0] and hb_marked[0] is None and time.perf_counter() - last[0] > 1.5: hb_marked[0] = time.perf_counter()
            time.sleep(0.02)
    for f in (prober, watcher): threading.Thread(target=f, daemon=True).start()
    time.sleep(1.2); t_fault[0] = time.perf_counter()
    if fault == 'crash': inst.crash()
    else: inst.hang()
    time.sleep(6.0); stop.set()
    h = (hb_marked[0] - t_fault[0]) if hb_marked[0] else None; p = (probe_marked[0] - t_fault[0]) if probe_marked[0] else None
    # 业务请求:故障后向实例发 10 个请求(超时 0.5 s),看有几个能成功
    ok = sum(1 for _ in range(10) if rpc(inst.port, '/work', 0.5, keepalive=False)[0] == 200) if fault != 'crash' else 0
    try: inst.svc.stop()
    except Exception: pass
    return h, p, ok
rows = []
for fault in ('crash', 'hang'):
    rs = [run_hb(fault) for _ in range(5)]
    hs = [r[0] for r in rs if r[0] is not None]; ps = [r[1] for r in rs if r[1] is not None]
    rows.append((fault, f'{statistics.median(hs):.2f} s({len(hs)} / 5 次摘除)' if hs else '一直认为健康(0 / 5 次摘除)', f'{statistics.median(ps):.2f} s({len(ps)} / 5 次摘除)' if ps else '没有摘除', f'{sum(r[2] for r in rs)} / 50'))
table(rows, ['故障', '心跳 + TTL 1.5 s:摘除延迟(中位数)', '探测 I = 0.5 s · K = 3:摘除延迟(中位数)', '故障之后发给它的 /work 请求成功数'])
print('  hang 时心跳线程和业务线程是独立的,心跳继续上报“我还活着”,注册中心不会摘掉它,发给它的请求全部超时;探测方因为 /health 也走业务线程池,探测会失败,所以能摘掉。心跳只能证明“进程活着、心跳线程活着”,不能证明“能处理请求”;要让心跳有意义,上报之前应当做一次真实的自检(走和业务一样的路径)')

# ============ 三 ============
print('== 三:探测多了会不会自己拖慢自己。一个探测器用固定大小的线程池,每轮探测 200 个实例,每个探测超时 1 s,每轮结束后立刻下一轮(尽快)。其中 10% 的实例是 hang 的(探测要等满 1 s 超时)。线程池大小 10 / 50 / 200 时,一轮探测要多久(= 实际的探测间隔)')
insts = [Instance() for _ in range(200)]
hung_set = set(random.Random(7).sample(range(200), 20))
for i in hung_set: insts[i].hang()
rows = []
for pool in (10, 50, 200):
    ts = []
    with ThreadPoolExecutor(pool) as ex:
        for _ in range(3):
            t0 = time.perf_counter(); list(ex.map(lambda p: rpc(p, '/health', 1.0, keepalive=False)[0], [i.port for i in insts])); ts.append(time.perf_counter() - t0)
    rows.append((pool, f'{statistics.median(ts):.2f} s', f'{min(ts):.2f} ~ {max(ts):.2f} s'))
table(rows, ['线程池大小', '一轮探测 200 个实例用时(中位数)', '3 轮范围'])
print('  理论下界:20 个 hang 的实例各占一个线程 1 s,用 10 个线程就至少要 2 s 才能处理完它们;线程池太小时,少量 hang 的实例就会把整轮探测拖慢,其它健康实例的探测间隔也跟着变长——探测间隔设成 1 s,实际可能是几秒')
for i in insts:
    try: i.svc.stop()
    except Exception: pass
