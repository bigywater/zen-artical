import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import subprocess as sp
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased, ALWAYS_ON
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import StatusCode, SpanKind
import opentelemetry.sdk.version as otv
tee('v64'); reset()
print(f'采样:头部采样与尾部采样。OpenTelemetry Python SDK {otv.__version__} 的采样器(TraceIdRatioBased、ParentBased)和 OpenTelemetry Collector contrib 0.163.1 的 tail_sampling 处理器。工作负载:3000 个 trace,每个 trace 4 个 span;其中 2% 的 trace 里有一个 span 状态是 ERROR,3% 的 trace 总耗时 800 ms(其余约 30 ms),固定随机种子,时间戳是按设定值写入的')
N, P_ERR, P_SLOW = 3000, 0.02, 0.03
def plan(seed=5):
    rnd = random.Random(seed); out = []
    for i in range(N):
        r = rnd.random(); kind = 'error' if r < P_ERR else ('slow' if r < P_ERR + P_SLOW else 'ok'); out.append(kind)
    return out
PLAN = plan(); CNT = collections.Counter(PLAN)
def gen(tracer_for, kinds, late_leaf_s=0.0, rate_sleep=0.0):
    """tracer_for(i)->tracer。每个 trace:root → mid → (leaf1, leaf2),时间戳按设定值写入;error 的 trace 里 leaf2 状态为 ERROR;slow 的 trace 总耗时 800 ms"""
    ids = []
    for i, k in enumerate(kinds):
        tr = tracer_for(i); t0 = time.time_ns(); dur = 800_000_000 if k == 'slow' else 30_000_000
        root = tr.start_span('root', start_time=t0, kind=SpanKind.SERVER); rc = trace.set_span_in_context(root)
        mid = tr.start_span('mid', context=rc, start_time=t0 + 1_000_000); mc = trace.set_span_in_context(mid)
        l1 = tr.start_span('leaf1', context=mc, start_time=t0 + 2_000_000); l1.end(end_time=t0 + 10_000_000)
        l2 = tr.start_span('leaf2', context=mc, start_time=t0 + 3_000_000)
        if k == 'error': l2.set_status(StatusCode.ERROR, 'boom')
        def finish_l2(l2=l2, t0=t0, dur=dur): l2.end(end_time=t0 + dur - 2_000_000)
        if late_leaf_s: threading.Timer(late_leaf_s, finish_l2).start()
        else: finish_l2()
        mid.end(end_time=t0 + dur - 1_000_000); root.end(end_time=t0 + dur)
        ids.append(root.get_span_context().trace_id)
        if rate_sleep: time.sleep(rate_sleep)
    return ids

# ============ 一 ============
print('== 一:头部采样。SDK 里用 TraceIdRatioBased(比例) 在 trace 的第一个 span 上决定要不要保留,3000 个 trace 全部生成一遍,看内存导出器里最后保留了多少 trace、多少 span,其中出错的 trace 和慢 trace 各保留了几个(分母是各类 trace 的总数)')
tot = dict(CNT)
rows = []
for ratio in (1.0, 0.1, 0.01):
    tp = TracerProvider(sampler=ParentBased(TraceIdRatioBased(ratio))); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); tr = tp.get_tracer('h')
    ids = gen(lambda i: tr, PLAN); kept = collections.Counter(); spans = mem.get_finished_spans(); byt = collections.defaultdict(int)
    keptids = {s.context.trace_id for s in spans}
    for tid, k in zip(ids, PLAN):
        if tid in keptids: kept[k] += 1
    rows.append((f'{ratio:.0%}', len(keptids), len(spans), f'{kept["error"]} / {tot["error"]}', f'{kept["slow"]} / {tot["slow"]}', f'{kept["ok"]} / {tot["ok"]}'))
table(rows, ['采样比例', '保留的 trace 数', '保留的 span 数', '出错的 trace 保留', '慢 trace 保留', '正常 trace 保留'])
print('  头部采样在 trace 开始时按 trace id 做决定,那时还不知道这个 trace 之后会不会出错、会不会变慢,所以出错和慢的 trace 和正常的 trace 以同样的比例被丢弃')

