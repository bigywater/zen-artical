import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import re
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased, ALWAYS_ON
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import SpanKind
import opentelemetry.sdk.version as otv
tee('v80'); reset()
print(f'服务依赖图是怎么从 span 里算出来的。OpenTelemetry Python SDK {otv.__version__} 生成 2000 个 trace(7 条服务间的调用边,有概率地出现),OTLP/gRPC 发给 Collector contrib 0.163.1 的 servicegraph 连接器,把 span 配对成 “客户端服务 → 服务端服务” 的请求计数,再用 Prometheus 导出器暴露;并和我从 span 的父子关系自己算出来的边、以及程序里记下的真实调用次数比较')
SERVICES = ['frontend', 'orders', 'users', 'inventory', 'payments', 'notifier']
def build(gp, sampler=None, drop=None):
    provs = {}; mems = {}
    class Drop(SpanExporter):
        def __init__(self, inner, p): self.inner, self.p, self.rnd = inner, p, random.Random(9)
        def export(self, spans): return self.inner.export([s for s in spans if not (s.kind in (SpanKind.SERVER, SpanKind.CONSUMER) and self.rnd.random() < self.p)])
        def shutdown(self): self.inner.shutdown()
    for name in SERVICES:
        tp = TracerProvider(resource=Resource.create({'service.name': name}), sampler=sampler or ALWAYS_ON); exp = OTLPSpanExporter(endpoint=f'127.0.0.1:{gp}', insecure=True)
        if drop and name in drop: exp = Drop(exp, drop[name])
        tp.add_span_processor(BatchSpanProcessor(exp, max_queue_size=200000, schedule_delay_millis=200)); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); provs[name] = tp; mems[name] = mem
    return provs, mems
def generate(provs, n, seed=7):
    rnd = random.Random(seed); truth = collections.Counter(); tr = {k: v.get_tracer(k) for k, v in provs.items()}
    def call(frm, to, name, kind_client=SpanKind.CLIENT, kind_server=SpanKind.SERVER, body=None, attrs=None):
        with tr[frm].start_as_current_span(f'call {to}', kind=kind_client, attributes=attrs or {}):
            carrier = {}; propagate.inject(carrier); ctx = propagate.extract(carrier)
            with tr[to].start_as_current_span(name, kind=kind_server, context=ctx):
                if body: body()
    def virtual(frm, attrs):
        with tr[frm].start_as_current_span('call external', kind=SpanKind.CLIENT, attributes=attrs): pass
    for i in range(n):
        def in_orders():
            call('orders', 'inventory', 'reserve'); truth[('orders', 'inventory')] += 1
            virtual('orders', {'db.system': 'mysql', 'db.name': 'orders-db'}); truth[('orders', 'orders-db')] += 1
            if rnd.random() < 0.6:
                def in_pay(): virtual('payments', {'peer.service': 'bank'}); truth[('payments', 'bank')] += 1
                call('orders', 'payments', 'charge', body=in_pay); truth[('orders', 'payments')] += 1
            if rnd.random() < 0.3:
                call('orders', 'notifier', 'send', kind_client=SpanKind.PRODUCER, kind_server=SpanKind.CONSUMER, attrs={'messaging.system': 'kafka'}); truth[('orders', 'notifier')] += 1
        with tr['frontend'].start_as_current_span('GET /checkout', kind=SpanKind.SERVER):
            call('frontend', 'orders', 'POST /orders', body=in_orders); truth[('frontend', 'orders')] += 1
            call('frontend', 'users', 'GET /me'); truth[('frontend', 'users')] += 1
    return truth
def mine(mems):
    spans = [s for m in mems.values() for s in m.get_finished_spans()]; svc = {s.context.span_id: s.resource.attributes['service.name'] for s in spans}; kind = {s.context.span_id: s.kind for s in spans}; edges = collections.Counter()
    for s in spans:
        if s.kind in (SpanKind.SERVER, SpanKind.CONSUMER) and s.parent is not None and s.parent.span_id in svc and kind[s.parent.span_id] in (SpanKind.CLIENT, SpanKind.PRODUCER):
            a, b = svc[s.parent.span_id], s.resource.attributes['service.name']
            if a != b: edges[(a, b)] += 1
        if s.kind == SpanKind.CLIENT and s.attributes and any(k in s.attributes for k in ('peer.service', 'db.name')):
            edges[(s.resource.attributes['service.name'], s.attributes.get('peer.service') or s.attributes.get('db.name'))] += 1
    return edges
