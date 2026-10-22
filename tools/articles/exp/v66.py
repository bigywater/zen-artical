import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import logging, subprocess as sp
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
import opentelemetry.sdk.version as otv
tee('v66'); reset()
class Cap(logging.Handler):
    def __init__(self): super().__init__(); self.msgs = collections.Counter()
    def emit(self, r): self.msgs[r.getMessage()[:70]] += 1
CAP = Cap(); lg = logging.getLogger('opentelemetry'); lg.addHandler(CAP); lg.propagate = False; lg.setLevel(logging.WARNING)
print(f'OpenTelemetry SDK 的批量导出与丢弃策略。OpenTelemetry Python SDK {otv.__version__} 的 BatchSpanProcessor(默认 max_queue_size=2048,max_export_batch_size=512,schedule_delay_millis=5000,export_timeout_millis=30000)+ OTLP/HTTP 导出器,发给我自己写的接收端(可以让它变慢、返回 503 或者整个停掉)。每个 span 带一个序号属性 seq,用来看丢的是哪些')

class Receiver:
    def __init__(self, port=None):
        self.delay = 0.0; self.mode = 'ok'; self.seqs = []; self.lk = threading.Lock(); self.reqs = 0; self.sizes = []
        def app(h):
            n = int(h.headers.get('Content-Length', 0)); body = h.rfile.read(n); self.reqs += 1; self.sizes.append(n)
            if self.mode == 'fail503': h.reply(503, b'busy'); return
            if self.delay: time.sleep(self.delay)
            req = ExportTraceServiceRequest(); req.ParseFromString(body); got = []
            for rs in req.resource_spans:
                for ss in rs.scope_spans:
                    for sp_ in ss.spans:
                        for a in sp_.attributes:
                            if a.key == 'seq': got.append(a.value.int_value)
            with self.lk: self.seqs += got
            h.reply(200, b'')
        self.svc = Svc(app, 'otlp', port=port); self.port = self.svc.port
    def stop(self): self.svc.stop()
def mkprov(rc, **kw):
    tp = TracerProvider(); exp = OTLPSpanExporter(endpoint=f'http://127.0.0.1:{rc.port}/v1/traces', timeout=kw.pop('timeout', 10)); bsp = BatchSpanProcessor(exp, **kw); tp.add_span_processor(bsp); return tp, tp.get_tracer('b')
def produce(tr, n, rate=None):
    t0 = time.perf_counter(); costs = []
    for i in range(n):
        if rate:
            d = t0 + i / rate - time.perf_counter()
            if d > 0: time.sleep(d)
        t1 = time.perf_counter()
        with tr.start_as_current_span('s', attributes={'seq': i}): pass
        costs.append(time.perf_counter() - t1)
    return costs
def ranges(seqs):
    xs = sorted(set(seqs)); out = []
    for x in xs:
        if out and x == out[-1][1] + 1: out[-1][1] = x
        else: out.append([x, x])
    return ','.join(f'{a}-{b}' for a, b in out)
def summarize(rc, n):
    got = sorted(set(rc.seqs)); lost = n - len(got)
    return len(got), lost, (f'{got[0]}~{got[-1]}' if got else '-')

# ============ 一 ============
print('== 一:接收端变慢。默认参数的 BatchSpanProcessor,以 1000 个 span/秒的速度产生 6000 个 span(6 s),接收端每次请求处理 1.5 s。产生完之后等 20 s 再统计接收到了多少个 span,收到的序号范围,以及 SDK 打的 warning')
rc = Receiver(); rc.delay = 1.5; tp, tr = mkprov(rc); CAP.msgs.clear()
costs = produce(tr, 6000, rate=1000); t_prod_end = time.time(); time.sleep(20.0)
got, lost, rng = summarize(rc, 6000)
print(f'  接收端收到 {got} 个 span,没收到(丢了){lost} 个;收到的序号范围 {rng};接收端一共处理了 {rc.reqs} 个请求;产生 span 的调用(start 到 end)耗时中位数 {statistics.median(costs) * 1e6:.0f} µs、p99 {pct(costs, 99) * 1e6:.0f} µs、最大 {max(costs) * 1e3:.2f} ms;SDK 的 warning:' + ';'.join(f'“{m}…”× {n}' for m, n in CAP.msgs.items()))
seq_sorted = sorted(set(rc.seqs)); first_block = [s for s in seq_sorted if s < 2048]; last = [s for s in seq_sorted if s >= 4000]
print(f'  收到的序号区间(连续的一段算一个区间):{ranges(rc.seqs)}')
tp.shutdown(); rc.stop()

# ============ 二 ============
print('== 二:队列大小。同样的慢接收端(1.5 s/请求)和 6000 个 span,max_queue_size 分别是 512、2048(默认)、20000;max_export_batch_size 保持 512。产生完等 30 s 再统计')
rows = []
for q in (512, 2048, 20000):
    rc = Receiver(); rc.delay = 1.5; tp, tr = mkprov(rc, max_queue_size=q); produce(tr, 6000, rate=1000); time.sleep(30.0); got, lost, rng = summarize(rc, 6000); rows.append((q, got, lost, rng, rc.reqs)); tp.shutdown(); rc.stop()
table(rows, ['max_queue_size', '收到', '丢了', '收到的序号范围', '接收端处理的请求数'])
print('  接收端每次请求处理 1.5 s、一批最多 512 个 span,所以持续的处理能力有上限;产生速度超过它,队列装不下的 span 就被丢弃,队列越大能缓冲的越多,但内存也随之增加')

