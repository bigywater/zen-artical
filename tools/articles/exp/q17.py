import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
import datetime
tee('q17'); reset()
n = Node('q17', plugins=['rabbitmq_stream']); n.start()
c = n.conn(); ch = c.channel()
def mk_stream(name, **a):
    ch.queue_delete(name); ch.queue_declare(name, durable=True, arguments=dict({'x-queue-type': 'stream'}, **a))
def consume(q, offset, k=None, wait=1.0, prefetch=100, chn=None):
    """从 stream 消费:返回 [(offset, body)];stream 的消费者必须设 prefetch 并手动 ack"""
    cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=prefetch); got = []
    def cb(chn_, m, p, b):
        got.append((p.headers.get('x-stream-offset'), b.decode())); chn_.basic_ack(m.delivery_tag)
    args = {} if offset is None else {'x-stream-offset': offset}
    cch.basic_consume(q, cb, arguments=args)
    t0 = time.time()
    while time.time() - t0 < wait and (k is None or len(got) < k): cc.process_data_events(0.05)
    cc.close(); return got

print('== 一:stream 队列是追加日志:消息读完不会消失。发 10 条,消费者 A 读完并 ack,消费者 B 再从头读,队列里的消息数不变')
mk_stream('s1')
for i in range(10): ch.basic_publish('', 's1', f'm{i}'.encode())
time.sleep(0.5)
a = consume('s1', 'first', 10)
print(f'  消费者 A(offset=first)读到并 ack: {[x[1] for x in a]};带的 offset 头: {[int(x[0]) for x in a]}')
time.sleep(0.5)
b = consume('s1', 'first', 10)
print(f'  消费者 B 随后也从头读: {[x[1] for x in b]}(消息还在)')
import json as _j
def sstatus(q):
    o = subprocess.run([f'{SBIN}/rabbitmq-streams', '-n', n.nodename, '--formatter', 'json', 'stream_status', q], env=n.env(), capture_output=True, text=True).stdout
    return _j.loads(o[o.index('['):])
st = sstatus('s1')[0]
print('  rabbitmq-streams stream_status s1: ' + ', '.join(f'{k}={v}' for k, v in st.items() if k in ('role', 'epoch', 'offset', 'committed_offset', 'first_offset', 'readers', 'segments')))

print('== 二:x-stream-offset 的各种取值:first / last / next / 数字 / 时间戳 / 没有设')
mk_stream('s2')
t_mid = None
for i in range(30):
    ch.basic_publish('', 's2', f'm{i}'.encode())
    if i == 14: time.sleep(1.2); t_mid = datetime.datetime.now(datetime.timezone.utc); time.sleep(1.2)
time.sleep(1)
for label, off in (('first', 'first'), ('last', 'last'), ('next', 'next'), ('数字 20', 20), ('时间戳(第 15 条之后)', t_mid), ('不设', None)):
    try:
        r = consume('s2', off, wait=1.2)
        print(f'  offset={label:<16}→ 收到 {len(r):>2} 条,第一条 {r[0][1] if r else "-"}(offset {int(r[0][0]) if r else "-"}),最后一条 {r[-1][1] if r else "-"}')
    except Exception as e: print(f'  offset={label}: {type(e).__name__}: {str(e)[:120]}')
print('  不设 offset 时的默认行为是 next(只收订阅之后新到的),所以 0 条')

print('== 三:两个消费者各自的位置互不影响;重启消费者后从自己的 offset 继续(消费者用 offset 记位置,broker 不替你存)')
mk_stream('s3')
for i in range(20): ch.basic_publish('', 's3', f'm{i}'.encode())
time.sleep(0.5)
first5 = consume('s3', 'first', 5)[:5]   # 一次投递的是整个 chunk,回调里实际收到的比 5 多;这里只“处理”前 5 条并记下 offset
last_off = int(first5[-1][0])
rest = consume('s3', last_off + 1, wait=1.0)
print(f'  先读 5 条(最后一条 offset={last_off}),下次用 offset={last_off + 1} 继续,读到 {len(rest)} 条: 从 {rest[0][1]} 到 {rest[-1][1]}')

