import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v6'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('熔断触发条件的两种窗口:计数窗口 = 最近 N 次调用;时间窗口 = 最近 T 秒内的调用。两者都有“最少调用数”(窗口里不到这么多次调用就不判断)和失败率阈值,可选慢调用率阈值(耗时超过 slow 秒的调用算慢)。前两节用虚拟时钟模拟(同一个类,不真的 sleep),第三节用真实的 HTTP 服务和线程')

class WB:
    def __init__(self, kind, size, min_calls, fail_thr=0.5, slow_thr=None, slow_s=1.0):
        self.kind, self.size, self.min_calls, self.fail_thr, self.slow_thr, self.slow_s = kind, size, min_calls, fail_thr, slow_thr, slow_s
        self.w = collections.deque(); self.open = False
    def record(self, t, ok, dur=0.0):
        """记录一次调用的结果;返回 True 表示这次记录使熔断器打开"""
        self.w.append((t, ok, dur))
        if self.kind == 'count':
            while len(self.w) > self.size: self.w.popleft()
        else:
            while self.w and self.w[0][0] <= t - self.size: self.w.popleft()
        n = len(self.w)
        if n < self.min_calls: return False
        fr = sum(1 for _, o, _ in self.w if not o) / n
        sr = sum(1 for _, _, d in self.w if d >= self.slow_s) / n
        if fr >= self.fail_thr or (self.slow_thr is not None and sr >= self.slow_thr): self.open = True; return True
        return False

# ============ 一 ============
print('== 一:多久能发现下游坏了。下游在 t = 20 s 之前全部成功,之后 100% 失败;请求以固定速率到达。计数窗口:最近 20 次、至少 10 次、失败率 ≥ 50%;时间窗口:最近 10 s、至少 10 次、失败率 ≥ 50%。“发现延迟”= 从下游开始坏到熔断器打开的秒数;“已经打到坏下游的请求”= 这期间失败的调用数')
def detect(kind, size, rate, outage=None):
    wb = WB(kind, size, 10, 0.5); t = 0.0; dt = 1.0 / rate; fails = 0
    while t < 20 + 3000:
        ok = t < 20
        if not ok: fails += 1
        if wb.record(t, ok): return t - 20, fails
        t += dt
    return None, fails
rows = []
for rate in (0.5, 1, 2, 5, 20, 100, 500):
    c, cf = detect('count', 20, rate); tm, tf = detect('time', 10, rate)
    rows.append((f'{rate:g} 次/秒', f'{c:.2f} s' if c is not None else '不触发', cf, f'{tm:.2f} s' if tm is not None else '不触发(窗口里不到 10 次调用)', tf))
table(rows, ['请求速率', '计数窗口:发现延迟', '已经打到坏下游的请求', '时间窗口:发现延迟', '已经打到坏下游的请求'])
print('  计数窗口的发现时间 ≈ 10 次 ÷ 速率,速率越高越快,速率低时要等很久;时间窗口只要窗口里调用数够就是看比例,发现时间在 5 s 上下(窗口一半的时间),与速率无关,但速率低到窗口里不够最少调用数时永远不会触发')

# ============ 二 ============
print('== 二:阈值太敏感会误判。下游平时有 2% 的随机失败,请求 50 次/秒,每分钟有 5% 的概率出现一个 5 秒的小故障(这 5 秒里失败率 30%,例如一次 GC 停顿)。虚拟跑 6 小时,统计各配置的误触发次数;再统计真故障(100% 失败)的发现延迟')
def noisy(seed=11, hours=6, rate=50, with_blips=True):
    rng = random.Random(seed); evs = []; blips = []
    for m in range(hours * 60):
        if rng.random() < 0.05: blips.append(m * 60 + rng.uniform(0, 55))
    if not with_blips: blips_used = []
    else: blips_used = blips
    t = 0.0; dt = 1.0 / rate; n = int(hours * 3600 * rate); out = []
    bi = 0
    for i in range(n):
        t = i * dt; inblip = any(b <= t < b + 5 for b in blips_used[max(0, bi - 1):bi + 2])
        while bi < len(blips_used) and blips_used[bi] + 5 < t: bi += 1
        out.append((t, rng.random() >= (0.30 if inblip else 0.02)))
    return out, blips
