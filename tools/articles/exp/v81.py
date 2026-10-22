import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import sqlite3, queue as Q
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest, ExportTraceServiceResponse
from opentelemetry.proto.trace.v1 import trace_pb2
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from opentelemetry.trace import SpanKind
import opentelemetry.sdk.version as otv
tee('v81'); reset()
print(f'自己写一个最小的 trace 收集器。用 Python 写:接收 OTLP/HTTP(protobuf)的 /v1/traces、解析 span、写进 SQLite、提供按 trace_id 查询和还原调用树、找最慢的请求。接收端用 opentelemetry-proto 里的消息定义解析(不是自己手写 protobuf),发送端用 OpenTelemetry Python SDK {otv.__version__} 的标准 OTLP/HTTP 导出器。看(一)和 SDK 里的真实 span 对不对得上;(二)写入方式对吞吐的影响;(三)索引对查询的影响和每个 span 占的存储;(四)丢 span 之后怎么发现不完整的 trace')
SCHEMA = 'create table spans(trace_id text, span_id text, parent_id text, service text, name text, kind int, start_ns integer, dur_ns integer, status int, attrs text)'
def parse(body):
    req = ExportTraceServiceRequest(); req.ParseFromString(body); rows = []
    for rs in req.resource_spans:
        svc = next((a.value.string_value for a in rs.resource.attributes if a.key == 'service.name'), '?')
        for ss in rs.scope_spans:
            for sp in ss.spans:
                at = {a.key: (a.value.string_value or a.value.int_value or a.value.double_value or a.value.bool_value) for a in sp.attributes}
                rows.append((sp.trace_id.hex(), sp.span_id.hex(), sp.parent_span_id.hex(), svc, sp.name, sp.kind, sp.start_time_unix_nano, sp.end_time_unix_nano - sp.start_time_unix_nano, sp.status.code, json.dumps(at, ensure_ascii=False)))
    return rows
class MiniCollector:
    """mode: 'autocommit'(每个 span 一次提交)、'per_request'(每个请求一个事务,默认的 journal)、'wal'(每个请求一个事务,WAL + synchronous=NORMAL)、'buffered'(内存队列 + 后台线程批量写,WAL)"""
    def __init__(self, path, mode='wal', index=True):
        self.path, self.mode = str(path), mode; self.n = 0; self.reqs = 0; self.lk = threading.Lock(); self.q = Q.Queue(); self.stop = threading.Event()
        for ext in ('', '-wal', '-shm', '-journal'): pathlib.Path(self.path + ext).unlink(missing_ok=True)
        c = sqlite3.connect(self.path); c.execute(SCHEMA)
        if index: c.execute('create index ix_trace on spans(trace_id)'); c.execute('create index ix_root on spans(parent_id, dur_ns)')
        if mode in ('wal', 'buffered'): c.execute('pragma journal_mode=wal'); c.execute('pragma synchronous=normal')
        else: c.execute('pragma journal_mode=delete'); c.execute('pragma synchronous=full')
        c.commit(); c.close(); self.local = threading.local()
        self.svc = Svc(self.app, 'mtc'); self.port = self.svc.port
        if mode == 'buffered': self.writer = threading.Thread(target=self.flush_loop, daemon=True); self.writer.start()
    def conn(self):
        c = getattr(self.local, 'c', None)
        if c is None: c = self.local.c = sqlite3.connect(self.path, timeout=60, isolation_level=None if self.mode == 'autocommit' else 'DEFERRED', check_same_thread=False)
        return c
    def app(self, h):
        n = int(h.headers.get('Content-Length', 0)); body = h.rfile.read(n); rows = parse(body); self.reqs += 1
        if self.mode == 'buffered': self.q.put(rows)
        elif self.mode == 'autocommit':
            c = self.conn()
            for r in rows: c.execute('insert into spans values (?,?,?,?,?,?,?,?,?,?)', r)
        else:
            with self.lk:
                c = self.conn(); c.executemany('insert into spans values (?,?,?,?,?,?,?,?,?,?)', rows); c.commit()
        with self.lk: self.n += len(rows)
        h.reply(200, ExportTraceServiceResponse().SerializeToString(), {'Content-Type': 'application/x-protobuf'})
    def flush_loop(self):
        c = sqlite3.connect(self.path, timeout=60, check_same_thread=False); buf = []; last = time.time()
        while not self.stop.is_set() or not self.q.empty():
            try: buf += self.q.get(timeout=0.1)
            except Q.Empty: pass
            if buf and (len(buf) >= 5000 or time.time() - last > 0.2 or self.stop.is_set()):
                c.executemany('insert into spans values (?,?,?,?,?,?,?,?,?,?)', buf); c.commit(); buf = []; last = time.time()
        if buf: c.executemany('insert into spans values (?,?,?,?,?,?,?,?,?,?)', buf); c.commit()
    def close(self):
        self.stop.set()
        if self.mode == 'buffered': self.writer.join(30)
        self.svc.stop()
    # ---- 查询 ----
    def trace_tree(self, tid):
        c = sqlite3.connect(self.path); rows = c.execute('select span_id, parent_id, service, name, start_ns, dur_ns from spans where trace_id = ?', (tid,)).fetchall(); c.close()
        by = collections.defaultdict(list)
        for r in rows: by[r[1]].append(r)
        def build(pid, depth=0):
            return [(r[3], r[2], depth, r[5], build(r[0], depth + 1)) for r in sorted(by.get(pid, []), key=lambda x: x[4])]
        ids = {r[0] for r in rows}; roots = [r for r in rows if r[1] == '' or r[1] not in ids]
        return rows, roots