# ============ 三 ============
print('== 三:突发。接收端正常(无延迟),在 0.1 s 内突然产生 10000 个 span。比较 max_queue_size=2048(默认)与 20000;max_export_batch_size 512。等 10 s 后统计')
rows = []
for q in (2048, 20000):
    rc = Receiver(); tp, tr = mkprov(rc, max_queue_size=q); CAP.msgs.clear(); produce(tr, 10000); time.sleep(10.0); got, lost, rng = summarize(rc, 10000)
    rows.append((q, got, lost, rng, rc.reqs, f'{statistics.mean(rc.sizes) / 1000:.0f} KB' if rc.sizes else '-', sum(CAP.msgs.values()))); tp.shutdown(); rc.stop()
table(rows, ['max_queue_size', '收到', '丢了', '收到的序号范围', '请求数', '平均每个请求体', 'SDK warning 条数'])
print('  产生 span 的线程比导出线程快,队列装满之后新来的(或最老的)被丢;队列够大时突发能被吸收')

# ============ 四 ============
print('== 四:接收端故障。接收端先正常,第 2 s 起返回 503,第 8 s 恢复。以 200 个 span/秒产生 12 s(共 2400 个 span),导出器超时 10 s(默认的重试在超时内退避重试)。(a)接收端返回 503;(b)接收端整个停掉(连接被拒),第 8 s 在同一个端口重新启动。统计收到多少、丢了多少')
rows = []
for mode in ('503', 'down'):
    rc = Receiver(); port = rc.port; tp, tr = mkprov(rc, timeout=10); CAP.msgs.clear()
    def chaos():
        time.sleep(2.0)
        if mode == '503': rc.mode = 'fail503'
        else: rc.stop()
        time.sleep(6.0)
        if mode == '503': rc.mode = 'ok'
        else:
            global rc2
            rc2 = Receiver(port=port)
    rc2 = None; th = threading.Thread(target=chaos); th.start(); produce(tr, 2400, rate=200); th.join(); time.sleep(25.0)
    seqs = list(rc.seqs) + (list(rc2.seqs) if rc2 else []); got = len(set(seqs)); rows.append(('(a)503' if mode == '503' else '(b)停掉再重启', got, 2400 - got, f'{min(seqs)}~{max(seqs)}' if seqs else '-', ';'.join(f'{m[:40]}… × {n}' for m, n in CAP.msgs.items())[:160]))
    tp.shutdown(); rc.stop()
    if rc2: rc2.stop()
table(rows, ['故障方式', '收到', '丢了', '收到的序号范围', 'SDK 的 warning(去重 × 次数)'])

print('== 四(续):长时间故障。接收端返回 503 的时间拉长到 20 s(第 2 s 到第 22 s),以 200 个 span/秒产生 30 s(共 6000 个 span),导出器超时 10 s,默认队列 2048。等 40 s 后统计')
rc = Receiver(); tp, tr = mkprov(rc, timeout=10); CAP.msgs.clear()
def chaos2():
    time.sleep(2.0); rc.mode = 'fail503'; time.sleep(20.0); rc.mode = 'ok'
th = threading.Thread(target=chaos2); th.start(); produce(tr, 6000, rate=200); th.join(); time.sleep(40.0)
got, lost, rng = summarize(rc, 6000)
print(f'  收到 {got} 个,丢了 {lost} 个;收到的序号区间:{ranges(rc.seqs)};SDK 的 warning:' + ';'.join(f'“{m}…”× {n}' for m, n in CAP.msgs.items()))
tp.shutdown(); rc.stop()

# ============ 五 ============
print('== 五:进程退出。子进程产生 1000 个 span(导出间隔设成默认的 5 s,所以还有很多在队列里),然后分别用三种方式结束:(a)正常退出(SDK 注册的 atexit 钩子会 shutdown);(b)os._exit(0)(不跑钩子);(c)产生完 1 s 后被 SIGKILL。统计接收端收到多少')
CHILD = r'''
import sys, os, time
sys.path.insert(0, %r)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
port, how = int(sys.argv[1]), sys.argv[2]
tp = TracerProvider(); tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f'http://127.0.0.1:{port}/v1/traces'))); tr = tp.get_tracer('c')
import opentelemetry.trace as t
t.set_tracer_provider(tp)
for i in range(1000):
    with tr.start_as_current_span('s', attributes={'seq': i}): pass
if how == 'normal': sys.exit(0)
if how == 'exit': os._exit(0)
print('ready', flush=True); time.sleep(60)
''' % str(pathlib.Path(__file__).resolve().parent.parent)
(TT / 'v66_child.py').write_text(CHILD); rows = []
for how, name in (('normal', '(a)正常退出'), ('exit', '(b)os._exit(0)'), ('kill', '(c)产生完 1 s 后 SIGKILL')):
    rc = Receiver(); p = sp.Popen([sys.executable, str(TT / 'v66_child.py'), str(rc.port), how], stdout=sp.PIPE, text=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
    if how == 'kill': p.stdout.readline(); time.sleep(1.0); p.kill()
    p.wait(); time.sleep(1.0); got, lost, rng = summarize(rc, 1000); rows.append((name, got, lost, rc.reqs)); rc.stop()
table(rows, ['结束方式', '收到', '丢了', '接收端处理的请求数'])
print('  队列里还没导出的 span,进程不经过 shutdown 就退出(os._exit、被杀)就永远丢了;正常退出时 SDK 的 atexit 钩子会把队列刷出去')
print('ERRORS', dict(ERRORS))
