import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanLimits
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import StatusCode, SpanKind
import opentelemetry.sdk.version as otv
tee('v65'); reset()
import logging
class Cap(logging.Handler):
    def __init__(self): super().__init__(); self.msgs = collections.Counter()
    def emit(self, r): self.msgs[r.getMessage()[:90]] += 1
CAP = Cap(); lg = logging.getLogger('opentelemetry'); lg.addHandler(CAP); lg.propagate = False; lg.setLevel(logging.WARNING)
print(f'span 的属性、事件与状态。OpenTelemetry Python SDK {otv.__version__}:默认的数量/长度限制、超限时丢掉哪些、状态(UNSET / OK / ERROR)的设置规则、异常怎么记录、一个 span 序列化后有多大;最后用 Collector 0.163.1 的 attributes / transform 处理器去掉或打码属性里的敏感信息')
def mk(limits=None):
    tp = TracerProvider(span_limits=limits) if limits else TracerProvider(); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); return tp.get_tracer('t'), mem

# ============ 一 ============
L = SpanLimits()
print(f'== 一:默认限制与超限行为。SpanLimits 的默认值:max_attributes={L.max_attributes},max_events={L.max_events},max_links={L.max_links},max_event_attributes={L.max_event_attributes},max_link_attributes={L.max_link_attributes},max_attribute_length={L.max_attribute_length}(None 表示不限长度)。往同一个 span 里加 200 个属性(k0…k199)、200 个事件(e0…e199),看保留了多少、留下的是哪一段、丢了多少;再测属性值长度限制')
tr, mem = mk()
with tr.start_as_current_span('s') as sp:
    for i in range(200): sp.set_attribute(f'k{i}', i)
    for i in range(200): sp.add_event(f'e{i}')
s = mem.get_finished_spans()[0]; ks = [int(k[1:]) for k in s.attributes]; es = [int(e.name[1:]) for e in s.events]
print(f'  属性:保留 {len(s.attributes)} 个,键编号 {min(ks)}~{max(ks)},dropped_attributes={s.dropped_attributes};事件:保留 {len(s.events)} 个,编号 {min(es)}~{max(es)},dropped_events={s.dropped_events}')
tr, mem = mk(SpanLimits(max_attribute_length=20))
with tr.start_as_current_span('s') as sp: sp.set_attribute('long', 'x' * 100); sp.set_attribute('lst', ['y' * 50, 'z' * 5]); sp.set_attribute('num', 12345678901234567890)
s = mem.get_finished_spans()[0]
print('  这一步里 SDK 打出的 warning 日志(去重后的内容 × 次数):' + ';'.join(f'“{m}…”× {n}' for m, n in CAP.msgs.items())); CAP.msgs.clear()
print(f'  max_attribute_length=20 时:字符串 100 字符 → 保留 {len(s.attributes["long"])} 字符;字符串数组里 50 字符的元素 → {len(s.attributes["lst"][0])} 字符,5 字符的元素 → {len(s.attributes["lst"][1])} 字符;超大整数属性 → {s.attributes.get("num", "(没有这个属性)")!r}')
tr, mem = mk()
with tr.start_as_current_span('s') as sp:
    sp.set_attribute('v.str', 'v'); sp.set_attribute('v.list', [1, 2, 3]); sp.set_attribute('v.mixed_list', [1, 'a']); sp.set_attribute('v.map', {'a': 1}); sp.set_attribute('v.none', None); sp.set_attribute('v.object', object())
s = mem.get_finished_spans()[0]
print('  属性值的类型限制(保留下来的属性值):' + ';'.join(f'{k}={s.attributes[k]!r}' for k in sorted(s.attributes)) + f';SDK 的 warning 日志:' + ';'.join(f'“{m}…”× {n}' for m, n in CAP.msgs.items()) + '。没有抛异常')

# ============ 二 ============
CAP.msgs.clear()
print('== 二:状态与异常。set_status 的几种顺序;start_as_current_span 默认在异常离开 with 块时记录异常并把状态设为 ERROR;record_exception 本身不改状态')
def final(seq):
    tr, mem = mk()
    with tr.start_as_current_span('s') as sp:
        for st, d in seq: sp.set_status(st, d) if d is not None else sp.set_status(st)
    s = mem.get_finished_spans()[0]; return s.status.status_code.name, s.status.description
rows = []
for name, seq in (('什么都不设置', []), ('ERROR("a")', [(StatusCode.ERROR, 'a')]), ('ERROR("a") → ERROR("b")', [(StatusCode.ERROR, 'a'), (StatusCode.ERROR, 'b')]), ('ERROR → OK', [(StatusCode.ERROR, 'a'), (StatusCode.OK, None)]), ('OK → ERROR', [(StatusCode.OK, None), (StatusCode.ERROR, 'a')]), ('OK → UNSET', [(StatusCode.OK, None), (StatusCode.UNSET, None)]), ('ERROR → UNSET', [(StatusCode.ERROR, 'a'), (StatusCode.UNSET, None)]), ('OK 带描述', [(StatusCode.OK, 'fine')])):
    c, d = final(seq); rows.append((name, c, repr(d)))
table(rows, ['调用顺序', '最终状态', '描述'])
print('  SDK 的 warning 日志(去重 × 次数):' + ';'.join(f'“{m}…”× {n}' for m, n in CAP.msgs.items()))
def exc_case(**kw):
    tr, mem = mk()
    try:
        with tr.start_as_current_span('s', **kw): raise ValueError('boom')
    except ValueError: pass
    s = mem.get_finished_spans()[0]; ev = [e for e in s.events if e.name == 'exception']
    return s.status.status_code.name, repr(s.status.description), len(ev), (sorted(ev[0].attributes) if ev else [])