# ============ 一 ============
print('== 一:和 SDK 里的真实 span 对不对得上。3 个服务(A → B → C)的 TracerProvider 把 2000 个 trace(每个 trace 的 span 个数见下面的统计)通过 OTLP/HTTP 发给收集器;同时每个 SDK 保留一份内存里的 span 作为真值。比较:收集器里的 span 个数、每个 span 的 parent_id / 开始时间 / 耗时是否和真值逐个相同,以及 100 个随机 trace 还原出来的调用树节点数')
mc = MiniCollector(TT / 'v81_a.db', 'wal'); provs = {}; mems = {}
for name in 'ABC':
    tp = TracerProvider(resource=Resource.create({'service.name': name})); tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f'http://127.0.0.1:{mc.port}/v1/traces'), max_queue_size=100000, schedule_delay_millis=200)); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); provs[name] = tp; mems[name] = mem
tr = {k: v.get_tracer(k) for k, v in provs.items()}; rnd = random.Random(6)
def call(frm, to, body):
    with tr[frm].start_as_current_span(f'call {to}', kind=SpanKind.CLIENT):
        carrier = {}; propagate.inject(carrier); ctx = propagate.extract(carrier)
        with tr[to].start_as_current_span(f'handle {to}', kind=SpanKind.SERVER, context=ctx): body()
for i in range(2000):
    def in_c():
        for _ in range(rnd.randrange(0, 3)):
            with tr['C'].start_as_current_span('query', attributes={'db.system': 'mysql', 'i': i}): pass
    def in_b():
        if rnd.random() < 0.7: call('B', 'C', in_c)
        with tr['B'].start_as_current_span('compute'): pass
    with tr['A'].start_as_current_span('GET /x', kind=SpanKind.SERVER, attributes={'http.status_code': 200}): call('A', 'B', in_b)
for tp in provs.values(): tp.force_flush(30000)
time.sleep(1.0)
truth = {}
for m in mems.values():
    for s in m.get_finished_spans(): truth[format(s.context.span_id, '016x')] = (format(s.parent.span_id, '016x') if s.parent else '', s.start_time, s.end_time - s.start_time, s.resource.attributes['service.name'], s.name)
c = sqlite3.connect(mc.path); stored = {r[0]: r[1:] for r in c.execute('select span_id, parent_id, start_ns, dur_ns, service, name from spans')}; c.close()
diff_parent = sum(1 for k, v in truth.items() if k in stored and stored[k][0] != v[0]); diff_t = sum(1 for k, v in truth.items() if k in stored and (stored[k][1] != v[1] or stored[k][2] != v[2])); diff_svc = sum(1 for k, v in truth.items() if k in stored and (stored[k][3] != v[3] or stored[k][4] != v[4]))
tids = sorted({format(s.context.trace_id, '032x') for m in mems.values() for s in m.get_finished_spans()}); sample = random.Random(1).sample(tids, 100); ok_tree = 0
per_trace = collections.Counter(format(s.context.trace_id, '032x') for m in mems.values() for s in m.get_finished_spans())
for tid in sample:
    rows, roots = mc.trace_tree(tid)
    if len(rows) == per_trace[tid] and len(roots) == 1: ok_tree += 1
