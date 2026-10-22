import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v5'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')

class Open(Exception): pass
class TooMany(Exception): pass

class Breaker:
    """手写的熔断器:连续失败 trip 次 → 打开;打开 open_s 秒后第一个到来的请求使它进入半开;半开最多放行 max_half 个请求,max_half 个连续成功 → 关闭,任何一次失败 → 立刻重新打开。clock 可替换成虚拟时钟。"""
    def __init__(self, trip=5, open_s=1.0, max_half=3, clock=time.perf_counter, log=None):
        self.trip, self.open_s, self.max_half, self.clock, self.log = trip, open_s, max_half, clock, log
        self.state = 'closed'; self.cf = 0; self.cs = 0; self.admitted = 0; self.opened_at = 0.0; self.lk = threading.Lock(); self.t0 = clock(); self.trans = []
    def _set(self, new):
        if new == self.state: return
        self.trans.append(((self.clock() - self.t0), self.state, new)); self.state = new
        self.cf = 0; self.cs = 0; self.admitted = 0
        if new == 'open': self.opened_at = self.clock()
    def call(self, fn):
        with self.lk:
            if self.state == 'open':
                if self.clock() - self.opened_at >= self.open_s: self._set('half-open')
                else: raise Open()
            if self.state == 'half-open':
                if self.admitted >= self.max_half: raise TooMany()
                self.admitted += 1
            gen = (self.state, len(self.trans))
        try: r = fn(); ok = True
        except Exception: ok = False
        with self.lk:
            if (self.state, len(self.trans)) == gen:        # 状态没有被别人改过才计数
                if ok:
                    if self.state == 'closed': self.cf = 0
                    else:
                        self.cs += 1
                        if self.cs >= self.max_half: self._set('closed')
                else:
                    if self.state == 'closed':
                        self.cf += 1
                        if self.cf >= self.trip: self._set('open')
                    else: self._set('open')
        if not ok: raise RuntimeError('boom')
        return r

def failing(i): return 10 <= i < 50 or 80 <= i < 112

# ============ 一 ============
print('== 一:手写熔断器的状态转换。剧本:每 50 ms 调用一次、共 160 次(i 从 0 数);i 在 10..49 和 80..111 时下游失败,其余时间正常;连续失败 5 次打开,打开 1025 ms 后进入半开,半开最多放行 3 个请求、3 个连续成功才关闭(1025 而不是 1000 ms,是为了不要正好卡在 20 个调用间隔的整数倍上)')
def scenario_py():
    b = Breaker(5, 1.025, 3); cnt = collections.Counter(); T0 = time.perf_counter()
    for i in range(160):
        d = T0 + i * 0.05 - time.perf_counter()
        if d > 0: time.sleep(d)
        def fn():
            cnt['reached'] += 1
            if failing(i): cnt['failed'] += 1; raise RuntimeError
            return 'ok'
        try: b.call(fn)
        except Open: cnt['open'] += 1
        except TooMany: cnt['toomany'] += 1
        except RuntimeError: pass
    return b.trans, cnt
tr, cnt = scenario_py()
table([(f'{t * 1000:.0f} ms', a, b) for t, a, b in tr], ['时刻', '从', '到'])
print(f"  160 次调用里:真正到达下游 {cnt['reached']} 次(其中失败 {cnt['failed']} 次),被熔断器直接拒绝 {cnt['open']} 次,半开状态因放行名额用完被拒 {cnt['toomany']} 次")

# ============ 二 ============
print('== 二:同一个剧本交给 Go 的 gobreaker(github.com/sony/gobreaker/v2 v2.4.0;Settings:MaxRequests 3、Timeout 1025 ms、ReadyToTrip = 连续失败 ≥ 5)。对照两边的状态转换序列')
out = sh(f'cd {HERE}/vtmp/gb && ./gbrun')
gtr = [(int(l.split()[1]), l.split()[2], l.split()[3]) for l in out.splitlines() if l.startswith('T ')]
gc = dict(kv.split('=') for kv in out.splitlines()[-1].split()[1:])
rows = []
for k in range(max(len(tr), len(gtr))):
    a = tr[k] if k < len(tr) else None; g = gtr[k] if k < len(gtr) else None
    rows.append((k + 1, f'{a[1]} → {a[2]}' if a else '-', f'{a[0] * 1000:.0f} ms' if a else '-', f'{g[1]} → {g[2]}' if g else '-', f'{g[0]} ms' if g else '-'))
