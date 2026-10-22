import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import subprocess as sp, concurrent.futures, contextvars
from opentelemetry import trace, propagate, context as otctx
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
import opentelemetry.sdk.version as otv
tee('v63'); reset()
print(f'span 树错乱的常见原因和时钟偏移的影响。OpenTelemetry Python SDK {otv.__version__}。(一)调用方与下游在两个进程里,下游进程的 SDK 时钟函数加上固定偏移(模拟机器之间的时钟不同步);(二)忘记 detach 上下文造成的串线;(三)异步任务比父 span 活得久;(四)导出时随机丢 span 造成的残缺 trace')
D = TT / 'v63'; D.mkdir(exist_ok=True); CHILD = pathlib.Path(__file__).resolve().parent.parent / 'vtmp/v63/child.py'
def mkprov():
    tp = TracerProvider(); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); return tp, mem

# ============ 一 ============
print('== 一:时钟偏移。调用方进程(时钟正常)每个请求创建一个 CLIENT span 去调下游;下游进程的时钟比调用方快(正数)或慢(负数)一个固定偏移,下游处理约 3 ms。每种偏移发 100 个请求。统计:下游 SERVER span 的开始时间早于它的父 CLIENT span 的开始时间的请求数("子比父先开始"),下游 span 的结束时间晚于父 span 结束时间的请求数,以及“表观网络耗时”(下游开始时间 − 调用方开始时间)的中位数')
rows = []
for skew in (0, 5, 20, -5, -20, 100):
    outf = D / f'spans_{skew}.jsonl'; outf.unlink(missing_ok=True); port = free_port()
    p = sp.Popen([sys.executable, str(CHILD), str(port), str(skew), str(outf)], stdout=sp.PIPE, text=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}); assert p.stdout.readline().strip() == 'ready'
    tp, mem = mkprov(); tr = tp.get_tracer('front')
    for i in range(100):
        with tr.start_as_current_span('front call', kind=SpanKind.CLIENT):
            h = {}; propagate.inject(h); rpc(port, '/x', 5.0, h, keepalive=False)
    time.sleep(0.3); p.kill()
    cs = {format(s.context.span_id, '016x'): s for s in mem.get_finished_spans()}
    ch = [json.loads(l) for l in outf.read_text().splitlines()]
    before = after = 0; app = []
    for c in ch:
        par = cs[c['parent']]
        if c['start'] < par.start_time: before += 1
        if c['end'] > par.end_time: after += 1
        app.append((c['start'] - par.start_time) / 1e6)
    rows.append((f'{skew:+d} ms' if skew else '0(同步)', len(ch), before, after, f'{statistics.median(app):.2f}'))
table(rows, ['下游时钟相对调用方', '请求数', '下游 span 比父 span 先开始', '下游 span 比父 span 后结束', '表观网络耗时中位数(ms,下游开始 − 调用方开始)'])
print('  下游时钟偏快时,子 span 看起来在父 span 开始很久之后才开始、甚至在父 span 结束之后才结束;偏慢时子 span 看起来比父 span 先开始。追踪后端画出来的瀑布图、算出来的网络耗时都会受影响;父子关系本身(parent_id)不受时钟影响')

# ============ 二 ============
print('== 二:忘记 detach 造成串线。一个只有 1 个线程的线程池处理 6 个请求;每个请求在线程里先 attach 一个“请求上下文”(带一个新的根 span)、处理完应该 detach。(a)正确地 detach;(b)忘记 detach。统计 6 个请求里有多少个请求的根 span 却带着父 span(父是上一个请求),以及一共出现了几个 trace')
def run_pool(forget):
    tp, mem = mkprov(); tr = tp.get_tracer('pool'); rids = {}
    def handle(i):
        root = tr.start_span(f'request-{i}'); ctx = trace.set_span_in_context(root); tok = otctx.attach(ctx)
        try:
            with tr.start_as_current_span(f'work-{i}'): pass
        finally:
            root.end()
            if not forget: otctx.detach(tok)
        return i
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        for i in range(6): ex.submit(handle, i).result()
    spans = {s.name: s for s in mem.get_finished_spans()}
    bad = sum(1 for i in range(6) if spans[f'request-{i}'].parent is not None)        # 本该是根的请求 span,却有父 span
    return bad, len({s.context.trace_id for s in spans.values()}), max(len(str(0)) for _ in [0])
