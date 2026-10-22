import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v12'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('服务端:同时最多处理 8 个请求(信号量),每个请求 50 ms(容量 160 个/秒),多的请求在服务端排队(不拒绝)。客户端:开环地以 300 个/秒发请求(是容量的近 2 倍),发之前先过一个“并发上限”限流器:在途请求数 ≥ 上限就立刻拒绝。“成功”= 拿到 200 且从发出到回来不超过 500 ms')

class Static:
    def __init__(s, n): s.limit = float(n); s.inflight = 0; s.lk = threading.Lock()
    def acquire(s):
        with s.lk:
            if s.inflight >= s.limit: return False
            s.inflight += 1; return True
    def release(s, rtt, ok):
        with s.lk: s.inflight -= 1
class AIMD(Static):
    """基于延迟的 AIMD:rtt 超过(最近最小 rtt × 1.5)就乘性减小(×0.9,至多每 100 ms 一次),否则加性增大(每个样本 + 1/limit)"""
    def __init__(s, start=10, lo=1, hi=200, win_s=None): super().__init__(start); s.lo, s.hi, s.win_s = lo, hi, win_s; s.win = collections.deque(maxlen=200); s.last_dec = 0.0
    def release(s, rtt, ok):
        with s.lk:
            s.inflight -= 1
            if not ok: return
            now = time.perf_counter(); s.win.append((now, rtt))
            if s.win_s:
                while s.win[0][0] < now - s.win_s: s.win.popleft()
            base = min(r for _, r in s.win)
            if rtt > base * 1.5:
                if time.perf_counter() - s.last_dec > 0.1: s.limit = max(s.lo, s.limit * 0.9); s.last_dec = time.perf_counter()
            else: s.limit = min(s.hi, s.limit + 1.0 / s.limit)
class Gradient(Static):
    """gradient:每 200 ms 一个窗口,gradient = 2 × (整体最小 rtt) / (窗口内 rtt 的中位数),限制在 [0.5, 1];新上限 = 上限 × gradient + 4,再平滑(0.2 的权重)"""
    def __init__(s, start=10, lo=1, hi=200): super().__init__(start); s.lo, s.hi = lo, hi; s.samples = []; s.noload = None; s.t0 = time.perf_counter()
    def release(s, rtt, ok):
        with s.lk:
            s.inflight -= 1
            if not ok: return
            s.samples.append(rtt); s.noload = rtt if s.noload is None else min(s.noload, rtt)
            if time.perf_counter() - s.t0 >= 0.2 and len(s.samples) >= 5:
                med = statistics.median(s.samples); g = max(0.5, min(1.0, 2 * s.noload / med)); new = s.limit * g + 4
                s.limit = max(s.lo, min(s.hi, s.limit * 0.8 + new * 0.2)); s.samples = []; s.t0 = time.perf_counter()

def run(lim, dur=10, rate=300, service=lambda t: 0.05, workers=8):
    sem = threading.Semaphore(workers); t0 = [0.0]
    def app(h):
        with sem: time.sleep(service(time.perf_counter() - t0[0]))
        h.reply(200, b'ok')
    S = Svc(app, backlog=1024); lims = []; res = []; lk = threading.Lock()
    def one(i):
        if not lim.acquire(): return ('rej', 0.0, 0.0)
        ts = time.perf_counter(); st, _, dt = rpc(S.port, '/', 5.0); lim.release(dt, st == 200)
        return ('ok' if st == 200 and dt <= 0.5 else 'late', dt, ts - t0[0])
    t0[0] = time.perf_counter(); stop = threading.Event()
    def sampler():
        while not stop.is_set(): lims.append((time.perf_counter() - t0[0], lim.limit)); time.sleep(0.1)
    threading.Thread(target=sampler, daemon=True).start()
    out = openloop(one, rate, dur, workers=600); stop.set(); S.stop()
    return [(ts, r) for ts, r in out], lims
def summarize(out, lims, t_from=0.0):
    sel = [r for ts, r in out if ts >= t_from]; n = len(sel)
    acc = [r for r in sel if r[0] != 'rej']; ok = [r for r in sel if r[0] == 'ok']; dt = [r[1] for r in acc]
    span = max(ts for ts, _ in out) - t_from if out else 1
    ls = [l for t, l in lims if t >= t_from]
    return n, len(sel) - len(acc), len(ok), pct(dt, 50) if dt else float('nan'), pct(dt, 99) if dt else float('nan'), statistics.mean(ls) if ls else float('nan'), len(ok) / (10 - t_from if t_from < 10 else 1)

# ============ 一 ============
print('== 一:静态上限 vs 自适应上限(10 秒,服务容量不变)。静态上限取 4 / 8 / 16 / 64 / 256;自适应:AIMD(基于延迟;“基准 rtt”取最近 200 个样本的最小值,或取最近 2 秒内的最小值两种)和 gradient。“被客户端拒绝”是限流器直接拒绝的;“成功”按 500 ms 内回来算;延迟只统计放行出去的请求')
rows = []
for name, mk in (('静态 4', lambda: Static(4)), ('静态 8', lambda: Static(8)), ('静态 16', lambda: Static(16)), ('静态 64', lambda: Static(64)), ('静态 256', lambda: Static(256)), ('AIMD(参照最近 200 个样本的最小 rtt)', lambda: AIMD()), ('AIMD(参照最近 2 秒的最小 rtt)', lambda: AIMD(win_s=2.0)), ('gradient', lambda: Gradient())):
    out, lims = run(mk()); n, rej, ok, p50, p99, ml, gp = summarize(out, lims, 2.0)
    rows.append((name, n, rej, ok, f'{gp:.0f}/s', f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms', f'{ml:.0f}'))
table(rows, ['上限', '第 2 到 10 秒到达的请求', '被客户端拒绝', '成功', '成功的速率', '放行请求延迟中位数', 'p99', '平均上限'])
nerr()

# ============ 二 ============
print('== 二:容量突然变化。第 5 秒时服务的单个请求耗时从 50 ms 变成 100 ms(容量从 160/s 降到 80/s,同时处理的并发数 8 不变),共跑 12 秒。比较:静态 8(为变化之前调的)、静态 64、两种 AIMD、gradient。分别统计变化之前(2 到 5 秒)和变化之后(7 到 12 秒)')
rows = []
for name, mk in (('静态 8', lambda: Static(8)), ('静态 64', lambda: Static(64)), ('AIMD(最近 200 个样本)', lambda: AIMD()), ('AIMD(最近 2 秒)', lambda: AIMD(win_s=2.0)), ('gradient', lambda: Gradient())):
    out, lims = run(mk(), dur=12, service=lambda t: 0.05 if t < 5 else 0.1)
    b = [r for ts, r in out if 2 <= ts < 5]; a = [r for ts, r in out if ts >= 7]
    def st(sel, secs):
        acc = [r for r in sel if r[0] != 'rej']; ok = [r for r in sel if r[0] == 'ok']; dt = [r[1] for r in acc]
        return f'{len(ok) / secs:.0f}/s · p99 {pct(dt, 99) * 1000:.0f} ms' if dt else '-'
    ml_b = statistics.mean([l for t, l in lims if 2 <= t < 5]); ml_a = statistics.mean([l for t, l in lims if t >= 7])
    rows.append((name, st(b, 3), f'{ml_b:.0f}', st(a, 5), f'{ml_a:.0f}'))
table(rows, ['上限', '变化之前:成功速率 · p99', '平均上限', '变化之后:成功速率 · p99', '平均上限'])
nerr()