table(rows, ['#', '手写:转换', '时刻', 'gobreaker:转换', '时刻'])
same = [(a[1], a[2]) for a in tr] == [(g[1], g[2]) for g in gtr]
print(f"  转换序列{'完全相同' if same else '不同'}({len(tr)} 次对 {len(gtr)} 次);gobreaker:到达下游 {gc['reached']} 次(失败 {gc['failed']}),拒绝(打开){gc['rejected_open']},拒绝(半开名额用完){gc['rejected_toomany']};手写:到达 {cnt['reached']}(失败 {cnt['failed']}),拒绝(打开){cnt['open']},拒绝(半开名额用完){cnt['toomany']}")

# ============ 三 ============
print('== 三:半开放行多少个。20 个并发线程各自每 20 ms 通过熔断器调用一个真实的本机 HTTP 服务;服务在 0.5 s 到 3.5 s 之间不可用(立刻回 503,每次请求处理 5 ms),之后恢复;熔断器连续失败 5 次打开,打开 1 s 后半开。共 6 秒。比较半开放行 1 个 / 3 个 / 10 个。“半开期间到达下游的失败”是在服务仍不可用时(3.5 s 之前)半开放过去、结果失败的探测请求')
def run3(mh):
    t0 = [0.0]
    def app(h):
        t = time.perf_counter() - t0[0]; time.sleep(0.005)
        h.reply(503 if 0.5 <= t < 3.5 else 200, b'x')
    S = Svc(app); b = Breaker(5, 1.0, mh); cnt = collections.Counter(); lk = threading.Lock(); done_at = [None]
    t0[0] = time.perf_counter(); b.t0 = t0[0]
    def cl(k):
        while time.perf_counter() - t0[0] < 6.0:
            st0 = b.state
            def fn():
                st, _, _ = rpc(S.port, '/', 2.0)
                with lk:
                    cnt['reached'] += 1
                    if st != 200 and time.perf_counter() - t0[0] < 3.5 and st0 != 'closed': cnt['halfopen_fail'] += 1
                if st != 200: raise RuntimeError
            try: b.call(fn)
            except Open: cnt['open'] += 1
            except TooMany: cnt['toomany'] += 1
            except RuntimeError: cnt['err'] += 1
            time.sleep(0.02)
    ths = [threading.Thread(target=cl, args=(k,)) for k in range(20)]; [t.start() for t in ths]; [t.join() for t in ths]; S.stop()
    closed_after = [t for t, a, bb in b.trans if bb == 'closed' and t >= 3.5]
    return b.trans, cnt, (closed_after[0] - 3.5) if closed_after else None
rows = []
for mh in (1, 3, 10):
    tr3, c3, ca = run3(mh)
    rows.append((mh, sum(1 for t, a, bb in tr3 if bb == 'open'), sum(1 for t, a, bb in tr3 if bb == 'half-open'), c3['reached'], c3['halfopen_fail'], c3['open'], c3['toomany']))
table(rows, ['半开放行数', '打开的次数', '进入半开的次数', '到达下游的请求', '半开期间到达下游的失败', '被拒(打开)', '被拒(半开名额用完)'])
nerr()

# ============ 四 ============
print('== 四:恢复后下游仍不稳定。用虚拟时钟模拟(同一个 Breaker 类,不真的 sleep):下游在 t=0 恢复,但每次调用以概率 q 成功;每 50 ms 调用一次;打开 1 s 后半开;从打开期满(下游已经恢复、可以进半开)开始计时,到真正关闭要多久,上限 599 s。每个组合 1000 次试验,取中位数和 p90')
def run4(q, mh, seed):
    clk = [0.0]; rng = random.Random(seed); b = Breaker(5, 1.0, mh, clock=lambda: clk[0]); b._set('open'); b.opened_at = 0.0; start = None; cycles = 0
    while clk[0] < 600:
        clk[0] += 0.05
        try:
            b.call(lambda: None if rng.random() < q else (_ for _ in ()).throw(RuntimeError()))
        except (Open, TooMany, RuntimeError): pass
        if b.state == 'half-open' and start is None: start = clk[0]
        if b.state == 'closed': break
    return clk[0] - 1.0, sum(1 for t, a, c in b.trans if c == 'open') - 1
rows = []
for q in (1.0, 0.9, 0.7, 0.5):
    row = [f'q = {q:.0%}']
    for mh in (1, 3, 10):
        R = [run4(q, mh, s) for s in range(1000)]; T = [r[0] for r in R]; C = [r[1] for r in R]
        fm = lambda x: '≥ 599 s' if x >= 598.9 else f'{x:.2f} s'
        row.append(f'中位数 {fm(statistics.median(T))} / p90 {fm(pct(T, 90))} / 平均重新打开 {statistics.mean(C):.1f} 次')
    rows.append(tuple(row))
table(rows, ['下游成功率', '半开放行 1', '半开放行 3', '半开放行 10'])
print('  半开要连续 N 个成功才关闭,所以下游成功率 q 不高时,N 越大越容易在半开里又失败一次、重新打开(q^N 是一轮半开通过的概率)')