b1 = run_pool(False); b2 = run_pool(True)
table([('(a)正确 detach', f'{b1[0]} / 6', b1[1]), ('(b)忘记 detach', f'{b2[0]} / 6', b2[1])], ['做法', '本该是根 span、却有父 span 的请求数', '6 个请求一共出现的 trace 数'])
print('  线程池里的线程会被复用,没有 detach 的上下文留在线程里,后面的请求创建 span 时以它为父:每个请求的根 span 被挂在了上一个请求的 span 下面,6 个互不相干的请求并成了一个 trace')

# ============ 三 ============
print('== 三:异步任务比父 span 活得久。请求处理里用 fire-and-forget 起一个后台任务(耗时 200 ms),请求本身约 10 ms 就结束了,span 在请求结束时关闭。统计父子 span 的时间关系')
tp, mem = mkprov(); tr = tp.get_tracer('ff'); ths = []
with tr.start_as_current_span('request') as p:
    ctx = otctx.get_current()
    def bg():
        tok = otctx.attach(ctx)
        try:
            with tr.start_as_current_span('background'): time.sleep(0.2)
        finally: otctx.detach(tok)
    t = threading.Thread(target=bg); t.start(); time.sleep(0.01)
t.join(); sps = {s.name: s for s in mem.get_finished_spans()}; rq, bgs = sps['request'], sps['background']
print(f'  request span:{(rq.end_time - rq.start_time) / 1e6:.1f} ms;background span(是 request 的子 span:{bgs.parent is not None and bgs.parent.span_id == rq.context.span_id}):{(bgs.end_time - bgs.start_time) / 1e6:.1f} ms;background 比 request 晚结束 {(bgs.end_time - rq.end_time) / 1e6:.1f} ms。按 trace 里“根 span 的耗时”统计这次请求耗时是 {(rq.end_time - rq.start_time) / 1e6:.1f} ms,按“trace 里最晚的 span 结束时间 − 最早的开始时间”统计是 {(max(s.end_time for s in sps.values()) - min(s.start_time for s in sps.values())) / 1e6:.1f} ms,两者之比 {(max(s.end_time for s in sps.values()) - min(s.start_time for s in sps.values())) / (rq.end_time - rq.start_time):.1f} 倍')

# ============ 四 ============
print('== 四:导出时丢了 span。每个 trace 有 5 个 span(1 个根、4 个子 span,树形:根 → 2 个中间 span → 各 1 个叶子)。导出器以固定概率随机丢弃 span(种子固定),共 2000 个 trace,统计收到的 trace 里:完整的、缺根的(出现“孤儿”span:父 span 没有收到)、其他不完整的')
class Lossy(SpanExporter):
    def __init__(self, p): self.p, self.rnd, self.kept = p, random.Random(1), []
    def export(self, spans):
        for s in spans:
            if self.rnd.random() >= self.p: self.kept.append(s)
        return SpanExportResult.SUCCESS
rows = []
for pl in (0.0, 0.01, 0.05, 0.2):
    tp = TracerProvider(); lo = Lossy(pl); tp.add_span_processor(SimpleSpanProcessor(lo)); tr = tp.get_tracer('lossy')
    for i in range(2000):
        with tr.start_as_current_span('root'):
            for j in range(2):
                with tr.start_as_current_span(f'mid{j}'):
                    with tr.start_as_current_span(f'leaf{j}'): pass
    by = collections.defaultdict(list)
    for s in lo.kept: by[s.context.trace_id].append(s)
    full = orphan = other = gone = 0
    for tid, ss in by.items():
        ids = {s.context.span_id for s in ss}; names = {s.name for s in ss}
        has_orphan = any(s.parent is not None and s.parent.span_id not in ids for s in ss)
        if len(ss) == 5: full += 1
        elif has_orphan: orphan += 1
        else: other += 1
    gone = 2000 - len(by)
    rows.append((f'{pl:.0%}', full, orphan, other, gone))
table(rows, ['每个 span 被丢弃的概率', '完整的 trace', '有孤儿 span 的 trace(父 span 丢了)', '不完整但没有孤儿(只丢了叶子)', '一个 span 都没收到'])
print('  丢掉任何一个非叶子 span,它的子 span 就成了孤儿,追踪后端要么把它们当作新的根,要么显示“缺失的父 span”;丢的概率是按 span 算的,一个 trace 有 5 个 span,完整的 trace 比例比 1 减去丢弃概率低得多')
print('ERRORS', dict(ERRORS))
