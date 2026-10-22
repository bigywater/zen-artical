import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import prometheus_client as pc
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server
tee('v68'); reset()
print(f'指标的类型:counter、gauge、histogram。Prometheus 3.15.0(自己起的,抓取间隔按各节写明)抓取 prometheus_client {pc.__version__ if hasattr(pc, "__version__") else "0.26.0"} 暴露的指标。看三种类型各自在采样、重启、聚合时的行为差别:gauge 会漏掉两次抓取之间的尖峰、counter 重启会归零、预先算好的分位数不能跨实例聚合')
def prom_cfg(targets, interval):
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
def q_scalar(prom, q):
    r = prom.query(q); return float(r[0]['value'][1]) if r else float('nan')

# ============ 一 ============
print('== 一:gauge 会漏掉两次抓取之间的尖峰。应用有一个 gauge(inflight),平时是 5,每隔一段随机时间有一个 2 s 的尖峰到 100,共 10 个尖峰(总共 20 s),整个实验 100 s;同时有一个 counter(busy_seconds_total)在尖峰期间每 0.1 s 加 0.1。Prometheus 抓取间隔 5 s。实验结束后,看抓到的 gauge 样本里有几个是 100、max_over_time 是多少,以及 counter 的 increase 是多少')
reg = CollectorRegistry(); g = Gauge('inflight', 'in flight', registry=reg); c = Counter('busy_seconds_total', 'busy seconds', registry=reg); g.set(5)
port, srv = serve(reg); prom = Prom('v68a', prom_cfg([f'127.0.0.1:{port}'], 5)).start(); time.sleep(2)
rnd = random.Random(8); starts = sorted(rnd.sample(range(5, 95, 2), 10)); T0 = time.time(); spike_total = 0.0
def spiker():
    global spike_total
    for st in starts:
        time.sleep(max(0, T0 + st - time.time())); g.set(100); t1 = time.time()
        while time.time() - t1 < 2.0: c.inc(0.1); time.sleep(0.1)
        g.set(5); spike_total += time.time() - t1
th = threading.Thread(target=spiker); th.start(); th.join(); time.sleep(max(0, T0 + 100 - time.time())); time.sleep(6)
raw = prom.query('inflight[3m]')[0]['values']; vals = [float(v) for _, v in raw]
ten = [int(float(v)) for _, v in raw]
inc = q_scalar(prom, 'increase(busy_seconds_total[3m])'); mx = q_scalar(prom, 'max_over_time(inflight[3m])')
table([('gauge inflight', f'{len(vals)} 个样本', f'{sum(1 for v in vals if v == 100)} 个样本是 100', f'max_over_time = {mx:.0f}'), ('counter busy_seconds_total', f'{len(vals)} 个样本', f'increase = {inc:.1f} s', f'应用实际在尖峰里的时间 {spike_total:.1f} s')], ['指标', '抓到的样本数', '结果', '备注'])
print(f'  共 {len(starts)} 个尖峰,每个 2 s;抓取间隔 5 s,一个 2 s 的尖峰被某次抓取碰上的概率约 2/5。gauge 只记录抓取那一刻的值,没碰上的尖峰就看不到;counter 记录累计量,两次抓取之间发生的变化会在下一次抓取时全部体现,increase 能还原总量(counter 在抓取边界处有外推的误差)')
prom.stop(); srv.shutdown()

# ============ 二 ============
print('== 二:counter 重启归零。应用每秒处理 100 个请求(counter requests_total 每秒 +100),运行 20 s 后进程重启(counter 回到 0,模拟新进程),再运行 20 s;抓取间隔 1 s。比较:最后一个样本减第一个样本,和 increase()、rate() 的结果')
regs = [CollectorRegistry()]; cnt = Counter('requests_total', 'requests', registry=regs[0]); holder = {'reg': regs[0], 'cnt': cnt}
class Dyn(pc.registry.Collector):
    def collect(self): return holder['reg'].collect()
dyn = CollectorRegistry(auto_describe=False); dyn.register(Dyn())
port, srv = serve(dyn); prom = Prom('v68b', prom_cfg([f'127.0.0.1:{port}'], 1)).start(); time.sleep(1.5)
t0 = time.time()
for sec in range(40):
    if sec == 20:
        r2 = CollectorRegistry(); holder['reg'] = r2; holder['cnt'] = Counter('requests_total', 'requests', registry=r2)       # “重启”:新进程里 counter 从 0 开始
    holder['cnt'].inc(100); time.sleep(max(0, t0 + sec + 1 - time.time()))
time.sleep(2)
raw = [(float(t), float(v)) for t, v in prom.query('requests_total[2m]')[0]['values']]
drops = [(raw[i][1], raw[i + 1][1]) for i in range(len(raw) - 1) if raw[i + 1][1] < raw[i][1]]
last_first = raw[-1][1] - raw[0][1]; inc = q_scalar(prom, 'increase(requests_total[2m])'); rt = q_scalar(prom, f'rate(requests_total[2m])')
manual = last_first + sum(a for a, b in drops)
table([('最后一个样本 − 第一个样本', f'{last_first:.0f}'), ('按重置规则手算:(最后 − 第一个) + 重置前的最后一个值', f'{manual:.0f}'), ('increase(requests_total[2m])', f'{inc:.0f}'), ('rate(requests_total[2m]) × 120', f'{rt * 120:.0f}'), ('应用实际处理的请求数', '4000')], ['计算方式', '结果'])
print(f'  抓到 {len(raw)} 个样本,第一个样本 {raw[0][1]:.0f},最后一个样本 {raw[-1][1]:.0f};样本序列里检测到的“值变小”的位置:{drops}。increase() 和 rate() 把“值变小”当作 counter 重置,重置之前的值也算进去,所以比“最后 − 第一个”大得多;它们和手算值的差别来自窗口边界的外推;手算值也比应用实际处理的少,因为第一个样本之前的增量不在样本里')
prom.stop(); srv.shutdown()

