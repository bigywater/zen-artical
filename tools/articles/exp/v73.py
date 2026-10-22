import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import queue as Q
import prometheus_client as pc
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server
tee('v73'); reset()
print('RED 与 USE。一个带 8 个工作线程和长度 50 的等待队列的服务(基准每个请求 20 ms,理论容量 8 ÷ 0.02 s = 400 个/秒,实际能达到多少看过载阶段的完成速率),prometheus_client 暴露:请求计数(按状态)、耗时直方图、忙碌线程数、队列长度。Prometheus 3.15.0 每秒抓取。依次注入四种情形,各 25 s,用 PromQL 在每个阶段末尾取 RED(请求速率、错误率、耗时)和 USE(利用率、饱和度、错误)')
POOL, QMAX = 8, 50
reg = CollectorRegistry()
REQ = Counter('app_requests_total', 'requests', ['status'], registry=reg)
DUR = Histogram('app_request_seconds', 'latency', buckets=[.005, .01, .025, .05, .1, .15, .25, .5, 1, 2.5], registry=reg)
BUSY = Gauge('app_workers_busy', 'busy workers', registry=reg); QLEN = Gauge('app_queue_length', 'queue length', registry=reg); PSZ = Gauge('app_pool_size', 'pool size', registry=reg); PSZ.set(POOL)
q = Q.Queue(QMAX); knobs = {'rate': 200, 'service': 0.020, 'err': 0.0}; stop = threading.Event(); busy = [0]; lk = threading.Lock(); rnd = random.Random(5)
def worker():
    while not stop.is_set():
        try: t_arr = q.get(timeout=0.2)
        except Q.Empty: continue
        with lk: busy[0] += 1; BUSY.set(busy[0])
        time.sleep(knobs['service'])
        with lk: busy[0] -= 1; BUSY.set(busy[0])
        st = 'error' if rnd.random() < knobs['err'] else 'ok'; REQ.labels(st).inc(); DUR.observe(time.time() - t_arr)
ws = [threading.Thread(target=worker, daemon=True) for _ in range(POOL)]
for w in ws: w.start()
def gen():
    nxt = time.perf_counter()
    while not stop.is_set():
        nxt += 1.0 / knobs['rate']; d = nxt - time.perf_counter()
        if d > 0: time.sleep(d)
        elif d < -0.2: nxt = time.perf_counter()               # 落后太多就重新校准,避免追赶突发
        try: q.put_nowait(time.time())
        except Q.Full: REQ.labels('rejected').inc()
g = threading.Thread(target=gen, daemon=True); g.start()
def qsampler():
    while not stop.is_set(): QLEN.set(q.qsize()); time.sleep(0.1)
threading.Thread(target=qsampler, daemon=True).start()
port = free_port(); srv, _ = start_http_server(port, addr='127.0.0.1', registry=reg)
prom = Prom('v73', f"""global:
  scrape_interval: 1s
  evaluation_interval: 1s
scrape_configs:
  - job_name: app
    static_configs:
      - targets: ['127.0.0.1:{port}']
""").start()
def v(qs, t):
    r = prom.query(qs, t=t); return float(r[0]['value'][1]) if r else float('nan')
