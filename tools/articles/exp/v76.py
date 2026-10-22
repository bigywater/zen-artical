import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import logging, re, concurrent.futures
from opentelemetry import trace, propagate, context as otctx
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
import opentelemetry.sdk.version as otv
tee('v76'); reset()
print(f'日志:结构化日志与关联 trace_id。Python logging + OpenTelemetry Python SDK {otv.__version__};Collector contrib 0.163.1 的 filelog 接收器解析 JSON 日志。(一)文本日志与 JSON 日志的体积和解析;(二)哪些日志行能带上 trace_id;(三)Collector 读 JSON 日志并把 trace_id 放进 OTLP 日志记录;(四)采样之后日志里的 trace_id 能不能找到对应的 trace')

# ============ 一 ============
print('== 一:文本日志与 JSON 日志。同样的 20 万个事件(订单创建,带 user、order、amount、latency_ms 四个字段),分别写成文本行(key=value)和 JSON 行;其中 2% 的事件有一段带 “user=…” 字样的错误消息。比较:体积、提取 user 和 amount 的耗时(文本用正则、JSON 用 json.loads)、以及提取出的 user 与真实 user 不一致的行数')
rnd = random.Random(2); N = 200000; ev = []
for i in range(N):
    err = rnd.random() < 0.02
    ev.append(dict(user=f'u{rnd.randrange(5000)}', order=f'o{i}', amount=round(rnd.uniform(1, 500), 2), lat=rnd.randrange(5, 400), level='ERROR' if err else 'INFO', msg=(f'payment rejected: user=guest{rnd.randrange(9)} not allowed' if err else 'order created')))
text = [f'2026-10-19 12:00:00,{i % 1000:03d} {e["level"]} order-svc {e["msg"]} user={e["user"]} order={e["order"]} amount={e["amount"]} latency_ms={e["lat"]}' for i, e in enumerate(ev)]
js = [json.dumps({'ts': f'2026-10-19T12:00:00.{i % 1000:03d}Z', 'level': e['level'], 'service': 'order-svc', 'msg': e['msg'], 'user': e['user'], 'order': e['order'], 'amount': e['amount'], 'latency_ms': e['lat']}, ensure_ascii=False) for i, e in enumerate(ev)]
rx = re.compile(r'user=(\S+).*amount=(\S+)')
t = time.perf_counter(); got_t = [rx.search(l) for l in text]; dt_text = time.perf_counter() - t
t = time.perf_counter(); got_j = [json.loads(l) for l in js]; dt_json = time.perf_counter() - t
bad = sum(1 for m, e in zip(got_t, ev) if m.group(1) != e['user']); bad_j = sum(1 for d, e in zip(got_j, ev) if d['user'] != e['user'])
table([('文本行(key=value)', f'{sum(len(l) + 1 for l in text) / 1e6:.1f} MB', f'{sum(len(l) + 1 for l in text) / N:.0f}', f'{dt_text:.2f} s', bad), ('JSON 行', f'{sum(len(l) + 1 for l in js) / 1e6:.1f} MB', f'{sum(len(l) + 1 for l in js) / N:.0f}', f'{dt_json:.2f} s', bad_j)], ['格式', '20 万行的体积', '平均每行字节数', '提取字段的耗时(CPython)', 'user 提取错误的行数'])
print('  JSON 每行多了键名和引号,体积更大,但解析是确定的;文本行用正则提取,消息正文里恰好出现 “user=…” 时贪婪匹配会取错字段(这里的错误行就是那 2% 的错误消息)。结构化日志用字段而不是正文来承载信息,查询和聚合更可靠')

# ============ 二 ============
print('== 二:哪些日志行能带上 trace_id。一个服务的请求处理函数(每个请求一个 SERVER span),日志过滤器从当前 span 取 trace_id 和 span_id。每个请求里有几种写日志的位置:(a)请求处理函数里(span 内);(b)请求处理完、span 结束之后;(c)线程池里的任务(没有传递上下文);(d)线程池里的任务(用 copy_context().run 传递上下文)。2000 个请求,统计每种位置写出的日志行里有多少带有效的 trace_id')
tp = TracerProvider(); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); tracer = tp.get_tracer('v76')
LOG = []; llk = threading.Lock()
class TraceFilter(logging.Filter):
    def filter(self, rec):
        sc = trace.get_current_span().get_span_context(); rec.trace_id = format(sc.trace_id, '032x') if sc.is_valid else None; rec.span_id = format(sc.span_id, '016x') if sc.is_valid else None; return True
class Collect(logging.Handler):
    def emit(self, rec):
        with llk: LOG.append({'where': getattr(rec, 'where', '?'), 'svc': rec.name, 'trace_id': rec.trace_id, 'span_id': rec.span_id, 'level': rec.levelname, 'msg': rec.getMessage()})
lg = logging.getLogger('B'); lg.setLevel(logging.INFO); lg.addFilter(TraceFilter()); lg.addHandler(Collect()); lg.propagate = False
pool = concurrent.futures.ThreadPoolExecutor(4)
def call_b(i):
    ctx = None
    with tracer.start_as_current_span('B handle', kind=SpanKind.SERVER):
        lg.info('handling', extra={'where': 'a_in_span'})
        f1 = pool.submit(lambda: lg.info('async task', extra={'where': 'c_pool_no_ctx'}))
        f2 = pool.submit(contextvars.copy_context().run, lambda: lg.info('async task', extra={'where': 'd_pool_ctx'}))
        f1.result(); f2.result()
    lg.info('done', extra={'where': 'b_after_span'})
