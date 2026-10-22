import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import logging, socketserver, re
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExp
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExp
from opentelemetry.exporter.otlp.proto.grpc.exporter import Compression as GC
from opentelemetry.exporter.otlp.proto.http import Compression as HC
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
import opentelemetry.sdk.version as otv
tee('v67'); reset()
logging.getLogger('opentelemetry').setLevel(logging.ERROR)
print(f'OTLP 与 Collector。OpenTelemetry Python SDK {otv.__version__} 作为发送端,OpenTelemetry Collector contrib 0.163.1 作为接收端:gRPC 与 HTTP 两种传输(以及 gzip 压缩)的字节数和耗时、Collector 流水线里 batch / filter / resource 处理器的效果、Collector 在下游故障时作为缓冲的表现。应用到 Collector 之间我放了一个按字节计数的 TCP 转发')
class CountProxy:
    """TCP 转发:统计客户端→服务端、服务端→客户端的字节数和连接数"""
    def __init__(self, target_port):
        self.up = self.down = self.conns = 0; self.lk = threading.Lock(); tp_ = target_port; me = self
        class H(socketserver.BaseRequestHandler):
            def handle(self):
                me.conns += 1; up = socket.create_connection(('127.0.0.1', tp_)); c = self.request
                def pump(a, b, key):
                    try:
                        while True:
                            d = a.recv(65536)
                            if not d: break
                            with me.lk: setattr(me, key, getattr(me, key) + len(d))
                            b.sendall(d)
                    except Exception: pass
                    finally:
                        for x in (a, b):
                            try: x.shutdown(socket.SHUT_RDWR)
                            except Exception: pass
                t = threading.Thread(target=pump, args=(up, c, 'down'), daemon=True); t.start(); pump(c, up, 'up'); t.join(2)
        class S(socketserver.ThreadingTCPServer): allow_reuse_address = True; daemon_threads = True
        self.port = free_port(); self.srv = S(('127.0.0.1', self.port), H); threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def stop(self): self.srv.shutdown(); self.srv.server_close()
def send_spans(exporter, n, attrs=5, bsp_kw=None):
    tp = TracerProvider(); tp.add_span_processor(BatchSpanProcessor(exporter, max_queue_size=200000, schedule_delay_millis=100, max_export_batch_size=512, **(bsp_kw or {}))); tr = tp.get_tracer('o')
    t0 = time.perf_counter()
    for i in range(n):
        with tr.start_as_current_span('GET /orders/{id}', attributes={'seq': i, 'http.method': 'GET', 'http.route': '/orders/{id}', 'http.status_code': 200, 'user.tier': 'gold' if i % 3 else 'basic', 'host.zone': 'z1'} if attrs else {'seq': i}): pass
    tp.force_flush(60000); dt = time.perf_counter() - t0; tp.shutdown(); return dt

# ============ 一 ============
print('== 一:传输方式。20000 个 span(每个 6 个属性),分别用 gRPC、gRPC+gzip、HTTP(protobuf)、HTTP+gzip 发给 Collector(Collector 开着 gRPC 和 HTTP 两个 OTLP receiver,exporter 是 nop,不写磁盘)。经过按字节计数的转发,统计应用 → Collector 方向的字节数、连接数,以及发送到 force_flush 返回的总耗时(含 SDK 创建 span 的时间)')
gp, hp = free_port(), free_port()
cfg1 = f'''receivers:
  otlp:
    protocols:
      grpc: {{endpoint: 127.0.0.1:{gp}}}
      http: {{endpoint: 127.0.0.1:{hp}}}
exporters:
  nop: {{}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    traces: {{receivers: [otlp], exporters: [nop]}}
'''
oc = Otelcol('v67a', cfg1, gp).start(); time.sleep(0.5); rows = []
raw = None
for name, mode in (('gRPC', 'grpc'), ('gRPC + gzip', 'grpc_gz'), ('HTTP(protobuf)', 'http'), ('HTTP + gzip', 'http_gz')):
    px = CountProxy(gp if mode.startswith('grpc') else hp)
    if mode == 'grpc': ex = GrpcExp(endpoint=f'127.0.0.1:{px.port}', insecure=True)
    elif mode == 'grpc_gz': ex = GrpcExp(endpoint=f'127.0.0.1:{px.port}', insecure=True, compression=GC.Gzip)
    elif mode == 'http': ex = HttpExp(endpoint=f'http://127.0.0.1:{px.port}/v1/traces')
    else: ex = HttpExp(endpoint=f'http://127.0.0.1:{px.port}/v1/traces', compression=HC.Gzip)
    dt = send_spans(ex, 20000); time.sleep(0.3); rows.append((name, f'{px.up:,}', f'{px.up / 20000:.1f}', f'{px.down:,}', px.conns, f'{dt:.2f}')); px.stop()