PHASES = [('基准', dict(rate=200, service=0.020, err=0.0)), ('错误率升高', dict(rate=200, service=0.020, err=0.2)), ('下游变慢(每个请求 60 ms)', dict(rate=100, service=0.060, err=0.0)), ('过载(来得比处理得快)', dict(rate=600, service=0.020, err=0.0))]
print('== 一:四种情形。每个阶段 25 s,在阶段末尾用 10 s 的窗口计算。RED:请求速率(含被拒绝的)、错误率((error + rejected) ÷ 全部)、耗时 p99 和平均耗时(完成的请求,从进入队列算起)。USE:工作线程利用率(忙碌线程 ÷ 8)、队列长度(饱和度)的最大值、被拒绝的请求数/秒(错误)。p99 来自 histogram_quantile(桶边界 …、25、50、100、150、250 ms),落在两个边界之间时按线性插值,所以是估计值')
rows = []; time.sleep(3)
for name, kn in PHASES:
    knobs.update(kn); time.sleep(25); t = time.time()
    tot = v('sum(rate(app_requests_total[10s]))', t) + 0; rej = v('rate(app_requests_total{status="rejected"}[10s])', t); rej = 0 if rej != rej else rej
    done = v('sum(rate(app_requests_total{status=~"ok|error"}[10s]))', t); err = v('rate(app_requests_total{status="error"}[10s])', t); err = 0 if err != err else err
    arrival = done + rej; p99 = v('histogram_quantile(0.99, sum by (le) (rate(app_request_seconds_bucket[10s])))', t) * 1000; mean = v('rate(app_request_seconds_sum[10s]) / rate(app_request_seconds_count[10s])', t) * 1000
    util = v('avg_over_time(app_workers_busy[10s]) / app_pool_size', t); ql = v('max_over_time(app_queue_length[10s])', t)
    rows.append((name, f'{arrival:.0f}', f'{done:.0f}', f'{(err + rej) / arrival:.1%}', f'{mean:.0f}', f'{p99:.0f}', f'{util:.0%}', f'{ql:.0f}', f'{rej:.0f}'))
table(rows, ['阶段', '到达速率(/s)', '完成速率(/s)', '错误率', '平均耗时(ms)', 'p99(ms)', '线程利用率', '队列长度(最大)', '被拒绝(/s)'])
print('  同一个服务四种不同的问题:错误率升高时 RED 的错误率马上变,利用率和队列都正常;下游变慢时耗时升高、利用率升高,但还没有排队;过载时到达速率超过完成速率,利用率 100%、队列满、请求被拒绝、耗时被队列拉长——只看某一个指标会漏掉另一种问题')

print('== 二:“错误”的定义。服务收到的请求里 70% 返回 200、25% 返回 404(客户端请求了不存在的资源)、5% 返回 500。分别按 “5xx ÷ 全部” 和 “非 2xx ÷ 全部” 计算错误率,用 Prometheus 查询')
reg2 = CollectorRegistry(); C2 = Counter('http_requests_total', 'x', ['code'], registry=reg2); r2 = random.Random(3)
for _ in range(20000): C2.labels(r2.choices(['200', '404', '500'], weights=[70, 25, 5])[0]).inc()
p2, s2 = start_http_server(free_port(), addr='127.0.0.1', registry=reg2) if False else (None, None)
port2 = free_port(); srv2, _ = start_http_server(port2, addr='127.0.0.1', registry=reg2)
prom.stop()
prom2 = Prom('v73b', f"""global:
  scrape_interval: 1s
scrape_configs:
  - job_name: web
    static_configs:
      - targets: ['127.0.0.1:{port2}']
""").start(); t0 = time.time()
while time.time() - t0 < 30 and not prom2.query('http_requests_total'): time.sleep(0.3)
time.sleep(2)
def v2(qs):
    r = prom2.query(qs); return float(r[0]['value'][1]) if r else float('nan')
e5 = v2('sum(http_requests_total{code=~"5.."}) / sum(http_requests_total)'); en2 = v2('sum(http_requests_total{code!~"2.."}) / sum(http_requests_total)')
table([('5xx ÷ 全部', f'{e5:.1%}'), ('非 2xx ÷ 全部', f'{en2:.1%}')], ['错误率的定义', '结果'])
print('  404 是客户端的问题,不是服务的错误;把所有非 2xx 都算错误,错误率会被客户端的请求虚高,告警会误报。哪些状态码算“错误”需要按 SLI 的目的定义')
prom2.stop(); srv2.shutdown(); stop.set(); srv.shutdown()
print('ERRORS', dict(ERRORS))
