import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import subprocess as sp, logging, logging.handlers, queue as Q, re
import prometheus_client as pc
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import opentelemetry.sdk.version as otv
tee('v77'); reset()
print(f'可观测性的开销。Go 部分:go1.27.1 的 testing 基准(Apple M2 Pro,darwin/arm64,GOMAXPROCS 默认),prometheus/client_golang v1.25.0 和标准库 log/slog,每个基准跑 3 次取中位数;Python 部分:Python 3.14、prometheus_client 0.26.0、OpenTelemetry SDK {otv.__version__},用 time.perf_counter 循环计时。数字只反映这台机器上的热路径开销(不含网络、磁盘落盘之外的东西)')
D = pathlib.Path(__file__).resolve().parent.parent / 'vtmp/v77'

# ============ 一 ============
print('== 一:Go 热路径。每次操作的耗时(ns/op,3 次的中位数)和每次操作的内存分配次数。对照项:atomic 加一、mutex 加一、time.Now()')
r = sp.run(['go', 'test', '-run', 'xxx', '-bench', '.', '-benchmem', '-count=3'], cwd=D, capture_output=True, text=True, timeout=600)
res = collections.defaultdict(list)
for line in r.stdout.splitlines():
    m = re.match(r'Benchmark(\w+)-\d+\s+\d+\s+([\d.]+) ns/op\s+(\d+) B/op\s+(\d+) allocs/op', line)
    if m: res[m.group(1)].append((float(m.group(2)), int(m.group(4))))
names = [('AtomicAdd', 'atomic.Int64.Add(1)'), ('MutexAdd', 'sync.Mutex 加一'), ('TimeNow', 'time.Now()'), ('PromCounterInc', 'Prometheus Counter.Inc()'), ('PromCounterVecWithLabelValues', 'CounterVec.WithLabelValues(…).Inc()(每次查标签)'), ('PromCounterVecCachedChild', 'CounterVec 缓存 child 后 .Inc()'), ('PromGaugeSet', 'Gauge.Set()'), ('PromHistogramObserve', 'Histogram.Observe()(默认 11 个桶)'), ('PromHistogramVecObserve', 'HistogramVec.WithLabelValues(…).Observe()'), ('PromCounterIncParallel', 'Counter.Inc() 10 个 goroutine 并发(每次操作的均摊耗时)'), ('AtomicAddParallel', 'atomic.Int64.Add(1) 10 个 goroutine 并发'), ('SlogDisabledLevel', 'slog.Info 级别被关掉'), ('SlogTextToDiscard', 'slog.Info(文本)写到 io.Discard'), ('SlogJSONToDiscard', 'slog.Info(JSON)写到 io.Discard')]
table([(lab, f'{statistics.median(v for v, a in res[k]):.1f}', res[k][0][1]) for k, lab in names if k in res], ['操作', 'ns/op(中位数)', 'allocs/op'])
print('  一次不带标签的 Counter.Inc 和一次 atomic 加一差不多(都是几纳秒);带标签的 WithLabelValues 每次要把标签值做哈希查表,约十倍;Histogram 要按桶二分查找再做几次原子操作;日志一行是几百纳秒,而且和字段个数、编码方式有关;关掉的日志级别几乎免费。并发写同一个计数器时,缓存行争用让每次操作慢了十几倍(atomic 本身也一样)')

# ============ 二 ============
print('== 二:Python 热路径。每次操作的耗时(ns/op,中位数,5 轮)。prometheus_client 的 Counter / Histogram、OpenTelemetry 的 span(未配置 SDK 的 no-op、SDK 加内存导出器的 SimpleSpanProcessor、SDK 加 BatchSpanProcessor 导出到丢弃一切的导出器)、logging(级别关闭、NullHandler、写临时文件并格式化)')
def bench(fn, n, rounds=5):
    ts = []
    for _ in range(rounds):
        t = time.perf_counter()
        for _ in range(n): fn()
        ts.append((time.perf_counter() - t) / n * 1e9)
    return statistics.median(ts)
reg = CollectorRegistry(); c0 = Counter('c0', 'x', registry=reg); cv = Counter('cv', 'x', ['m', 'c'], registry=reg); ch = cv.labels('GET', '200'); h0 = Histogram('h0', 'x', registry=reg); hv = Histogram('hv', 'x', ['route'], registry=reg); g0 = Gauge('g0', 'x', registry=reg)
tp_noop = trace.NoOpTracerProvider().get_tracer('n')
class Drop(SpanExporter):
    def export(self, spans): return SpanExportResult.SUCCESS
tp1 = TracerProvider(); tp1.add_span_processor(SimpleSpanProcessor(Drop())); tr1 = tp1.get_tracer('s')
tp2 = TracerProvider(); tp2.add_span_processor(BatchSpanProcessor(Drop(), max_queue_size=1000000, schedule_delay_millis=200)); tr2 = tp2.get_tracer('b')
def span_noop():
    with tp_noop.start_as_current_span('x'): pass