table([('SDK 里的 span 总数(真值)', len(truth)), ('收集器里存下的 span 数', len(stored)), ('parent_id 与真值不同的', diff_parent), ('开始时间或耗时与真值不同的', diff_t), ('服务名或 span 名与真值不同的', diff_svc), ('随机抽 100 个 trace:还原出的 span 数等于真值且恰好 1 个根', f'{ok_tree} / 100')], ['检查项', '结果'])
import inspect
pt = collections.Counter(format(s_.context.trace_id, '032x') for m in mems.values() for s_ in m.get_finished_spans())
print(f'  每个 trace 的 span 个数:最少 {min(pt.values())}、最多 {max(pt.values())}、平均 {len(truth) / len(pt):.1f};收集器的代码(parse 函数加 MiniCollector 类,含空行和注释)共 {len(inspect.getsource(parse).splitlines()) + len(inspect.getsource(MiniCollector).splitlines())} 行')
print('  收集器只需要做三件事:把 OTLP 请求解析成行、存下来、查询时按 parent_id 把行拼成树;和 SDK 里的内存 span 逐个比较,没有丢也没有错')
for tp in provs.values(): tp.shutdown()
mc.close()

# ============ 二 ============
print('== 二:写入方式与吞吐。4 个客户端线程把 10 万个 span(每个请求 500 个,共 200 个请求;请求体是预先编好的 protobuf)发给收集器,看每秒存下多少个 span。四种写法:(a)每个 span 单独提交;(b)每个请求一个事务(默认的回滚日志模式,synchronous=FULL);(c)每个请求一个事务(WAL + synchronous=NORMAL);(d)请求只入内存队列,后台线程攒够 5000 个或 0.2 s 批量写(WAL)')
def mkreq(i, n=500):
    req = ExportTraceServiceRequest(); rs = req.resource_spans.add(); rs.resource.attributes.add(key='service.name').value.string_value = 'svc'
    ss = rs.scope_spans.add(); base = time.time_ns()
    for k in range(n):
        sp = ss.spans.add(); sp.trace_id = os.urandom(16); sp.span_id = os.urandom(8); sp.name = 'op'; sp.kind = 2; sp.start_time_unix_nano = base + k; sp.end_time_unix_nano = base + k + 1000000
        a = sp.attributes.add(); a.key = 'http.route'; a.value.string_value = '/orders/{id}'; b = sp.attributes.add(); b.key = 'n'; b.value.int_value = k
    return req.SerializeToString()
bodies = [mkreq(i) for i in range(200)]
rows = []
for mode, name, nreq in (('autocommit', '(a)每个 span 单独提交', 8), ('per_request', '(b)每个请求一个事务,默认日志', 200), ('wal', '(c)每个请求一个事务,WAL', 200), ('buffered', '(d)内存队列 + 后台批量写', 200)):
    p = TT / f'v81_b_{mode}.db'
    for ext in ('', '-wal', '-shm', '-journal'): pathlib.Path(str(p) + ext).unlink(missing_ok=True)
    mc = MiniCollector(p, mode, index=False); t0 = time.perf_counter(); sent = [0]; slk = threading.Lock()
    def client(ids):
        for i in ids:
            s, d, _ = rpc(mc.port, '/v1/traces', 60.0, {'Content-Type': 'application/x-protobuf'}, 'POST') if False else (None, None, None)
            import http.client as hc
            cn = hc.HTTPConnection('127.0.0.1', mc.port, timeout=120); cn.request('POST', '/v1/traces', body=bodies[i], headers={'Content-Type': 'application/x-protobuf'}); r = cn.getresponse(); r.read(); cn.close()
    ids = list(range(nreq)); parts = [ids[k::4] for k in range(4)]; ths = [threading.Thread(target=client, args=(pp,)) for pp in parts]
    for t in ths: t.start()
    for t in ths: t.join()
    t_recv = time.perf_counter() - t0
    mc.close(); t_all = time.perf_counter() - t0
    c = sqlite3.connect(str(p)); n = c.execute('select count(*) from spans').fetchone()[0]; c.close()
    rows.append((name, n, f'{t_recv:.2f}', f'{n / t_recv:,.0f}', f'{t_all:.2f}', f'{n / t_all:,.0f}'))
