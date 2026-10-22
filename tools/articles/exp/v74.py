import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import prometheus_client as pc
from prometheus_client import CollectorRegistry, Counter, start_http_server
tee('v74'); reset()
print('SLO 与错误预算的计算。(一)预算的算术(纯计算);(二)(三)用 Prometheus 3.15.0 对一个“流量”的 counter 计算累计错误、剩余预算和燃烧速率(burn rate)。流量是我程序里按设定的错误率生成的计数(每秒 200 个请求,没有真实的 HTTP 调用),这样每个时刻的真实错误数是已知的;实验只有 300 s,所以“预算窗口”取 300 s,告警窗口取几秒到一两分钟,阈值按这个小窗口重新选,不是 30 天窗口下的常用取值')

# ============ 一 ============
print('== 一:错误预算的算术。可用性目标(SLO)在 30 天里允许的不可用时间 = 30 天 × (1 − SLO)(算出来的,按“请求成功率”等价于全部不可用的时间)')
rows = []
for slo in (0.99, 0.999, 0.9999, 0.99999):
    mins = 30 * 24 * 60 * (1 - slo); rows.append((f'{slo * 100:g}%', f'{mins:.1f} 分钟', f'{mins * 60:.0f} 秒', f'{1 - slo:.5f}'))
table(rows, ['SLO', '30 天允许的完全不可用时间', '秒', '错误预算(允许的错误比例)'])
print('  每增加一个 9,预算缩小为原来的十分之一;错误预算是“允许失败的请求比例”,不是时间:没有全部挂掉、只是一部分请求失败时,按失败的请求占比消耗预算')
print('  30 天窗口下常见的多窗口燃烧速率告警取值(长窗口 / 短窗口,燃烧速率阈值),以及按“燃烧速率 × 窗口 ÷ 30 天”算出来的、触发时已经消耗的预算比例(算出来的):')
table([(w, f'{th}×', f'{th * hrs / 720:.0%}') for w, th, hrs in (('1 小时 / 5 分钟', 14.4, 1), ('6 小时 / 30 分钟', 6, 6), ('3 天 / 6 小时', 1, 72))], ['窗口(长 / 短)', '燃烧速率阈值', '触发时已消耗的 30 天预算比例'])

# ============ 二 ============
reg = CollectorRegistry(); TOT = Counter('req_total', 'requests', registry=reg); ERR = Counter('req_errors_total', 'errors', registry=reg)
port, srv = (lambda p: (p, start_http_server(p, addr='127.0.0.1', registry=reg)[0]))(free_port())
prom = Prom('v74', f"""global:
  scrape_interval: 1s
  evaluation_interval: 1s
scrape_configs:
  - job_name: app
    static_configs:
      - targets: ['127.0.0.1:{port}']
""").start()
SLO = 0.99; BUDGET = 1 - SLO; RATE = 200; WIN = 300; ALLOWED = RATE * WIN * BUDGET
# 时间线(相对起点,秒):0~30 基线错误率 0.1%;30~36 事故 A(30% 错误);36~100 基线;100~160 事故 B(3% 错误);160~300 基线
def err_p(t):
    if 30 <= t < 36: return 0.30
    if 100 <= t < 160: return 0.03
    return 0.001
time.sleep(2); T0 = time.time(); carry = 0.0; hist = []
for sec in range(300):
    p = err_p(sec); n_err = RATE * p + carry; e = int(n_err); carry = n_err - e
    TOT.inc(RATE); ERR.inc(e); hist.append((sec, RATE, e)); time.sleep(max(0, T0 + sec + 1 - time.time()))
time.sleep(3)
def qr(expr, step=1):
    r = prom.query_range(expr, T0 + 10, T0 + 300, step); return [(float(t) - T0, float(v)) for t, v in r[0]['values']] if r else []
def ratio(W): return f'sum(increase(req_errors_total[{W}s])) / sum(increase(req_total[{W}s]))'
def burn(W): return f'({ratio(W)}) / {BUDGET}'