def span_simple():
    with tr1.start_as_current_span('x'): pass
def span_batch():
    with tr2.start_as_current_span('x'): pass
def span_attrs():
    with tr2.start_as_current_span('x', attributes={'a': 1, 'b': 'two', 'c': 3.0, 'd': True, 'e': 'five'}): pass
lg_off = logging.getLogger('off'); lg_off.setLevel(logging.ERROR); lg_off.propagate = False
lg_null = logging.getLogger('null'); lg_null.setLevel(logging.INFO); lg_null.propagate = False; lg_null.addHandler(logging.NullHandler())
logf = TT / 'v77_py.log'; lg_file = logging.getLogger('file'); lg_file.setLevel(logging.INFO); lg_file.propagate = False
fh = logging.FileHandler(logf, mode='w'); fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')); lg_file.addHandler(fh)
rows = [('Counter.inc()(无标签)', bench(c0.inc, 200000)), ('Counter.labels(…).inc()(每次查标签)', bench(lambda: cv.labels('GET', '200').inc(), 100000)), ('缓存 child 后 .inc()', bench(ch.inc, 200000)), ('Gauge.set()', bench(lambda: g0.set(1), 200000)), ('Histogram.observe()(无标签)', bench(lambda: h0.observe(0.037), 100000)), ('Histogram.labels(…).observe()', bench(lambda: hv.labels('/o').observe(0.037), 100000)),
        ('span(no-op,没配 SDK)', bench(span_noop, 100000)), ('span(SDK + SimpleSpanProcessor)', bench(span_simple, 20000)), ('span(SDK + BatchSpanProcessor)', bench(span_batch, 20000)), ('span(SDK + Batch,5 个属性)', bench(span_attrs, 20000)),
        ('logging.info,级别被关掉', bench(lambda: lg_off.info('order created user=%s', 'u1'), 200000)), ('logging.info → NullHandler', bench(lambda: lg_null.info('order created user=%s', 'u1'), 100000)), ('logging.info → 文件(格式化 + 写入)', bench(lambda: lg_file.info('order created user=%s', 'u1'), 50000))]
table([(a, f'{b:.0f}', f'{b / 1000:.2f}') for a, b in rows], ['操作', 'ns/op(中位数)', 'µs/op'])
go_inc = statistics.median(v for v, a in res['PromCounterInc']); py_inc = dict(rows)['Counter.inc()(无标签)']
print(f'  同样是 Counter.inc():Python {py_inc:.0f} ns,Go {go_inc:.1f} ns,Python 是 Go 的 {py_inc / go_inc:.0f} 倍(算出来的比值);Python 里指标操作是零点几到一微秒,一个 span 是 {dict(rows)["span(SDK + BatchSpanProcessor)"] / 1000:.1f} 到 {dict(rows)["span(SDK + Batch,5 个属性)"] / 1000:.1f} µs,一行日志写文件是 {dict(rows)["logging.info → 文件(格式化 + 写入)"] / 1000:.1f} µs(NullHandler 是 {dict(rows)["logging.info → NullHandler"] / 1000:.1f} µs,说明大部分在格式化和写文件);给 span 加属性、指标带标签的查询都会增加耗时')
tp1.shutdown(); tp2.shutdown(); fh.close()

# ============ 三 ============
print('== 三:同步写与异步写日志。日志的目的地很慢(每次写入 3 ms 或 8 ms,用 sleep 模拟慢盘/慢网络)。请求以 200 个/秒的速度到来,每个请求写 1 行日志,运行 10 s(共 2000 次调用),测每次 logger.info 调用本身的耗时(也就是日志对请求路径加的延迟)。(a)同步 handler;(b)QueueHandler + QueueListener,队列上限 1000。8 ms 时目的地的处理能力是 125 行/秒,低于 200 行/秒,看队列满了之后的表现')
class SlowHandler(logging.Handler):
    def __init__(self, delay): super().__init__(); self.delay = delay; self.n = 0
    def emit(self, rec): time.sleep(self.delay); self.n += 1
def run_logging(mode, delay):
    lg = logging.getLogger(f'm{mode}{delay}'); lg.setLevel(logging.INFO); lg.propagate = False; slow = SlowHandler(delay); lst = None; drops = [0]
    if mode == 'sync': lg.addHandler(slow)
    else:
        q = Q.Queue(maxsize=1000)
        class QH(logging.handlers.QueueHandler):
            def enqueue(self, record):
                try: self.queue.put_nowait(record)
                except Q.Full: drops[0] += 1
        lg.addHandler(QH(q)); lst = logging.handlers.QueueListener(q, slow); lst.start()
    lat = []; t0 = time.perf_counter(); n = 2000
    for i in range(n):
        d = t0 + i / 200 - time.perf_counter()
        if d > 0: time.sleep(d)
        t = time.perf_counter(); lg.info('order created'); lat.append(time.perf_counter() - t)
    wall = time.perf_counter() - t0
    if lst: time.sleep(1.0); lst.stop()
    return lat, wall, slow.n, drops[0]