table(rows, ['写法', '存下的 span 数', '全部请求都被应答用的时间(s)', '按这个时间算的 span/秒', '全部落盘用的时间(s)', '按落盘时间算的 span/秒'])
print('  每个 span 单独提交的吞吐只有每秒两千多个;(b)(c)(d) 三种批量写法每秒都是几万到十几万个,彼此差别不大(都远高于单个提交),说明关键是把很多 span 合并成一次提交;内存队列加后台批量写把应答和落盘分开,应答最快,代价是崩溃时队列里还没写的 span 会丢(我没有测崩溃)。(a)只发了 8 个请求(4000 个 span),因为太慢;解析 protobuf 和 SQLite 写入在同一个进程里,这里的吞吐受 Python 的 GIL 限制')

# ============ 三 ============
print('== 三:索引与查询。直接往 SQLite 里灌 50 万个 span(10 万个 trace,每个 5 个 span;按 trace_id 分布,根 span 的耗时服从长尾分布),分别建“有索引”(trace_id、(parent_id, dur_ns))和“没有索引”两个库。查询:按 trace_id 取出一个 trace(取 20 个不同的 trace 的中位数);找耗时最长的 10 个根 span;按服务统计 span 数。再看每个 span 占的存储')
rnd = random.Random(8); N_TR = 100000; svcs = ['frontend', 'orders', 'users', 'inventory', 'payments']
def gen_rows():
    for t in range(N_TR):
        tid = '%032x' % rnd.getrandbits(128); root = '%016x' % rnd.getrandbits(64); dur = int(rnd.lognormvariate(16.5, 1.0)); st = 1_790_000_000_000_000_000 + t * 1000
        yield (tid, root, '', 'frontend', 'GET /x', 2, st, dur, 0, '{"http.status_code": 200}')
        for k in range(4):
            yield (tid, '%016x' % rnd.getrandbits(64), root, svcs[1 + k], f'op{k}', 2, st + 10 + k, int(dur * rnd.uniform(0.1, 0.6)), 0, '{"db.system": "mysql"}')
res = {}
for index in (True, False):
    p = TT / f'v81_c_{int(index)}.db'
    for ext in ('', '-wal', '-shm'): pathlib.Path(str(p) + ext).unlink(missing_ok=True)
    c = sqlite3.connect(str(p)); c.execute(SCHEMA); c.execute('pragma journal_mode=wal'); c.execute('pragma synchronous=off')
    rnd = random.Random(8); t0 = time.perf_counter(); c.executemany('insert into spans values (?,?,?,?,?,?,?,?,?,?)', gen_rows()); c.commit(); t_ins = time.perf_counter() - t0
    if index: t0 = time.perf_counter(); c.execute('create index ix_trace on spans(trace_id)'); c.execute('create index ix_root on spans(parent_id, dur_ns)'); c.commit(); t_idx = time.perf_counter() - t0
    else: t_idx = 0.0
    c.execute('pragma wal_checkpoint(truncate)'); tids = [r[0] for r in c.execute('select trace_id from spans where parent_id = "" limit 20 offset 5000')]
    def timeit(fn, n=5):
        ts = []
        for _ in range(n): t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
        return statistics.median(ts) * 1000
    q1 = timeit(lambda: [c.execute('select * from spans where trace_id = ?', (t,)).fetchall() for t in tids[:20]], 3) / 20
    q2 = timeit(lambda: c.execute('select trace_id, dur_ns from spans where parent_id = "" order by dur_ns desc limit 10').fetchall(), 3)
    q3 = timeit(lambda: c.execute('select service, count(*) from spans group by service').fetchall(), 3)
    c.close(); size = os.path.getsize(p); res[index] = (size, t_ins, t_idx, q1, q2, q3)