table(rows, ['传输方式', '应用 → Collector 字节数', '平均每个 span 的字节数', 'Collector → 应用 字节数', 'TCP 连接数', '总耗时(s)'])
print('  gRPC 和 HTTP 的负载都是同一个 protobuf 消息,所以不压缩时字节数接近;gzip 把属性里重复的键名和值压缩掉,体积大幅下降;gRPC 复用一条 HTTP/2 连接,HTTP 导出器(requests)的连接数见表')
oc.stop()

# ============ 二 ============
print('== 二:流水线与处理器。同一个 OTLP receiver 同时接入三条流水线,各自写一个 file exporter:(A)没有处理器;(B)batch 处理器(send_batch_size 2000,timeout 1 s);(C)resource 处理器给所有 span 的资源加 deployment.environment=prod,filter 处理器丢掉 health=true 的 span。20000 个 span,其中 20% 带 health=true,SDK 每批 512 个。统计每条流水线输出的导出次数(file exporter 的行数)、span 数,以及 C 的输出里资源属性')
gp = free_port(); outs = {k: TT / f'v67_{k}.jsonl' for k in 'abc'}
for f in outs.values(): f.unlink(missing_ok=True)
cfg2 = f'''receivers:
  otlp:
    protocols:
      grpc: {{endpoint: 127.0.0.1:{gp}}}
processors:
  batch/b: {{send_batch_size: 2000, timeout: 1s}}
  resource/env:
    attributes:
      - {{key: deployment.environment, value: prod, action: upsert}}
  filter/hc:
    error_mode: ignore
    traces:
      span:
        - 'attributes["health"] == true'
exporters:
  file/a: {{path: {outs["a"]}}}
  file/b: {{path: {outs["b"]}}}
  file/c: {{path: {outs["c"]}}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    traces/a: {{receivers: [otlp], exporters: [file/a]}}
    traces/b: {{receivers: [otlp], processors: [batch/b], exporters: [file/b]}}
    traces/c: {{receivers: [otlp], processors: [resource/env, filter/hc], exporters: [file/c]}}
'''
oc = Otelcol('v67b', cfg2, gp).start(); time.sleep(0.5)
tp = TracerProvider(); tp.add_span_processor(BatchSpanProcessor(GrpcExp(endpoint=f'127.0.0.1:{gp}', insecure=True), max_queue_size=200000, schedule_delay_millis=100, max_export_batch_size=512)); tr = tp.get_tracer('o')
for i in range(20000):
    with tr.start_as_current_span('op', attributes={'seq': i, 'health': i % 5 == 0}): pass
tp.force_flush(60000); t_flush = time.time(); first = {}
def nspans(path):
    n = 0
    try:
        for line in open(path):
            try: d = json.loads(line)
            except Exception: continue
            for rs in d['resourceSpans']:
                for ss in rs['scopeSpans']: n += len(ss['spans'])
    except FileNotFoundError: pass
    return n
target = {'a': 20000, 'b': 20000, 'c': 16000}; deadline = time.time() + 15
while time.time() < deadline and len(first) < 3:
    for k, f in outs.items():
        if k not in first and nspans(f) >= target[k]: first[k] = time.time() - t_flush
    time.sleep(0.05)
time.sleep(1.0); tp.shutdown(); oc.stop()
def stats(path):
    lines = 0; spans = 0; res = {}
    for line in open(path):
        lines += 1
        for rs in json.loads(line)['resourceSpans']:
            for a in rs['resource'].get('attributes', []): res[a['key']] = list(a['value'].values())[0]
            for ss in rs['scopeSpans']: spans += len(ss['spans'])
    return lines, spans, res
rows = []
for k, name in (('a', '(A)没有处理器'), ('b', '(B)batch(2000 / 1 s)'), ('c', '(C)resource + filter')):
    l, s_, r = stats(outs[k]); rows.append((name, l, s_, f'{s_ / max(1, l):.0f}', f'{first.get(k, float("nan")):.2f}', ','.join(f'{a}={b}' for a, b in r.items() if a.startswith('deployment'))))
