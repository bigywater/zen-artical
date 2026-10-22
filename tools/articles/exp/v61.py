import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from opentelemetry import trace, propagate, context as otctx, baggage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind
import opentelemetry.sdk.version as otv
tee('v61'); reset()
print(f'trace、span、context 与 W3C traceparent。OpenTelemetry Python SDK {otv.__version__},三个服务 A → B → C(都是本进程里的 HTTP 服务,每个服务一个独立的 TracerProvider 和内存导出器),上下文只通过 HTTP 头在服务之间传递。看 traceparent 头的格式、每一跳哪些字段变化、中间一跳不传播会怎样、请求 ID 头和 trace 头的区别,以及收到格式不对的 traceparent 时 SDK 怎么处理')
class Service:
    def __init__(self, name, down=None, forward_trace=True, forward_reqid=True, attach=False):
        self.name, self.down, self.ft, self.fr, self.attach = name, down, forward_trace, forward_reqid, attach
        self.tp = TracerProvider(resource=Resource.create({'service.name': name})); self.exp = InMemorySpanExporter(); self.tp.add_span_processor(SimpleSpanProcessor(self.exp)); self.tracer = self.tp.get_tracer(name)
        self.seen = []        # 收到的请求头:(traceparent, tracestate, baggage, x-request-id)
        self.svc = Svc(self.app, name); self.port = self.svc.port
    def app(self, h):
        hd = {k.lower(): v for k, v in h.headers.items()}; self.seen.append((hd.get('traceparent'), hd.get('tracestate'), hd.get('baggage'), hd.get('x-request-id')))
        ctx = propagate.extract(hd); tok = otctx.attach(ctx) if self.attach else None
        try:
            with self.tracer.start_as_current_span(f'{self.name} handle', context=ctx, kind=SpanKind.SERVER) as sp:
                bag = baggage.get_baggage('user', ctx)
                if self.down:
                    with self.tracer.start_as_current_span(f'{self.name} call', kind=SpanKind.CLIENT):
                        out = {}
                        if self.ft: propagate.inject(out)
                        if self.fr and hd.get('x-request-id'): out['X-Request-Id'] = hd['x-request-id']
                        rpc(self.down.port, '/x', 5.0, out, keepalive=False)
        finally:
            if tok: otctx.detach(tok)
        h.reply(200, (bag or '').encode())
    def spans(self): return list(self.exp.get_finished_spans())
    def clear(self): self.exp.clear(); self.seen.clear()
    def stop(self): self.svc.stop()
fid = lambda n, w: format(n, f'0{w}x')
def chain(**kw):
    C = Service('C'); B = Service('B', C, **kw.get('b', {})); A = Service('A', B, **kw.get('a', {})); return A, B, C
def spans_of(*svcs):
    out = []
    for sv in svcs:
        for sp in sv.spans(): out.append((sv.name, sp))
    return out

# ============ 一 ============
print('== 一:一次调用在三个服务里留下的 span,以及每一跳收到的 traceparent。外部客户端带 X-Request-Id 调用 A,A 调 B,B 调 C,三个服务都正确传播')
A, B, C = chain(); rpc(A.port, '/x', 5.0, {'X-Request-Id': 'req-123'}, keepalive=False); time.sleep(0.2)
sp = spans_of(A, B, C); tid = {s.context.trace_id for _, s in sp}
rows = [(n, s.name, s.kind.name, fid(s.context.trace_id, 32)[:8] + '…', fid(s.context.span_id, 16), fid(s.parent.span_id, 16) if s.parent else '(根)') for n, s in sorted(sp, key=lambda x: x[1].start_time)]
table(rows, ['服务', 'span 名', '类型', 'trace_id', 'span_id', 'parent_span_id'])
print(f'  这次调用里不同的 trace_id 个数:{len(tid)}')
rows = []
for sv in (A, B, C):
    tp, ts, bg, rid = sv.seen[0]; rows.append((sv.name, tp or '(无)', rid))
table(rows, ['服务', '收到的 traceparent', '收到的 X-Request-Id'])
tp = C.seen[0][0].split('-'); print(f'  C 收到的 traceparent 的四段:version={tp[0]},trace-id={tp[1]}(32 个十六进制字符),parent-id={tp[2]}(16 个),trace-flags={tp[3]}。A 没有收到 traceparent,B 和 C 收到的 trace-id 相同、parent-id 不同:parent-id 是上一跳发出请求的那个 CLIENT span 的 span_id')
byid = {fid(s.context.span_id, 16): (n, s) for n, s in sp}
print('  C 收到的 parent-id 对应的 span:' + (f'{byid[tp[2]][0]} 的 “{byid[tp[2]][1].name}”' if tp[2] in byid else '找不到'))
A.stop(); B.stop(); C.stop()