rows = [('默认(异常离开 with 块)', *exc_case()), ('record_exception=False', *exc_case(record_exception=False)), ('set_status_on_exception=False', *exc_case(set_status_on_exception=False)), ('两个都 False', *exc_case(record_exception=False, set_status_on_exception=False))]
tr, mem = mk()
with tr.start_as_current_span('s') as sp:
    try: raise KeyError('k')
    except KeyError as e: sp.record_exception(e)
s = mem.get_finished_spans()[0]; ev = [e for e in s.events if e.name == 'exception']; rows.append(('手动 record_exception(不设状态)', s.status.status_code.name, repr(s.status.description), len(ev), sorted(ev[0].attributes)))
table([(a, b, c, d, ','.join(e)) for a, b, c, d, e in rows], ['做法', '最终状态', '状态描述', 'exception 事件数', 'exception 事件的属性键'])

# ============ 三 ============
print('== 三:一个 span 序列化之后有多大。用 SDK 的 OTLP 编码器(protobuf)编码一个只含属性的 span,量字节数。(a)属性个数 0、10、50、128,每个值 20 个字符;(b)10 个属性,值长度 20、200、2000 个字符;(c)10 个事件(各带 2 个属性)')
def enc_size(span_fn):
    tr, mem = mk()
    with tr.start_as_current_span('s') as sp: span_fn(sp)
    return len(encode_spans(mem.get_finished_spans()).SerializeToString())
base = enc_size(lambda sp: None); rows = [('(a)0 个属性', base, 0)]
for n in (10, 50, 128):
    b = enc_size(lambda sp, n=n: [sp.set_attribute(f'attr.name.{i:03d}', 'v' * 20) for i in range(n)]); rows.append((f'(a){n} 个属性,值 20 字符', b, f'{(b - base) / n:.1f}'))
for ln in (20, 200, 2000):
    b = enc_size(lambda sp, ln=ln: [sp.set_attribute(f'attr.name.{i:03d}', 'v' * ln) for i in range(10)]); rows.append((f'(b)10 个属性,值 {ln} 字符', b, f'{(b - base) / 10:.1f}'))
b = enc_size(lambda sp: [sp.add_event(f'event.{i}', {'a': 'x' * 20, 'b': 12345}) for i in range(10)]); rows.append(('(c)10 个事件(各 2 个属性)', b, f'{(b - base) / 10:.1f}'))
table(rows, ['内容', '序列化后的 span 字节数', '平均每个属性/事件增加的字节数'])
print('  OTLP 里每个属性的键和值各占字节,键名(这里是 attr.name.NNN)也要付出空间,值越长越大;个数上限由 max_attributes 控制,值的长度上限由 max_attribute_length 控制')

# ============ 四 ============
print('== 四:属性里的敏感信息。span 带 user.email、password、http.url(url 里有 token=SECRET123 的查询参数)三个属性,通过 OTLP/gRPC 发给 Collector。(a)直接导出;(b)Collector 的 attributes 处理器删除 password、对 user.email 取哈希;transform 处理器用 OTTL 把 http.url 里的 token 值替换成 ***。比较 Collector 输出文件里这三个属性')
def cfg(gp, outf, procs):
    pl = ', '.join(procs)
    return f'''receivers:
  otlp:
    protocols:
      grpc: {{endpoint: 127.0.0.1:{gp}}}
processors:
  attributes/scrub:
    actions:
      - {{key: password, action: delete}}
      - {{key: user.email, action: hash}}
  transform/url:
    trace_statements:
      - replace_pattern(span.attributes["http.url"], "token=[^&]*", "token=***")
exporters:
  file: {{path: {outf}}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    traces: {{receivers: [otlp], processors: [{pl}], exporters: [file]}}
'''
def run_pii(procs, tag):
    gp = free_port(); outf = TT / f'v65_{tag}.jsonl'; outf.unlink(missing_ok=True)
    oc = Otelcol('v65' + tag, cfg(gp, outf, procs), gp).start()
    tp = TracerProvider(); tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f'127.0.0.1:{gp}', insecure=True), schedule_delay_millis=100)); tr = tp.get_tracer('app')
    with tr.start_as_current_span('login') as sp:
        sp.set_attribute('user.email', 'alice@example.com'); sp.set_attribute('password', 'hunter2'); sp.set_attribute('http.url', 'https://api.example.com/login?user=alice&token=SECRET123&x=1')
    tp.force_flush(); time.sleep(1.5); oc.stop(); tp.shutdown()
    attrs = {}
    for line in open(outf):
        for rs in json.loads(line)['resourceSpans']:
            for ss in rs['scopeSpans']:
                for s in ss['spans']:
                    for a in s['attributes']: attrs[a['key']] = list(a['value'].values())[0]
    return attrs
rows = []
for name, procs in (('(a)没有处理器', []), ('(b)attributes/scrub + transform/url', ['attributes/scrub', 'transform/url'])):
    a = run_pii(procs, name[1])
    rows.append((name, a.get('user.email', '(已删除)'), a.get('password', '(已删除)'), a.get('http.url', '(没有)')))
table(rows, ['配置', 'user.email', 'password', 'http.url'])
print('  SDK 把属性原样放进 span,不会替你脱敏;在 Collector 里可以统一删除、哈希或者按正则替换,这样所有服务不用各自改代码')
print('ERRORS', dict(ERRORS))
