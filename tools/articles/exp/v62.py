import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import asyncio, contextvars, concurrent.futures, pika, ql
from opentelemetry import trace, propagate, context as otctx
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, Link
import opentelemetry.sdk.version as otv
tee('v62'); reset(); ql.reset()
print(f'上下文传播:跨线程、跨协程、跨消息队列。OpenTelemetry Python SDK {otv.__version__}(上下文存在 contextvars 里),Python 3.14;消息队列用 RabbitMQ(自己起的单节点,pika 1.4.4)。看哪些写法会让子 span 丢掉父 span,以及消息队列里 span 的父子关系和 span link 怎么用')
tp = TracerProvider(); exp = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(exp)); tracer = tp.get_tracer('v62')
def child(tag):
    with tracer.start_as_current_span('child:' + tag): pass
async def achild(tag): child(tag)
def verdict(tag, pc):
    sps = [s for s in exp.get_finished_spans() if s.name == 'child:' + tag]
    if not sps: return '没有 span'
    c = sps[0]
    if c.context.trace_id != pc.trace_id: return '另起新 trace(根 span)' if c.parent is None else '属于别的 trace'
    return '同一个 trace,父 span 是调用方' if c.parent is not None and c.parent.span_id == pc.span_id else '同一个 trace,但父 span 不是调用方'

# ============ 一 ============
print('== 一:跨线程。在一个 span(parent)里,用四种方式让另一个线程去创建子 span:(a)threading.Thread;(b)ThreadPoolExecutor.submit;(c)submit(contextvars.copy_context().run, f);(d)线程里先 attach 调用方保存下来的上下文')
exp.clear(); cases = []
with tracer.start_as_current_span('parent') as p:
    pc = p.get_span_context()
    t = threading.Thread(target=child, args=('thread',)); t.start(); t.join(); cases.append(('(a)threading.Thread', 'thread'))
    with concurrent.futures.ThreadPoolExecutor(2) as ex: ex.submit(child, 'pool').result()
    cases.append(('(b)ThreadPoolExecutor.submit', 'pool'))
    with concurrent.futures.ThreadPoolExecutor(2) as ex: ex.submit(contextvars.copy_context().run, child, 'pool_copy').result()
    cases.append(('(c)submit(copy_context().run, f)', 'pool_copy'))
    saved = otctx.get_current()
    def with_ctx(tag):
        tok = otctx.attach(saved)
        try: child(tag)
        finally: otctx.detach(tok)
    t = threading.Thread(target=with_ctx, args=('thread_attach',)); t.start(); t.join(); cases.append(('(d)线程里 attach 保存的上下文', 'thread_attach'))
table([(n, verdict(tag, pc)) for n, tag in cases], ['做法', '子 span 的归属'])
print('  新线程的 contextvars 是空的:线程池和 threading.Thread 都不会把调用方的上下文带过去,子 span 就成了新 trace 的根;要显式带上(copy_context().run 或者 attach)')

# ============ 二 ============
print('== 二:跨协程。在一个 span 里(协程里),用几种方式去创建子 span:create_task、gather、run_in_executor、asyncio.to_thread、call_soon、从另一个线程 call_soon_threadsafe、从事件循环自己的线程 call_soon_threadsafe')
exp.clear(); cases2 = []
async def amain():
    with tracer.start_as_current_span('aparent') as p:
        pc = p.get_span_context(); loop = asyncio.get_running_loop()
        await asyncio.create_task(achild('task')); cases2.append(('asyncio.create_task', 'task'))
        await asyncio.gather(achild('gather1'), achild('gather2')); cases2.append(('asyncio.gather(两个协程)', 'gather1'))
        await loop.run_in_executor(None, child, 'executor'); cases2.append(('loop.run_in_executor', 'executor'))
        await loop.run_in_executor(None, contextvars.copy_context().run, child, 'executor_copy'); cases2.append(('run_in_executor + copy_context().run', 'executor_copy'))
        await asyncio.to_thread(child, 'to_thread'); cases2.append(('asyncio.to_thread', 'to_thread'))
        loop.call_soon(child, 'call_soon'); await asyncio.sleep(0.05); cases2.append(('loop.call_soon', 'call_soon'))
        threading.Thread(target=lambda: loop.call_soon_threadsafe(child, 'ts_other_thread')).start(); await asyncio.sleep(0.05); cases2.append(('另一个线程里 call_soon_threadsafe', 'ts_other_thread'))
        loop.call_soon_threadsafe(child, 'ts_same_thread'); await asyncio.sleep(0.05); cases2.append(('事件循环线程里 call_soon_threadsafe', 'ts_same_thread'))
        return pc