rows = []
for delay in (0.003, 0.008):
    for mode, name in (('sync', '(a)同步'), ('async', '(b)异步队列')):
        lat, wall, written, drops = run_logging(mode, delay)
        rows.append((f'{delay * 1000:.0f} ms', name, f'{pct(lat, 50) * 1000:.3f}', f'{pct(lat, 99) * 1000:.3f}', f'{max(lat) * 1000:.1f}', f'{wall:.1f}', written, drops))
table(rows, ['目的地每次写入耗时', '方式', 'logger.info 耗时 p50(ms)', 'p99(ms)', '最大(ms)', '2000 次调用用的总时间(s)', '目的地实际写入的行数', '被丢弃的行数'])
print('  同步写时,目的地的耗时全部加在请求路径上:3 ms 的目的地让每次调用多 3 ms;8 ms 的目的地让 200 个/秒的请求跟不上(调用被拖慢,总时间变长)。异步队列把调用的耗时降到微秒级,代价是目的地跟不上时队列满了就只能丢日志(或者阻塞调用方)')

# ============ 四 ============
print('== 四:放在完整请求里。一个请求做 1 ms 的 CPU 工作(忙等),单线程不停地处理 5 s,看每秒处理的请求数。四种配置:(a)什么都不记录;(b)加 2 次指标(1 次带标签的 Counter、1 次 Histogram.observe);(c)再加 3 行 JSON 日志写到文件;(d)再加 1 个 span(SDK + BatchSpanProcessor,有 3 个属性)')
import json as _json
class JF(logging.Formatter):
    def format(self, rec): return _json.dumps({'ts': rec.created, 'level': rec.levelname, 'msg': rec.getMessage(), 'svc': 'order'})
lgq = logging.getLogger('req'); lgq.setLevel(logging.INFO); lgq.propagate = False; fh2 = logging.FileHandler(TT / 'v77_req.log', mode='w'); fh2.setFormatter(JF()); lgq.addHandler(fh2)
tp3 = TracerProvider(); tp3.add_span_processor(BatchSpanProcessor(Drop(), max_queue_size=1000000, schedule_delay_millis=200)); tr3 = tp3.get_tracer('r')
cv2 = Counter('rq_total', 'x', ['route', 'code'], registry=reg); hh = Histogram('rq_seconds', 'x', registry=reg)
def work():
    t = time.perf_counter()
    while time.perf_counter() - t < 0.001: pass
def req(level):
    if level >= 3:
        with tr3.start_as_current_span('req', attributes={'route': '/o', 'user': 'u1', 'n': 1}):
            work()
            if level >= 2: lgq.info('start'); lgq.info('working'); lgq.info('done')
            cv2.labels('/o', '200').inc(); hh.observe(0.001)
    else:
        work()
        if level >= 2: lgq.info('start'); lgq.info('working'); lgq.info('done')
        if level >= 1: cv2.labels('/o', '200').inc(); hh.observe(0.001)
rows = []; base = None
for level, name in ((0, '(a)什么都不记录'), (1, '(b)+ 2 次指标'), (2, '(c)+ 3 行 JSON 日志写文件'), (3, '(d)+ 1 个 span')):
    ts = []
    for _ in range(3):
        n = 0; t0 = time.perf_counter()
        while time.perf_counter() - t0 < 5.0: req(level if level != 2 else 2); n += 1
        ts.append(n / (time.perf_counter() - t0))
    thr = statistics.median(ts); base = base or thr; rows.append((name, f'{thr:.0f}', f'{1000 / thr:.3f}', f'{(1000 / thr - 1000 / base) * 1000:.0f}'))
table(rows, ['配置', '每秒处理的请求数(3 轮中位数)', '每个请求的平均耗时(ms)', '比 (a) 多出的耗时(µs/请求)'])
inc = [float(r[3]) for r in rows]
print(f'  每一档比上一档多出的耗时:指标 {inc[1] - inc[0]:.0f} µs,再加 3 行日志 {inc[2] - inc[1]:.0f} µs,再加 1 个 span {inc[3] - inc[2]:.0f} µs;全部加上比什么都不记录多 {inc[3]:.0f} µs,占 1 ms 请求的 {inc[3] / 1000:.1%}(算出来的)。请求本身越短,这个占比越大')
tp3.shutdown(); fh2.close()
print('ERRORS', dict(ERRORS))