print('== 四:不支持的操作:basic_get、requeue / reject、非持久、exclusive、优先级、不设 prefetch 就消费')
def err(fn):
    try: fn(); return '成功'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:170]}'
print('  basic_get:           ', err(lambda: n.conn().channel().basic_get('s1')))
print('  不设 prefetch 消费:   ', err(lambda: (lambda cc: (cc.channel().basic_consume('s1', lambda *a: None), cc.process_data_events(1)))(n.conn())))
print('  durable=False:       ', err(lambda: n.conn().channel().queue_declare('sx', durable=False, arguments={'x-queue-type': 'stream'})))
print('  exclusive=True:      ', err(lambda: n.conn().channel().queue_declare('sx', durable=True, exclusive=True, arguments={'x-queue-type': 'stream'})))
print('  auto_ack 消费:       ', err(lambda: (lambda cc: (lambda ch_: (ch_.basic_qos(prefetch_count=10), ch_.basic_consume('s1', lambda *a: None, auto_ack=True), cc.process_data_events(1)))(cc.channel()))(n.conn())))

print('== 五:保留策略:x-max-length-bytes 限制总大小,按“段”整段删除最老的;段大小 x-stream-max-segment-size-bytes。限制 20 MB、段 5 MB,发 60000 条 1 KB(共约 60 MB)')
mk_stream('s5', **{'x-max-length-bytes': 20 * 1000 * 1000, 'x-stream-max-segment-size-bytes': 5 * 1000 * 1000})
body = b'x' * 1024
for i in range(60000): ch.basic_publish('', 's5', body)
ch.queue_declare('s5', passive=True); time.sleep(3)
r = consume('s5', 'first', 1, wait=2)
st = sstatus('s5')[0]
print(f'  发了 60000 条;第一条还能读到的 offset = {int(r[0][0])};stream_status: first_offset={st.get("first_offset")} committed_offset={st.get("committed_offset")} segments={st.get("segments")}')
segs = sorted(n.d.rglob('*.segment'), key=lambda f: f.name)
idx = sorted(n.d.rglob('*.index'))
print(f'  数据目录里的 .segment 文件: {[(f.name, f.stat().st_size // 1024 // 1024) for f in segs]}(名字是这个段第一条消息的 offset,第二项是 MiB);.index 文件 {len(idx)} 个,每段一个')
print('== 六:消费吞吐:同一批 100000 条 100 字节消息,classic 队列消费并 ack vs stream 消费并 ack(prefetch=1000);各 3 次中位数')
mk_stream('s6'); ch.queue_delete('c6'); ch.queue_declare('c6', durable=True)
for i in range(100000):
    ch.basic_publish('', 's6', b'x' * 100); ch.basic_publish('', 'c6', b'x' * 100)
ch.queue_declare('s6', passive=True); ch.queue_declare('c6', passive=True); time.sleep(3)
def drain_time(q, off):
    cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=1000)
    cnt = [0]
    def cb(chn_, m, p, b): cnt[0] += 1; (chn_.basic_ack(m.delivery_tag, multiple=True) if cnt[0] % 100 == 0 else None)
    args = {'x-stream-offset': off} if off else {}
    t0 = time.perf_counter(); cch.basic_consume(q, cb, arguments=args)
    while cnt[0] < 100000: cc.process_data_events(0.5)
    e = ms(t0); cc.close(); return e
ts_s = [drain_time('s6', 'first') for _ in range(3)]
print(f'  stream 读 100000 条: {median(ts_s):.0f} ms(可重复读 3 次,每次都是同样的 100000 条)')
t_c = drain_time('c6', None)
print(f'  classic 读 100000 条: {t_c:.0f} ms(读完就没了,只能读 1 次)')
c.close(); n.stop()