# ============ 二 ============
print('== 二:多个服务的采样决定要一致。A → B → C 三个服务各有自己的 TracerProvider,请求经 traceparent 头传递。(a)A 用 TraceIdRatioBased(10%) 做决定,B、C 用 ParentBased(跟随父 span 的采样标志);(b)三个服务都不看父 span,各自用不同比例的 TraceIdRatioBased:A 10%、B 50%、C 100%;(c)三个服务都不看父 span,用同一个比例 10%。每种发 3000 个请求,统计每个 trace 在后端收到的 span 数(每个服务一个 SERVER span,最多 3 个)')
def three(samplers):
    mems = []; tracers = []
    for name, smp in zip('ABC', samplers):
        tp = TracerProvider(sampler=smp); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); mems.append(mem); tracers.append(tp.get_tracer(name))
    tids = []
    for i in range(3000):
        carrier = {}
        sa = tracers[0].start_span('A', kind=SpanKind.SERVER); ca = trace.set_span_in_context(sa); propagate.inject(carrier, ca)
        sb = tracers[1].start_span('B', context=propagate.extract(carrier), kind=SpanKind.SERVER); cb = trace.set_span_in_context(sb); c2 = {}; propagate.inject(c2, cb)
        sc = tracers[2].start_span('C', context=propagate.extract(c2), kind=SpanKind.SERVER); sc.end(); sb.end(); sa.end(); tids.append(sa.get_span_context().trace_id)
    per = collections.Counter()
    for m in mems:
        for s in m.get_finished_spans(): per[s.context.trace_id] += 1
    dist = collections.Counter(per.values()); return dist, len(per)
rows = []
for name, smp in (('(a)A 按 10% 决定,B、C 跟随父 span', [ParentBased(TraceIdRatioBased(0.1)), ParentBased(TraceIdRatioBased(0.1)), ParentBased(TraceIdRatioBased(0.1))]),
                  ('(b)各自独立:A 10%、B 50%、C 100%', [TraceIdRatioBased(0.1), TraceIdRatioBased(0.5), TraceIdRatioBased(1.0)]),
                  ('(c)各自独立,同一个比例 10%', [TraceIdRatioBased(0.1)] * 3)):
    dist, n = three(smp); rows.append((name, n, dist.get(3, 0), dist.get(2, 0), dist.get(1, 0)))
table(rows, ['配置', '后端收到至少 1 个 span 的 trace 数', '收到 3 个 span 的(完整)', '收到 2 个 span 的', '只收到 1 个 span 的'])
print('  跟随父 span 的采样标志(或者所有服务使用同一个确定性比例)时,一个 trace 要么三个 span 都在,要么都不在;各服务用不同的比例独立决定,就会出现只有一部分 span 的残缺 trace')

# ============ 三 ============
print('== 三:尾部采样。应用把全部 span 通过 OTLP/gRPC 发给 Collector,Collector 的 tail_sampling 处理器等一个 trace 的所有 span 到齐(decision_wait 3 s)再决定:出错的 trace 全留、耗时超过 500 ms 的全留、其余按 5% 概率留。Collector 的 file exporter 把保留下来的 span 写成文件。看保留了什么,以及 Collector 的内存')
def collector_cfg(grpc_port, outfile, wait_s=3, extra_pipeline=''):
    return f'''receivers:
  otlp:
    protocols:
      grpc: {{endpoint: 127.0.0.1:{grpc_port}}}
processors:
  tail_sampling:
    decision_wait: {wait_s}s
    num_traces: 20000
    policies:
      - {{name: errors, type: status_code, status_code: {{status_codes: [ERROR]}}}}
      - {{name: slow, type: latency, latency: {{threshold_ms: 500}}}}
      - {{name: rest, type: probabilistic, probabilistic: {{sampling_percentage: 5, hash_salt: "x"}}}}
exporters:
  file/sampled: {{path: {outfile}}}
  file/all: {{path: {outfile}.all}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    traces/sampled: {{receivers: [otlp], processors: [tail_sampling], exporters: [file/sampled]}}
    traces/all: {{receivers: [otlp], exporters: [file/all]}}
'''
def read_traces(path):
    kinds = {}; spans = 0; tr_spans = collections.defaultdict(list)
    if not pathlib.Path(path).exists(): return tr_spans
    for line in open(path):
        d = json.loads(line)
        for rs in d.get('resourceSpans', []):
            for ss in rs.get('scopeSpans', []):
                for sp in ss.get('spans', []): tr_spans[sp['traceId']].append(sp)
    return tr_spans
