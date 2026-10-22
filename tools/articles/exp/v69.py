import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import math
import prometheus_client as pc
from prometheus_client import CollectorRegistry, Histogram, start_http_server
tee('v69'); reset()
print('直方图:桶的选取、分位数误差与 histogram_quantile 的近似。Prometheus 3.15.0(经典直方图,没有开启 native histogram)抓取 prometheus_client 0.26.0 暴露的 histogram。同一批延迟样本(10 万个)用不同的桶划分记录,把 histogram_quantile 的结果和直接从样本里算出来的真实分位数比较;再看数据超出最大桶时、分布随时间变化时 rate 窗口的影响,以及桶数对时间序列数量的影响')
def prom_cfg(targets, interval=1):
    return f'''global:
  scrape_interval: {interval}s
  evaluation_interval: {interval}s
scrape_configs:
  - job_name: lab
    static_configs:
      - targets: [{", ".join(repr(t) for t in targets)}]
'''
def serve(reg):
    port = free_port(); srv, th = start_http_server(port, addr='127.0.0.1', registry=reg); return port, srv
def wait_data(prom, metric, timeout=30.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if prom.query(metric): return True
        time.sleep(0.3)
    return False
def scalar_at(prom, q, t):
    r = prom.query(q, t=t); return float(r[0]['value'][1]) if r else float('nan')
def scalar(prom, q):
    r = prom.query(q); return float(r[0]['value'][1]) if r else float('nan')
rnd = random.Random(33); N = 100000
samples = [rnd.uniform(500, 1000) if rnd.random() < 0.01 else rnd.lognormvariate(math.log(20), 0.8) for _ in range(N)]
QS = (0.5, 0.9, 0.99, 0.999); TRUE = {q: pct(samples, q * 100) for q in QS}

# ============ 一 ============
print('== 一:桶的划分与分位数误差。样本:99% 服从对数正态分布(中位数 20 ms),1% 是 500~1000 ms 的慢请求。六种桶划分(单位 ms),每种把同样的 10 万个样本记进去,等 Prometheus 抓取之后用 histogram_quantile(q, h_bucket) 估计,和真实分位数比较(相对误差 = (估计 − 真实) ÷ 真实)')
LAYOUTS = [('prometheus_client 默认(×1000)', [5, 10, 25, 50, 75, 100, 250, 500, 750, 1000, 2500, 5000, 7500, 10000]),
           ('线性,每 50 ms 一个', list(range(50, 1001, 50))),
           ('指数,×2(5 到 1280)', [5 * 2 ** k for k in range(9)]),
           ('指数,×1.3(5 到约 1000)', [round(5 * 1.3 ** k, 2) for k in range(0, 21)]),
           ('只有两个桶:100、1000', [100, 1000]),
           ('围绕慢请求加密:10、20、40、80、200、400、600、800、1000', [10, 20, 40, 80, 200, 400, 600, 800, 1000])]
reg = CollectorRegistry(); hs = {}
for i, (name, b) in enumerate(LAYOUTS): hs[i] = Histogram(f'lat{i}_ms', 'latency', buckets=b, registry=reg)
for x in samples:
    for h in hs.values(): h.observe(x)
port, srv = serve(reg); prom = Prom('v69a', prom_cfg([f'127.0.0.1:{port}'])).start(); assert wait_data(prom, 'lat0_ms_count')
rows = []
for i, (name, b) in enumerate(LAYOUTS):
    row = [name, len(b)]
    for q in QS:
        est = scalar(prom, f'histogram_quantile({q}, lat{i}_ms_bucket)'); row.append(f'{est:.1f}({(est - TRUE[q]) / TRUE[q]:+.0%})')
    rows.append(row)
print('  真实分位数(ms):' + ',  '.join(f'p{q * 100:g} = {TRUE[q]:.1f}' for q in QS))
table(rows, ['桶划分', '有限桶个数'] + [f'p{q * 100:g} 估计(相对误差)' for q in QS])
print('  桶越宽,线性插值的误差越大;最大误差出现在分位数落进宽桶的时候。桶边界要覆盖要关心的分位数和阈值附近(例如 SLO 的 500 ms),并不是桶越多越好')
prom.stop(); srv.shutdown()

# ============ 二 ============
print('== 二:数据超出最大桶、以及刚好落在桶边界上。桶是 10、50、100、250、500、1000(ms)。(a)全部请求 3000~9000 ms(都超出最大有限桶 1000);(b)所有请求都恰好是 100 ms;(c)所有请求都是 100.001 ms。看 histogram_quantile(0.5)、(0.99) 的结果')
BK = [10, 50, 100, 250, 500, 1000]; rows = []
for name, gen in (('(a)全部 3000~9000 ms', lambda: random.uniform(3000, 9000)), ('(b)全部恰好 100 ms', lambda: 100.0), ('(c)全部 100.001 ms', lambda: 100.001)):
    reg = CollectorRegistry(); h = Histogram('x_ms', 'x', buckets=BK, registry=reg)
    for _ in range(5000): h.observe(gen())
    port, srv = serve(reg); prom = Prom('v69b', prom_cfg([f'127.0.0.1:{port}'])).start(); assert wait_data(prom, 'x_ms_count')
    rows.append((name, f'{scalar(prom, "histogram_quantile(0.5, x_ms_bucket)"):.1f}', f'{scalar(prom, "histogram_quantile(0.99, x_ms_bucket)"):.1f}', f'{scalar(prom, "x_ms_sum / x_ms_count"):.1f}')); prom.stop(); srv.shutdown()
table(rows, ['数据', 'p50 估计(ms)', 'p99 估计(ms)', '用 sum / count 算的平均值(ms)'])
print('  超出最大有限桶的数据都进了 +Inf 桶,histogram_quantile 在落进 +Inf 桶时只能返回最大有限桶的上界(这里 1000),平均值(sum / count)才反映真实水平;桶边界是“小于等于”,恰好 100 ms 的请求进 le=100 的桶,估计值是这个桶 (50, 100] 内线性插值的位置(p50 = 75、p99 = 99.5),不是 100 本身;100.001 ms 的请求落进下一个桶 (100, 250]')

# ============ 三 ============
print('== 三:rate 窗口。一个服务以 200 个请求/秒的速度产生延迟,前 30 s 每个请求 10 ms,后 30 s 每个请求 200 ms(桶:5、10、25、50、100、250、500 ms)。Prometheus 每秒抓取。分别在第 50 秒和第 60 秒查询 histogram_quantile(0.5 / 0.99, rate(bucket[W])),窗口 W 取 10 s、30 s、60 s,并和按同一窗口从原始样本里算的真实 p50、p99 比较')
reg = CollectorRegistry(); h = Histogram('svc_ms', 'x', buckets=[5, 10, 25, 50, 100, 250, 500], registry=reg); port, srv = serve(reg); prom = Prom('v69c', prom_cfg([f'127.0.0.1:{port}'])).start(); time.sleep(1.5)
t0 = time.time(); hist_obs = []
for sec in range(60):
    v = 10.0 if sec < 30 else 200.0
    for k in range(200): h.observe(v); hist_obs.append((sec, v))
    time.sleep(max(0, t0 + sec + 1 - time.time()))
time.sleep(2); rows = []
for at in (50, 60):
    for W in (10, 30, 60):
        e50 = scalar_at(prom, f'histogram_quantile(0.5, rate(svc_ms_bucket[{W}s]))', t0 + at); e99 = scalar_at(prom, f'histogram_quantile(0.99, rate(svc_ms_bucket[{W}s]))', t0 + at)
        win = [v for s_, v in hist_obs if at - W <= s_ < at]; rows.append((f'第 {at} 秒', f'{W} s', f'{e50:.1f}', f'{pct(win, 50):.1f}', f'{e99:.1f}', f'{pct(win, 99):.1f}', f'{sum(1 for v in win if v == 200.0) / len(win):.0%}'))
table(rows, ['查询时刻(服务第 30 秒起变慢)', 'rate 窗口 W', 'p50 估计(ms)', '窗口内真实 p50(ms)', 'p99 估计(ms)', '窗口内真实 p99(ms)', '窗口内慢阶段请求的比例'])
print('  窗口里同时有快慢两个阶段时,p50 由占多数的阶段决定:第 50 秒时慢阶段只占 W=60 s 窗口的一部分(见表中最后一列),p50 还是快阶段的值,而 W=10 s 的窗口全是慢阶段;p99 只要慢阶段占比不低于 1% 就落在慢阶段的桶里,所以几个窗口给出几乎一样的值;p99 的估计比真实值(200)高,是因为落进 (100, 250] 这个桶之后在桶内做线性插值,与窗口无关')
prom.stop(); srv.shutdown()

# ============ 四 ============
print('== 四:桶数与时间序列数量。一个 histogram 带标签 route(50 个取值)和 status(3 个取值),每个组合都记录过数据;桶个数分别 5、14(默认)、20。数一数 Prometheus 里这个 histogram 一共有多少条时间序列(_bucket、_sum、_count)')
rows = []
for nb in (5, 14, 20):
    reg = CollectorRegistry(); bk = [round(5 * 1.5 ** k, 2) for k in range(nb)]; h = Histogram('api_ms', 'x', ['route', 'status'], buckets=bk, registry=reg)
    for r in range(50):
        for st in ('200', '404', '500'): h.labels(route=f'/r{r}', status=st).observe(10)
    port, srv = serve(reg); prom = Prom('v69d', prom_cfg([f'127.0.0.1:{port}'])).start(); assert wait_data(prom, 'api_ms_count')
    n = int(scalar(prom, 'count({__name__=~"api_ms_.*"})')); nb_series = int(scalar(prom, 'count(api_ms_bucket)')); rows.append((nb, 150, nb_series, n, f'{n / 150:.0f}')); prom.stop(); srv.shutdown()
table(rows, ['有限桶个数', '标签组合数', '_bucket 序列数', '这个 histogram 的总序列数(含 _sum、_count)', '平均每个标签组合的序列数'])
print('  每个标签组合的序列数 = 有限桶个数 + 1(+Inf 桶)+ 2(_sum 和 _count)+ 1(prometheus_client 额外暴露的 _created),数字与上表一致;桶越多、标签组合越多,序列数相乘增长')
print('ERRORS', dict(ERRORS))