import contextvars
for i in range(2000): call_b(i)
rows = []
for w, name in (('a_in_span', '(a)请求处理函数里(span 内)'), ('b_after_span', '(b)span 结束之后'), ('c_pool_no_ctx', '(c)线程池任务,没传上下文'), ('d_pool_ctx', '(d)线程池任务,copy_context().run')):
    ls = [l for l in LOG if l['where'] == w]; ok = sum(1 for l in ls if l['trace_id']); rows.append((name, len(ls), ok, f'{ok / len(ls):.0%}'))
table(rows, ['日志位置', '日志行数', '带有效 trace_id 的行数', '比例'])
print('  日志过滤器读的是“当前 span”:在 span 内、或者把上下文传到了新线程里,日志才有 trace_id;span 结束之后、没有传递上下文的线程里写的日志,trace_id 是空的,查 trace_id 的时候这些行就找不到了')

# ============ 三 ============
print('== 三:Collector 的 filelog 接收器。把 JSON 日志(每行含 time、level、msg、service、trace_id、span_id)写到文件,Collector 用 filelog 接收器 + json_parser 解析时间、严重级别,再用 trace_parser 把 trace_id、span_id 放进 OTLP 日志记录的专门字段;输出到 file exporter。看输出里一条记录的字段')
logf = TT / 'v76_app.log'; outf = TT / 'v76_out.jsonl'
for f in (logf, outf): f.unlink(missing_ok=True)
logf.write_text('')
cfg = f'''receivers:
  filelog:
    include: ['{logf}']
    start_at: beginning
    operators:
      - type: json_parser
        timestamp: {{parse_from: attributes.time, layout: '%Y-%m-%dT%H:%M:%S.%LZ'}}
        severity: {{parse_from: attributes.level}}
      - type: trace_parser
        trace_id: {{parse_from: attributes.trace_id}}
        span_id: {{parse_from: attributes.span_id}}
exporters:
  file: {{path: {outf}}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    logs: {{receivers: [filelog], exporters: [file]}}
'''
oc = Otelcol('v76oc', cfg).start()
tid = '4bf92f3577b34da6a3ce929d0e0e4736'; sid = '00f067aa0ba902b7'
with open(logf, 'a') as f:
    f.write(json.dumps({'time': '2026-10-19T12:00:01.250Z', 'level': 'ERROR', 'service': 'order-svc', 'msg': 'payment failed', 'user': 'u1', 'trace_id': tid, 'span_id': sid}) + '\n')
    f.write(json.dumps({'time': '2026-10-19T12:00:02.500Z', 'level': 'INFO', 'service': 'order-svc', 'msg': 'no trace here', 'user': 'u2'}) + '\n')
    f.flush()
t0 = time.time()
while time.time() - t0 < 20 and not (outf.exists() and outf.stat().st_size > 0): time.sleep(0.2)
time.sleep(1.0); oc.stop()
recs = []
for line in open(outf):
    for rl in json.loads(line)['resourceLogs']:
        for sl in rl['scopeLogs']:
            for r in sl['logRecords']: recs.append(r)
for r in recs:
    attrs = {a['key']: list(a['value'].values())[0] for a in r.get('attributes', [])}
    print(f'  记录 body={list(r["body"].values())[0][:40]!r} severityText={r.get("severityText")} severityNumber={r.get("severityNumber")} timeUnixNano={r.get("timeUnixNano")} traceId={r.get("traceId", "(空)")!r} spanId={r.get("spanId", "(空)")!r}')
    print(f'      attributes 里还有的键:{sorted(attrs)}')
print('  trace_parser 把 trace_id 和 span_id 从属性提升到 OTLP 日志记录的 traceId / spanId 专门字段(后端据此把日志挂到 trace 上);没有 trace_id 的日志行这两个字段是空的')

# ============ 四 ============
print('== 四:采样之后日志里的 trace_id 能不能找到 trace。追踪用 ParentBased(TraceIdRatioBased(10%)) 采样,但日志每一行都带 trace_id(未采样的请求,span 上下文仍然有效,只是不被记录)。1000 个请求每个写 1 行日志,统计:日志里的不同 trace_id 个数,和其中在导出的 span 里能找到的个数')
tp2 = TracerProvider(sampler=ParentBased(TraceIdRatioBased(0.1))); mem2 = InMemorySpanExporter(); tp2.add_span_processor(SimpleSpanProcessor(mem2)); tr2 = tp2.get_tracer('s')
lg2 = logging.getLogger('S'); lg2.setLevel(logging.INFO); lg2.addFilter(TraceFilter()); lg2.propagate = False; H2 = Collect(); lg2.addHandler(H2); LOG.clear()
for i in range(1000):
    with tr2.start_as_current_span('req'): lg2.info('request handled', extra={'where': 's'})
tids_log = {l['trace_id'] for l in LOG if l['trace_id']}; tids_span = {format(s.context.trace_id, '032x') for s in mem2.get_finished_spans()}
print(f'  日志里不同的 trace_id:{len(tids_log)} 个;导出的 span 里能找到的:{len(tids_log & tids_span)} 个({len(tids_log & tids_span) / len(tids_log):.0%});其余 {len(tids_log - tids_span)} 个 trace_id 在追踪后端里没有对应的 trace(点日志里的 trace_id 链接会打不开)')
print('ERRORS', dict(ERRORS))