table(rows, ['流水线', 'file exporter 写出的次数(行数)', 'span 数', '平均每次写出的 span 数', '写完全部 span 的时间(相对 SDK force_flush 返回,s)', '资源属性里的 deployment.*'])
print('  没有 batch 时 Collector 收到一批就写出一批(每批 512 个);batch 处理器把它们攒到 2000 个或 1 s 再写出,写出次数少、每次更大,代价是最多多等 timeout;filter 处理器丢弃了带 health=true 的 span')

# ============ 三 ============
print('== 三:Collector 作为缓冲。应用 → Collector(gRPC)→ 下游(OTLP/HTTP,我的接收端)。Collector 的 otlphttp exporter 配 sending_queue(队列 50 批)和 retry_on_failure(初始间隔 0.5 s,最大 2 s,最长重试 6 s),超时 2 s。应用每秒发 50 批、每批 100 个 span(共 20 s,100000 个 span;应用的 SDK 队列分别用 200000 和默认的 2048)。下游在第 3 s 停掉,停 3 s 或 10 s 再在同一个端口恢复。统计下游最终收到多少,以及 Collector 日志里重试和丢弃的条数')
class Recv:
    def __init__(self, port=None):
        self.seqs = set(); self.lk = threading.Lock()
        def app(h):
            n = int(h.headers.get('Content-Length', 0)); body = h.rfile.read(n)
            if h.headers.get('Content-Encoding') == 'gzip':
                import gzip; body = gzip.decompress(body)
            req = ExportTraceServiceRequest(); req.ParseFromString(body)
            with self.lk:
                for rs in req.resource_spans:
                    for ss in rs.scope_spans:
                        for sp_ in ss.spans:
                            for a in sp_.attributes:
                                if a.key == 'seq': self.seqs.add(a.value.int_value)
            h.reply(200, b'')
        self.svc = Svc(app, 'down', port=port); self.port = self.svc.port
    def stop(self): self.svc.stop()
rows = []
for down_s, sdkq in ((3, 200000), (10, 200000), (10, 2048)):
    gp = free_port(); rc = Recv(); port = rc.port
    cfg3 = f'''receivers:
  otlp:
    protocols:
      grpc: {{endpoint: 127.0.0.1:{gp}}}
exporters:
  otlphttp/d:
    endpoint: http://127.0.0.1:{port}
    compression: none
    timeout: 2s
    retry_on_failure: {{enabled: true, initial_interval: 0.5s, max_interval: 2s, max_elapsed_time: 6s}}
    sending_queue: {{enabled: true, num_consumers: 1, queue_size: 50}}
service:
  telemetry: {{metrics: {{level: none}}, logs: {{level: warn}}}}
  pipelines:
    traces: {{receivers: [otlp], exporters: [otlphttp/d]}}
'''
    oc = Otelcol(f'v67c{down_s}_{sdkq}', cfg3, gp).start(); time.sleep(0.5)
    ex = GrpcExp(endpoint=f'127.0.0.1:{gp}', insecure=True); tp = TracerProvider(); bsp = BatchSpanProcessor(ex, max_queue_size=sdkq, schedule_delay_millis=50, max_export_batch_size=100); tp.add_span_processor(bsp); tr = tp.get_tracer('o')
    holder = {'rc': rc}; sdk_drops = [0]
    def chaos():
        time.sleep(3.0); holder['rc'].stop(); time.sleep(down_s); holder['rc'] = Recv(port=port)
    th = threading.Thread(target=chaos); th.start(); t0 = time.perf_counter()
    for i in range(100000):
        d = t0 + i / 5000 - time.perf_counter()
        if d > 0: time.sleep(d)
        with tr.start_as_current_span('op', attributes={'seq': i}): pass
    tp.force_flush(60000); th.join(); time.sleep(12.0)
    got = len(holder['rc'].seqs | rc.seqs); log = oc.log()
    rej = len(re.findall(r'Rejecting data', log)); drops = len(re.findall(r'Dropping data', log))
    rows.append((f'{down_s} s', sdkq, got, 100000 - got, rej, drops)); tp.shutdown(); oc.stop(); holder['rc'].stop()
table(rows, ['下游停掉的时间', '应用 SDK 的队列大小', '下游最终收到的 span', '没收到', 'Collector 日志 “Rejecting data” 条数', 'Collector 日志 “Dropping data” 条数'])
print('  Collector 的 sending_queue 满了会拒收(“Rejecting data”),把压力还给应用的 SDK,由 SDK 的队列和重试继续缓冲;重试超过 max_elapsed_time 的那一批被丢弃(“Dropping data”)。所以丢多少取决于 Collector 队列、重试时间和 SDK 队列三层加起来能缓冲多久')
print('ERRORS', dict(ERRORS))