print(f'== 二:剩余预算。SLO 99%(预算 = 1% 的请求),“预算窗口”300 s,每秒 {RATE} 个请求,所以整个窗口的预算是 {RATE} × {WIN} × 1% = {ALLOWED:.0f} 个错误。时间线:0 到 30 s 基线(错误率 0.1%);30 到 36 s 事故 A(30% 的请求失败);36 到 100 s 基线;100 到 160 s 事故 B(3% 失败);160 到 300 s 基线。剩余预算 = 1 − 累计错误 ÷ {ALLOWED:.0f}(累计错误取自程序自己的计数,同时用 Prometheus 的 increase 核对)')
err_cum = lambda t: sum(e for s_, r, e in hist if s_ < t)
rows = []
for t in (29, 37, 99, 130, 161, 299):
    et = err_cum(t); pe = prom.query(f'sum(increase(req_errors_total[{t + 4}s]))', t=T0 + t)
    rows.append((f'第 {t} 秒', et, f'{et / ALLOWED:.0%}', f'{1 - et / ALLOWED:+.0%}', f'{float(pe[0]["value"][1]):.0f}' if pe else '-'))
table(rows, ['时刻', '累计错误(程序计数)', '已消耗的预算', '剩余预算', 'Prometheus increase 算出的累计错误'])
print('  预算按“失败的请求数”消耗:事故 A 只有 6 s、但 30% 的请求失败;事故 B 错误率只有 3%、但持续 60 s;两者各消耗了预算的相当一部分,再加上基线的 0.1%,到窗口结束时预算已经用完。两者换成时间的话,A 相当于 6 × 0.3 = 1.8 s 的完全不可用(算出来的)')

print('== 三:燃烧速率与告警。燃烧速率 = 窗口内错误率 ÷ 预算(1%);1 表示按这个速度恰好在预算窗口结束时用完预算。比较三种告警条件(窗口和阈值是我按这个小窗口选的):(a)快燃烧:燃烧速率(12 s)> 10 且燃烧速率(2 s)> 10;(b)慢燃烧:燃烧速率(60 s)> 2 且燃烧速率(6 s)> 2;(c)朴素:10 s 内错误率 > 5%。用 query_range(每秒一个点)看每条告警条件在什么时候成立:事故 A(第 30 到 36 秒)和事故 B(第 100 到 160 秒)各被哪条发现、从事故开始起多久、结束后多久恢复')
conds = {'(a)快燃烧:燃烧速率(12 s)> 10 且(2 s)> 10': f'{burn(12)} > 10 and {burn(2)} > 10', '(b)慢燃烧:燃烧速率(60 s)> 2 且(6 s)> 2': f'{burn(60)} > 2 and {burn(6)} > 2', '(c)朴素:10 s 错误率 > 5%': f'{ratio(10)} > 0.05'}
rows = []
for name, expr in conds.items():
    pts = qr(f'({expr})', 1); fired = sorted(t for t, v in pts) if pts else []
    def first_last(lo, hi):
        xs = [t for t in fired if lo <= t < hi]; return (min(xs), max(xs)) if xs else None
    A = first_last(30, 90); B = first_last(100, 240); out = [t for t in fired if not (30 <= t < 90 or 100 <= t < 240)]
    fa = f'第 {A[0]:.0f} 秒起(开始后 {A[0] - 30:+.0f} s,此时已消耗预算 {err_cum(A[0] + 1) / ALLOWED:.0%}),第 {A[1]:.0f} 秒止(结束后 {A[1] - 36:+.0f} s)' if A else '没有触发'; fb = f'第 {B[0]:.0f} 秒起(开始后 {B[0] - 100:+.0f} s,此时已消耗预算 {err_cum(B[0] + 1) / ALLOWED:.0%}),第 {B[1]:.0f} 秒止(结束后 {B[1] - 160:+.0f} s)' if B else '没有触发'
    b_cons = err_cum(B[0] + 1) / ALLOWED if B else None
    rows.append((name, fa, fb, len(out)))
table(rows, ['告警条件', '事故 A(30% 失败,6 s)', '事故 B(3% 失败,60 s)', '事故之外的触发点数'])
print('  事故 A 的燃烧速率是 30,B 是 3:快燃烧(阈值 10)只看得到 A,慢燃烧(阈值 2)两个都看得到但要等长窗口里累积到阈值——B 的发现比 A 晚得多;朴素的“10 s 错误率 > 5%”看不到 3% 的持续错误。短窗口的作用是事故结束之后让告警尽快清除')

prom.stop(); srv.shutdown()
print('ERRORS', dict(ERRORS))