# ============ 二 ============
print('== 二:中间一跳不传播会怎样。三种情形各调用一次:(a)B 调 C 时不带 traceparent、带 X-Request-Id;(b)B 调 C 时带 traceparent、不带 X-Request-Id;(c)全部不传播(B 既不带 traceparent 也不带 X-Request-Id)。看 C 的 span 属于哪个 trace、是不是根 span,以及 C 收到的请求头里有没有请求 ID')
rows = []
for name, kw in (('(a)B 不传 traceparent,传请求 ID', dict(b=dict(forward_trace=False, forward_reqid=True))), ('(b)B 传 traceparent,不传请求 ID', dict(b=dict(forward_trace=True, forward_reqid=False))), ('(c)B 两个都不传', dict(b=dict(forward_trace=False, forward_reqid=False)))):
    A, B, C = chain(**kw); rpc(A.port, '/x', 5.0, {'X-Request-Id': 'req-777'}, keepalive=False); time.sleep(0.2)
    sa = [s for s in A.spans() if s.kind == SpanKind.SERVER][0]; sc = [s for s in C.spans()][0]
    rows.append((name, 'A 与 C 同一个 trace' if sa.context.trace_id == sc.context.trace_id else 'A 与 C 是两个不同的 trace', 'C 的 span 是根' if sc.parent is None else 'C 的 span 有父 span', C.seen[0][3] or '(没有)'))
    A.stop(); B.stop(); C.stop()
table(rows, ['情形', 'trace 关系', 'C 的 span', 'C 收到的 X-Request-Id'])
print('  上下文只通过请求头传播:中间一跳没把 traceparent 带出去,下游就从一个新的 trace 开始,链路在这里断开;请求 ID 头同样要每一跳自己转发,SDK 不会替你转')

# ============ 三 ============
print('== 三:baggage 和 tracestate。外部请求带 traceparent、tracestate: vendor1=opaque,vendor2=x 和 baggage: user=alice,向下传播到 C。比较两种写法:(a)服务把提取出来的上下文只作为 start_as_current_span 的 context 参数传进去;(b)服务先把提取出来的上下文 attach 成当前上下文。看 B、C 收到的 tracestate 和 baggage,以及每一跳这三个头的总字符数')
TP = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
for name, att in (('(a)上下文只作为 context 参数传入', False), ('(b)先 attach 提取出来的上下文', True)):
    A, B, C = chain(a=dict(attach=att), b=dict(attach=att)); rpc(A.port, '/x', 5.0, {'traceparent': TP, 'baggage': 'user=alice', 'tracestate': 'vendor1=opaque,vendor2=x'}, keepalive=False); time.sleep(0.2)
    print(f'  {name}:')
    table([(sv.name, sv.seen[0][0] or '(无)', sv.seen[0][1] or '(无)', sv.seen[0][2] or '(无)', len((sv.seen[0][0] or '') + (sv.seen[0][1] or '') + (sv.seen[0][2] or ''))) for sv in (A, B, C)], ['服务', 'traceparent', 'tracestate', 'baggage', '三个头的字符数'])
    A.stop(); B.stop(); C.stop()
print('  tracestate 跟着 span 上下文走,baggage 是独立的上下文内容:只把提取出来的上下文当作 start_as_current_span 的父上下文传进去,新 span 的父子关系是对的,但是当前上下文里没有 baggage,发给下游的请求头里就没有它;要先 attach 才行')

# ============ 四 ============
print('== 四:收到格式不对的 traceparent 时 SDK 怎么处理。单个服务 A 直接收到下面这些 traceparent,看它的 span 是延续了这个 trace,还是另起一个新的 trace(根),以及未采样标志的效果(默认采样器 ParentBased(ALWAYS_ON))')
cases = [('合法,已采样(flags=01)', '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'), ('合法,未采样(flags=00)', '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00'),
         ('十六进制用了大写', '00-4BF92F3577B34DA6A3CE929D0E0E4736-00F067AA0BA902B7-01'), ('trace-id 全 0', '00-00000000000000000000000000000000-00f067aa0ba902b7-01'),
         ('parent-id 全 0', '00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01'), ('version=ff(非法)', 'ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'),
         ('version=01 且多出字段', '01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01-extra'), ('缺 trace-flags', '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7'),
         ('trace-id 太短', '00-4bf92f3577b34da6-00f067aa0ba902b7-01'), ('尾部有多余字符', '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01zz'), ('随便一个字符串', 'hello')]
rows = []; want = int('4bf92f3577b34da6a3ce929d0e0e4736', 16)
for name, val in cases:
    A = Service('A'); rpc(A.port, '/x', 5.0, {'traceparent': val}, keepalive=False); time.sleep(0.1); sps = A.spans()
    if not sps: rows.append((name, val[:46], '没有导出任何 span(未采样,span 没有被记录)'))
    else:
        s = sps[0]; rows.append((name, val[:46] + ('…' if len(val) > 46 else ''), '延续了这个 trace(parent 是请求里的 parent-id)' if s.context.trace_id == want and s.parent is not None else ('另起新 trace(根 span)' if s.parent is None else f'有父 span,trace_id={fid(s.context.trace_id, 32)[:8]}…')))
    A.stop()
table(rows, ['请求带的 traceparent', '值(截取)', 'SDK 的处理'])
print('  格式不对的 traceparent 会被丢掉,服务从一个新的 trace 开始,不会报错;“未采样”标志(flags=00)会让默认采样器也不记录这条 span')
print('ERRORS', dict(ERRORS))