stream, blips = noisy(); stream0, _ = noisy(with_blips=False)
def false_trips(kind, size, mc, thr, stream=stream):
    wb = WB(kind, size, mc, thr); trips = 0; last = -999
    for t, ok in stream:
        if wb.record(t, ok):       # 打开后立刻“复位”(清空窗口),模拟半开成功后重新开始
            trips += 1; wb.w.clear(); wb.open = False
    return trips
def real_outage(kind, size, mc, thr, rate=50):
    wb = WB(kind, size, mc, thr); t = 0.0
    for i in range(int(25 * rate)):
        t = i / rate
        if wb.record(t, t < 20): return t - 20
    return None
rows = []
for name, kind, size, mc, thr in (('计数 20 次 / 最少 20 / 失败率 ≥ 50%', 'count', 20, 20, 0.5), ('计数 20 次 / 最少 20 / 失败率 ≥ 20%', 'count', 20, 20, 0.2), ('计数 100 次 / 最少 100 / 失败率 ≥ 20%', 'count', 100, 100, 0.2), ('时间 10 s / 最少 20 / 失败率 ≥ 50%', 'time', 10, 20, 0.5), ('时间 10 s / 最少 20 / 失败率 ≥ 20%', 'time', 10, 20, 0.2), ('时间 60 s / 最少 20 / 失败率 ≥ 20%', 'time', 60, 20, 0.2)):
    ft = false_trips(kind, size, mc, thr); f0 = false_trips(kind, size, mc, thr, stream0); d = real_outage(kind, size, mc, thr)
    rows.append((name, f0, ft, f'{d:.2f} s' if d is not None else '不触发'))
table(rows, ['配置', '只有 2% 基线失败时的误触发次数', '加上 5 秒小故障时的误触发次数', '真故障(100% 失败)的发现延迟'])
print(f'  6 小时里一共有 {len(blips)} 次 5 秒的小故障;小窗口里随机失败的个数波动很大(20 次调用、失败率 30% 时,一个窗口里失败 ≥ 10 次的概率约 4.8%,一个 5 秒小故障有 250 个这样的窗口),所以计数窗口小的配置会被短暂的小故障误触发;时间窗口按比例看,6 小时里没有误触发')

# ============ 三 ============
print('== 三:只慢不错的下游。20 个并发线程反复调用一个真实的本机 HTTP 服务,每个线程调完一个再调下一个(闭环);服务在 1 s 之后每个请求要 2 s(仍然返回 200,不报错);调用超时 3 s。熔断器:计数窗口 20 次、最少 10 次;A = 只看失败率 ≥ 50%;B = 失败率 ≥ 50% 或 慢调用率 ≥ 50%(耗时 ≥ 1 s 算慢)。跑 12 秒')
def run3(slow_thr):
    t0 = [0.0]
    def app(h):
        t = time.perf_counter() - t0[0]
        time.sleep(2.0 if t >= 1.0 else 0.01); h.reply(200, b'ok')
    S = Svc(app); wb = WB('count', 20, 10, 0.5, slow_thr, 1.0); lk = threading.Lock(); cnt = collections.Counter(); tripped = [None]; held = [0.0]
    t0[0] = time.perf_counter()
    def cl():
        while time.perf_counter() - t0[0] < 12:
            with lk: is_open = wb.open
            if is_open: time.sleep(0.01); continue
            t1 = time.perf_counter() - t0[0]; st, _, dt = rpc(S.port, '/', 3.0); now = time.perf_counter() - t0[0]
            with lk:
                if t1 >= 1.0: cnt['slow_reached'] += 1; held[0] += dt
                if wb.record(now, st == 200, dt) and tripped[0] is None: tripped[0] = now
    ths = [threading.Thread(target=cl) for _ in range(20)]; [t.start() for t in ths]; [t.join() for t in ths]; S.stop()
    return tripped[0], cnt, held[0]
rows = []
for name, st in (('A 只看失败率', None), ('B 失败率 + 慢调用率', 0.5)):
    tr, c, held = run3(st); rows.append((name, f'{tr:.2f} s' if tr else '没有触发', c['slow_reached'], f'{held:.0f} s'))
table(rows, ['熔断器', '打开的时刻', '服务变慢之后(1 s 起)发出的调用', '这些调用占用线程的总时间'])
nerr()
print('  慢调用要等调用返回才能被记成“慢”,所以打开的时刻不会早于第一批慢调用完成(服务变慢在 1 s,每个要 2 s,最早约 3 s);A 永远看不见这种“慢但不错”的下游,20 个线程一直被拖在里面')