def run_collector(wait_s, kinds, late_leaf_s=0.0, tag='a'):
    gp = free_port(); out = TT / f'v64_{tag}.jsonl'
    for f in (out, pathlib.Path(str(out) + '.all')): f.unlink(missing_ok=True)
    oc = Otelcol(f'v64oc{tag}', collector_cfg(gp, out, wait_s), gp).start()
    tp = TracerProvider(sampler=ALWAYS_ON); bsp = BatchSpanProcessor(OTLPSpanExporter(endpoint=f'127.0.0.1:{gp}', insecure=True), max_queue_size=100000, schedule_delay_millis=200, max_export_batch_size=2048); tp.add_span_processor(bsp); tr = tp.get_tracer('app')
    t0 = time.time(); ids = gen(lambda i: tr, kinds, late_leaf_s); tp.force_flush(); t_gen = time.time() - t0
    rss = [int(sp.run(['ps', '-o', 'rss=', '-p', str(oc.p.pid)], capture_output=True, text=True).stdout.strip() or 0) / 1024]
    return oc, out, ids, t_gen, rss, tp
oc, out, ids, t_gen, rss, tp = run_collector(3, PLAN, 0.0, 'a')
time.sleep(0.5); first_seen = None; t_wait0 = time.time()
while time.time() - t_wait0 < 12:
    if pathlib.Path(out).exists() and pathlib.Path(out).stat().st_size > 0: first_seen = time.time() - t_wait0; break
    time.sleep(0.1)
time.sleep(5.0); smp = read_traces(out); allt = read_traces(str(out) + '.all')
tid_hex = {format(t, '032x'): k for t, k in zip(ids, PLAN)}
kept = collections.Counter(tid_hex[t] for t in smp if t in tid_hex)
full = sum(1 for t, ss in smp.items() if len(ss) == 4)
sz_s = pathlib.Path(out).stat().st_size if pathlib.Path(out).exists() else 0; sz_a = pathlib.Path(str(out) + '.all').stat().st_size
table([('保留的 trace 数', len(smp), f'全部 {len(allt)}'), ('出错的 trace', f'{kept["error"]} / {tot["error"]}', ''), ('慢 trace', f'{kept["slow"]} / {tot["slow"]}', ''), ('正常 trace', f'{kept["ok"]} / {tot["ok"]}', f'目标 5%(约 {int(tot["ok"] * 0.05)} 个)'), ('保留下来的 trace 中 span 完整(4 个)的', f'{full} / {len(smp)}', ''), ('file exporter 文件大小(字节)', f'{sz_s:,}', f'全量 {sz_a:,}')], ['指标', '尾部采样后', '备注'])
print(f'  应用生成 3000 个 trace 花了 {t_gen:.1f} s;从应用 flush 完到 Collector 的采样输出文件第一次有内容用了 {first_seen:.1f} s(decision_wait 3 s);Collector 内存(RSS)在应用发完之后 {rss[0]:.0f} MB')
oc.stop(); tp.shutdown()

# ============ 四 ============
print('== 四:迟到的 span。同样的 tail_sampling 配置(decision_wait 2 s),100 个出错的 trace,其中出错的那个 leaf2 span 在 trace 的其他 span 发出之后延迟 0.5 s 或 4 s 才结束并发出(span 要结束才会导出)。看这 100 个出错的 trace 最后保留了多少')
rows = []
for late in (0.5, 4.0):
    kinds = ['error'] * 100; gp = free_port(); outf = TT / f'v64_late{int(late * 10)}.jsonl'; outf.unlink(missing_ok=True); pathlib.Path(str(outf) + '.all').unlink(missing_ok=True)
    oc = Otelcol(f'v64od{int(late * 10)}', collector_cfg(gp, outf, 2), gp).start()
    tp = TracerProvider(); tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f'127.0.0.1:{gp}', insecure=True), schedule_delay_millis=100)); tr = tp.get_tracer('app')
    ids = gen(lambda i: tr, kinds, late_leaf_s=late); time.sleep(late + 4.5); tp.force_flush(); time.sleep(3.0)
    smp = read_traces(outf); has_err = sum(1 for t, ss in smp.items() if any(sp.get('status', {}).get('code') in (2, 'STATUS_CODE_ERROR') for sp in ss))
    rows.append((f'{late} s', len(smp), has_err, sum(1 for ss in smp.values() if len(ss) == 4))); oc.stop(); tp.shutdown()
table(rows, ['出错的 span 比其他 span 晚发出', '保留的 trace 数(共 100 个出错的)', '其中含出错 span 的', '其中 4 个 span 都在的'])
print('  tail_sampling 在 decision_wait 到期时按当时收到的 span 做决定;出错 span 比 decision_wait 还晚到,决定时这个 trace 里还没有错误,出错的 trace 就按 5% 的概率保留')
print('ERRORS', dict(ERRORS))