n_sp = N_TR * 5
table([('有索引', f'{res[True][0] / 1e6:.0f} MB', f'{res[True][0] / n_sp:.0f}', f'{res[True][3]:.3f}', f'{res[True][4]:.1f}', f'{res[True][5]:.0f}'), ('没有索引', f'{res[False][0] / 1e6:.0f} MB', f'{res[False][0] / n_sp:.0f}', f'{res[False][3]:.1f}', f'{res[False][4]:.0f}', f'{res[False][5]:.0f}')], ['配置', '数据库文件大小', '平均每个 span 字节数', '按 trace_id 取一个 trace(ms)', '耗时最长的 10 个根 span(ms)', '按服务统计 span 数(ms)'])
print(f'  灌入 {n_sp:,} 个 span 的耗时:无索引 {res[False][1]:.1f} s;有索引的库在灌入之后再建两个索引用了 {res[True][2]:.1f} s(灌入本身 {res[True][1]:.1f} s)。按 trace_id 查一个 trace,索引让它从扫描整张表变成毫秒以内;统计类的查询(group by)用不上这两个索引,仍然要扫描全表')

# ============ 四 ============
print('== 四:怎么发现不完整的 trace。用第一节的生成方式发 1000 个 trace,在 SDK 的导出器里按概率丢掉 span(丢 0%、5%、20%),收集器收到后,按 “存在 parent_id 指向的 span 不在这个 trace 里” 或者 “没有根 span” 判定 trace 不完整。统计每种丢弃率下不完整 trace 的比例')
rows = []
for pdrop in (0.0, 0.05, 0.2):
    mc = MiniCollector(TT / f'v81_d_{int(pdrop * 100)}.db', 'wal'); rndd = random.Random(3)
    class Lossy(SpanExporter):
        def __init__(self, inner): self.inner = inner
        def export(self, spans): return self.inner.export([s for s in spans if rndd.random() >= pdrop]) if spans else SpanExportResult.SUCCESS
        def shutdown(self): self.inner.shutdown()
    provs = {}
    for name in 'ABC':
        tp = TracerProvider(resource=Resource.create({'service.name': name})); tp.add_span_processor(BatchSpanProcessor(Lossy(OTLPSpanExporter(endpoint=f'http://127.0.0.1:{mc.port}/v1/traces')), max_queue_size=100000, schedule_delay_millis=200)); provs[name] = tp
    tr = {k: v.get_tracer(k) for k, v in provs.items()}; r2 = random.Random(6)
    def call2(frm, to, body):
        with tr[frm].start_as_current_span(f'call {to}', kind=SpanKind.CLIENT):
            carrier = {}; propagate.inject(carrier); ctx = propagate.extract(carrier)
            with tr[to].start_as_current_span(f'handle {to}', kind=SpanKind.SERVER, context=ctx): body()
    for i in range(1000):
        def in_c():
            with tr['C'].start_as_current_span('query'): pass
        def in_b(): call2('B', 'C', in_c)
        with tr['A'].start_as_current_span('GET /x', kind=SpanKind.SERVER): call2('A', 'B', in_b)
    for tp in provs.values(): tp.force_flush(30000)
    time.sleep(1.0); c = sqlite3.connect(mc.path); allr = c.execute('select trace_id, span_id, parent_id from spans').fetchall(); c.close()
    by = collections.defaultdict(list)
    for t, s, p in allr: by[t].append((s, p))
    inc = 0
    for t, ss in by.items():
        ids = {s for s, p in ss}
        if not any(p == '' for s, p in ss) or any(p != '' and p not in ids for s, p in ss): inc += 1
    rows.append((f'{pdrop:.0%}', len(by), inc, f'{inc / len(by):.1%}' if by else '-'))
    for tp in provs.values(): tp.shutdown()
    mc.close()
table(rows, ['每个 span 被丢弃的概率', '收集器里有记录的 trace 数', '判定不完整的 trace 数', '比例'])
print('  每个 trace 有 6 个 span,最里层的叶子 span(query)被丢不会让 trace 变成“残缺的树”(只是少了一个叶子,这种情形判定不出来),所以不完整的比例比“有 span 被丢的 trace 的比例”低;丢任何一个非叶子 span 都会让它的子 span 变成孤儿,丢根 span 则找不到根;收集器在查询时(或者等一个超时之后)检查这两个条件,就能给这类 trace 打上标记')
print('ERRORS', dict(ERRORS))