pc2 = asyncio.run(amain())
table([(n, verdict(tag, pc2)) for n, tag in cases2], ['做法', '子 span 的归属'])
print('  协程之间(create_task、gather)和 to_thread 会复制调用方的上下文;run_in_executor 不会;call_soon 取决于调用时所在线程的上下文,从另一个线程调用拿到的是那个线程自己的(空)上下文')

# ============ 三 ============
print('== 三:跨消息队列。RabbitMQ 一个队列。生产者在 PRODUCER span 里发消息,消息头可以带 traceparent。(a)不带;(b)带,消费者在 1 s 之后处理,span 作为生产者 span 的子 span;(c)3 个不同 trace 里的生产者各发一条,消费者一次批量处理这 3 条:一个 span 只能有一个父 span,所以用 3 个 span link 指向各自的生产者')
RQ = ql.Node('v62_rq'); RQ.start()
conn = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', RQ.amqp)); ch = conn.channel(); ch.queue_declare('work', durable=True)
def produce(tag, inject=True):
    with tracer.start_as_current_span(f'produce:{tag}', kind=SpanKind.PRODUCER) as sp:
        h = {}
        if inject: propagate.inject(h)
        ch.basic_publish('', 'work', tag.encode(), pika.BasicProperties(headers=h, delivery_mode=2)); return sp.get_span_context()
def fetch():
    m, props, body = ch.basic_get('work', auto_ack=True); return body.decode(), (props.headers or {}) if m else None
exp.clear(); rows = []
pa = produce('a', inject=False); body, hd = fetch()
with tracer.start_as_current_span('consume:a', kind=SpanKind.CONSUMER, context=propagate.extract(hd)) as sp: ca = sp
sa = [s for s in exp.get_finished_spans() if s.name == 'consume:a'][0]
rows.append(('(a)消息头不带 traceparent', '消费者 span 是新 trace 的根' if sa.parent is None and sa.context.trace_id != pa.trace_id else '?', '-'))
pb = produce('b'); t_pub = time.time(); time.sleep(1.0); body, hd = fetch(); ctx = propagate.extract(hd)
t_c0 = time.time()
with tracer.start_as_current_span('consume:b', kind=SpanKind.CONSUMER, context=ctx): time.sleep(0.01)
sb = [s for s in exp.get_finished_spans() if s.name == 'consume:b'][0]; spb = [s for s in exp.get_finished_spans() if s.name == 'produce:b'][0]
rows.append(('(b)带 traceparent,1 s 后消费', '消费者 span 是生产者 span 的子 span(同一个 trace)' if sb.parent is not None and sb.parent.span_id == pb.span_id and sb.context.trace_id == pb.trace_id else '?', f'生产者 span 在 {(spb.end_time - spb.start_time) / 1e6:.2f} ms 时结束,消费者 span 在它结束之后 {(sb.start_time - spb.end_time) / 1e6:.0f} ms 才开始'))
pcs = [produce(f'c{i}') for i in range(3)]; msgs = [fetch() for _ in range(3)]
links = [Link(trace.get_current_span(propagate.extract(hd)).get_span_context()) for _, hd in msgs]
with tracer.start_as_current_span('consume:batch', kind=SpanKind.CONSUMER, links=links): time.sleep(0.01)
sc = [s for s in exp.get_finished_spans() if s.name == 'consume:batch'][0]
ok = [l.context.trace_id == pc_.trace_id and l.context.span_id == pc_.span_id for l, pc_ in zip(sc.links, pcs)]
rows.append(('(c)3 条消息批量处理', f'批量 span 自己是新 trace 的根(parent={"无" if sc.parent is None else "有"}),带 {len(sc.links)} 个 link,各自指向对应的生产者 span:{all(ok)}', f'3 个生产者的 trace_id 互不相同:{len({p_.trace_id for p_ in pcs}) == 3};批量 span 的 trace_id 与它们都不同:{all(sc.context.trace_id != p_.trace_id for p_ in pcs)}'))
table(rows, ['情形', '结果', '备注'])
print('  parent-child 表示“这个 span 是那个 span 的一部分”;消息被延迟消费、或者一个 span 同时处理多个来源时,用 link 只记录“因果相关”,不放进同一棵树里')
conn.close(); RQ.stop() if hasattr(RQ, 'stop') else None
print('ERRORS', dict(ERRORS))