# ============ 三 ============
print('== 三:分位数能不能跨实例聚合。两个实例:A 处理 90% 的流量(延迟约 10 ms,其中 2% 的请求 500 ms),B 处理 10% 的流量(延迟约 40 ms,没有慢请求)。每个实例暴露 histogram(桶:5、10、25、50、100、250、500、1000 ms)和一个预先算好的 gauge p99(各自从自己的样本里算的,相当于 summary 的分位数)。总共 20000 个请求。比较:所有请求合在一起的真实 p99、两个实例的 p99 取平均、按请求量加权平均、histogram_quantile(0.99, sum by (le) (rate(bucket)))')
rnd = random.Random(21); lat = {'A': [], 'B': []}
for i in range(18000): lat['A'].append((500 + rnd.random() * 20) if rnd.random() < 0.02 else max(2.0, rnd.gauss(10, 2)))
for i in range(2000): lat['B'].append(max(5.0, rnd.gauss(40, 6)))
BUCK = (5, 10, 25, 50, 100, 250, 500, 1000); regsB = {}; ports = {}; hist = {}; p99g = {}
for name in 'AB':
    regsB[name] = CollectorRegistry(); hist[name] = Histogram('req_ms', 'latency ms', buckets=BUCK, registry=regsB[name]); p99g[name] = Gauge('req_p99_ms', 'precomputed p99', registry=regsB[name]); ports[name], _ = serve(regsB[name])
prom = Prom('v68c', prom_cfg([f'127.0.0.1:{p}' for p in ports.values()], 1)).start(); time.sleep(1.5)
t0 = time.time()
for name in 'AB':
    xs = lat[name]; p99g[name].set(pct(xs, 99))
for step in range(20):
    for name in 'AB':
        xs = lat[name]; chunk = xs[step * len(xs) // 20:(step + 1) * len(xs) // 20]
        for x in chunk: hist[name].observe(x)
    time.sleep(max(0, t0 + step + 1 - time.time()))
time.sleep(3)
allx = lat['A'] + lat['B']; true99 = pct(allx, 99); pa, pb = pct(lat['A'], 99), pct(lat['B'], 99)
hq = q_scalar(prom, 'histogram_quantile(0.99, sum by (le) (increase(req_ms_bucket[2m])))')
avg_g = q_scalar(prom, 'avg(req_p99_ms)'); wavg = (pa * 18000 + pb * 2000) / 20000
table([('所有 20000 个请求的真实 p99', f'{true99:.1f}'), ('A 自己的 p99', f'{pa:.1f}'), ('B 自己的 p99', f'{pb:.1f}'), ('两个 p99 取平均(PromQL avg(req_p99_ms))', f'{avg_g:.1f}'), ('两个 p99 按请求量加权平均(计算)', f'{wavg:.1f}'), ('histogram_quantile(0.99, sum by (le) (increase(bucket)))', f'{hq:.1f}')], ['计算方式', 'p99(ms)'])
print('  预先算好的分位数不能求平均:不管是简单平均还是按请求量加权,都不等于合并后的真实 p99;histogram 的桶是计数,可以先相加再估计分位数,但估计值是在桶内线性插值得到的:这里慢请求(500~520 ms)都落在 (500, 1000] 这个宽桶里,插值的结果和真实值差得比较多(见下一篇)')
prom.stop()
for p in ports.values(): pass

# ============ 四 ============
print('== 四:类型只是约定。同一个 gauge(inflight,值在 5 到 100 之间上下变化)和一个 counter(requests_total)都对它们用 rate():看 Prometheus 对 gauge 做 rate() 得到什么,以及 deriv() 和 delta() 的结果。gauge 序列:0 到 40 s 内从 10 线性升到 50,再回落到 10')
reg = CollectorRegistry(); gg = Gauge('level', 'a gauge', registry=reg); cc = Counter('hits_total', 'a counter', registry=reg)
port, srv = serve(reg); prom = Prom('v68d', prom_cfg([f'127.0.0.1:{port}'], 1)).start(); time.sleep(1.5); t0 = time.time()
for sec in range(40):
    gg.set(10 + 2 * sec if sec < 20 else 50 - 2 * (sec - 20)); cc.inc(10); time.sleep(max(0, t0 + sec + 1 - time.time()))
time.sleep(2)
rows = [('rate(hits_total[30s])(每秒 +10 的 counter)', f'{q_scalar(prom, "rate(hits_total[30s])"):.2f}'), ('rate(level[30s])(对 gauge 用 rate)', f'{q_scalar(prom, "rate(level[30s])"):.2f}'), ('deriv(level[30s])', f'{q_scalar(prom, "deriv(level[30s])"):.2f}'), ('delta(level[30s])', f'{q_scalar(prom, "delta(level[30s])"):.2f}'), ('level 当前值', f'{q_scalar(prom, "level"):.0f}')]
table(rows, ['PromQL', '结果'])
print('  rate() 是为 counter 设计的:它把“值变小”当作重置,gauge 下降的那一段会被当成重置、从 0 重新算;对 gauge 应该用 deriv()(最小二乘斜率)或 delta()(首尾差)')
prom.stop()
print('ERRORS', dict(ERRORS))