def cfg(gp, pm):
    return f'''receivers:
  otlp:
    protocols:
      grpc: {{endpoint: 127.0.0.1:{gp}}}
connectors:
  servicegraph:
    latency_histogram_buckets: [10ms, 100ms, 1s]
    store: {{ttl: 2s, max_items: 10000}}
    metrics_flush_interval: 2s
exporters:
  prometheus: {{endpoint: 127.0.0.1:{pm}}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    traces: {{receivers: [otlp], exporters: [servicegraph]}}
    metrics: {{receivers: [servicegraph], exporters: [prometheus]}}
'''
def run(tag, n=2000, sampler=None, drop=None):
    gp, pm = free_port(), free_port(); oc = Otelcol('v80' + tag, cfg(gp, pm), gp).start(); provs, mems = build(gp, sampler, drop)
    truth = generate(provs, n)
    for tp in provs.values(): tp.force_flush(30000)
    time.sleep(7.0)
    s, d, _ = rpc(pm, '/metrics', 10.0); txt = d.decode(); got = collections.Counter(); ctype = {}; other = {}
    for line in txt.splitlines():
        m = re.match(r'traces_service_graph_request_total\{(.*)\} ([\d.e+]+)', line)
        if m:
            lab = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1))); got[(lab['client'], lab['server'])] += int(float(m.group(2))); ctype[(lab['client'], lab['server'])] = lab.get('connection_type', '')
        else:
            m2 = re.match(r'(traces_service_graph_(?:unpaired|dropped)\w*)\{?[^}]*\}? ([\d.e+]+)', line)
            if m2: other[m2.group(1)] = other.get(m2.group(1), 0) + float(m2.group(2))
    own = mine(mems); oc.stop()
    for tp in provs.values(): tp.shutdown()
    return truth, got, own, ctype, other, txt

# ============ 一 ============
print('== 一:依赖边的计数。三个来源:程序里记下的真实调用次数;我从 span 父子关系(服务端 / 消费者 span 的父 span 是另一个服务的客户端 / 生产者 span)自己算出来的边;Collector servicegraph 连接器的 traces_service_graph_request_total。所有 span 都送达,100% 采样')
truth, got, own, ctype, other, txt1 = run('a')
edges = sorted(set(truth) | set(got) | set(own))
table([(f'{a} → {b}', truth[(a, b)], own[(a, b)], got[(a, b)], ctype.get((a, b), '-') or 'unset') for a, b in edges], ['边(客户端 → 服务端)', '真实调用次数', '我从父子关系算的', 'servicegraph 的 request_total', 'servicegraph 的 connection_type'])
print(f'  servicegraph 其他计数:{ {k: v for k, v in other.items()} or "无" }')
print(f'  服务图的边由配对的两个 span 得出:客户端(或生产者)span 和它的子 span(服务端 / 消费者 span)属于不同的服务,配成 “client → server” 的一次请求;数据库、外部服务这类没有对端 span 的调用,靠客户端 span 上的 peer 属性(peer.service、db.name、db.system、messaging.system)变成“虚拟节点”(上表里 orders-db 的 connection_type 是 database,bank 是 virtual_node,notifier 是 messaging_system)。表里还多了一条真实调用次数是 0 的 user → frontend,共 {got[("user", "frontend")]} 次:frontend 的根 span 是服务端 span、没有客户端一侧的父 span,连接器把它记成来自虚拟节点 user 的请求')

# ============ 二 ============
print('== 二:丢了一部分服务端 span。模拟 orders 和 payments 两个服务的服务端 span 有 20% 在送到 Collector 之前丢了(客户端 span 还在)。看 servicegraph 对 frontend → orders 和 orders → payments 这两条边的计数,和真实调用次数、和 span 全部送达时的计数')
truth2, got2, own2, ct2, other2, _ = run('b', drop={'orders': 0.2, 'payments': 0.2})
rows = []
for a, b in sorted(set(truth2) | set(got2)):
    rows.append((f'{a} → {b}', truth2[(a, b)], got2[(a, b)], f'{(got2[(a, b)] - truth2[(a, b)]) / truth2[(a, b)]:+.0%}' if truth2[(a, b)] else '-'))
table(rows, ['边', '真实调用次数', 'servicegraph 的 request_total', '相对真实值的差'])
lost = {c: truth2[(c, s_)] - got2[(c, s_)] for c, s_ in (('frontend', 'orders'), ('orders', 'payments'))}
print(f'  servicegraph 其他计数:{ {k: v for k, v in other2.items()} or "无" }。丢了服务端 span 的那些客户端 span 在 store.ttl(2 s)到期后找不到配对,没有被忽略,而是被记成指向虚拟节点 unknown 的边:frontend → orders 比真实值少 {lost["frontend"]} 次,frontend → unknown 有 {got2[("frontend", "unknown")]} 次;orders → payments 少 {lost["orders"]} 次,orders → unknown 有 {got2[("orders", "unknown")]} 次(少的和 unknown 的数量一致,总数守恒)。所以丢 span 的后果是图上出现 unknown 节点,而不是边上的数字消失')

# ============ 三 ============
print('== 三:头部采样之后。SDK 用 ParentBased(TraceIdRatioBased(10%)) 采样,其余同第一节。看 servicegraph 的计数相对真实调用次数(真实次数是 2000 个请求里全部发生过的调用,不管是否被采样)')
truth3, got3, own3, ct3, other3, _ = run('c', sampler=ParentBased(TraceIdRatioBased(0.1)))
table([(f'{a} → {b}', truth3[(a, b)], got3[(a, b)], f'{got3[(a, b)] / truth3[(a, b)]:.1%}' if truth3[(a, b)] else '-') for a, b in sorted(set(truth3) | set(got3))], ['边', '真实调用次数', 'servicegraph 的 request_total', '占真实调用次数的比例'])
print('  服务图的计数来自被采样的 span,采样率 10% 时每条边的计数只有真实调用的十分之一左右;所以请求速率不能直接用采样后的服务图计数,要么按采样率放大,要么用在采样之前统计的指标(例如 SDK 的指标或 Collector 上游的 spanmetrics)')
print('ERRORS', dict(ERRORS))
