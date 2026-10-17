import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q5'); reset()
n = Node('q5'); n.start()
px = Proxy(n.amqp)
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); ch = c.channel()
qdecl(ch, 'cq')

print('== 一:开启 confirm 模式后每条发布都会收到 broker 的 Basic.Ack(带 delivery-tag 和 multiple 标志);线上看一次连发 10 条会收到几个 Ack')
ch.confirm_delivery()
m = px.mark()
ch2 = c.channel(); ch2.confirm_delivery()
for i in range(10): ch2.basic_publish('', 'cq', f'm{i}'.encode(), pika.BasicProperties(delivery_mode=2))
ev = px.names(m)
acks = [e[2] for e in ev if e[2].startswith('Basic.Ack')]
sel = [e[2] for e in ev if e[2].startswith('Confirm.Select')]
print(f'  Confirm.Select / SelectOk 帧共 {len(sel)} 个(两个 channel 各开了一次);发布 10 条(pika BlockingChannel 每条同步等 ack)收到的 Basic.Ack:')
for a in acks: print('    ' + a)
ch2.queue_purge('cq')

print('== 二:不等一条一条的 ack:用 pika 的 SelectConnection 一口气发 5000 条,看 broker 把多少条合并成一个 multiple=True 的 Ack')
import pika.adapters.select_connection
def async_run(n_msgs, window, persistent=True, queue='cq', body=b'x' * 100, with_proxy=False):
    res = {'acks': [], 'sent': 0, 'conf': 0, 'outstanding': 0, 't0': None, 't1': None}
    port = px.port if with_proxy else n.amqp
    done = threading.Event()
    def on_open(conn): conn.channel(on_open_callback=on_ch)
    def on_ch(chn):
        res['ch'] = chn; chn.confirm_delivery(on_confirm, callback=lambda f: go())
    def on_confirm(frame):
        m_ = frame.method; k = m_.delivery_tag if not m_.multiple else None
        # 已确认数
        if isinstance(m_, pika.spec.Basic.Ack):
            cnt = (m_.delivery_tag - res['last']) if m_.multiple else 1
            res['last'] = m_.delivery_tag if m_.multiple else max(res['last'], m_.delivery_tag)
            res['acks'].append(cnt)
        else: res['nacks'] = res.get('nacks', 0) + 1; return
        res['conf'] += cnt
        if res['conf'] >= n_msgs:
            res['t1'] = time.perf_counter(); done.set()
        else: go()
    def go():
        chn = res['ch']; props = pika.BasicProperties(delivery_mode=2 if persistent else 1)
        while res['sent'] < n_msgs and res['sent'] - res['conf'] < window:
            chn.basic_publish('', queue, body, props); res['sent'] += 1
        if res['t0'] is None: pass
    res['last'] = 0
    conn = pika.SelectConnection(pika.ConnectionParameters('127.0.0.1', port), on_open_callback=on_open)
    res['t0'] = time.perf_counter()
    th = threading.Thread(target=conn.ioloop.start, daemon=True); th.start()
    done.wait(120)
    el = (res['t1'] - res['t0']) * 1000
    conn.ioloop.add_callback_threadsafe(conn.close) if hasattr(conn.ioloop, 'add_callback_threadsafe') else None
    time.sleep(0.2)
    try: conn.ioloop.stop()
    except Exception: pass
    return el, res
m = px.mark()
el, res = async_run(5000, 1000, with_proxy=True)
acks = [e[2] for e in px.names(m, 'S→C') if e[2].startswith('Basic.Ack')]
multi = [a for a in acks if 'multiple=True' in a]
print(f'  发 5000 条持久化消息,在途上限 1000:耗时 {el:.0f} ms;broker 一共发了 {len(acks)} 个 Basic.Ack,其中 multiple=True 的 {len(multi)} 个')
sizes = res['acks']
print(f'  每个 Ack 确认的条数: 最小 {min(sizes)},中位数 {median(sizes):.0f},最大 {max(sizes)};前 8 个 Ack: {sizes[:8]}')
ch.queue_purge('cq')

print('== 三:四种发布方式的吞吐(5000 条 100 字节持久化消息到持久队列):不开 confirm(pika BlockingConnection 连发)、每条同步等 confirm(BlockingConnection)、异步在途上限 100 / 1000(pika SelectConnection);各 3 次取中位数。注意前两行和后两行用的是不同的 pika 连接类型,数字不能直接当成“confirm 比不 confirm 更快”')
def sync_each(N):
    cc = n.conn(); cch = cc.channel(); cch.confirm_delivery(); props = pika.BasicProperties(delivery_mode=2)
    t0 = time.perf_counter()
    for i in range(N): cch.basic_publish('', 'cq', b'x' * 100, props)
    e = ms(t0); cc.close(); return e
def async_(N, W): 
    el, _ = async_run(N, W); return el
N = 5000
r1 = median([sync_each(N) for _ in range(3)]); ch.queue_purge('cq')
r2 = median([async_(N, 100) for _ in range(3)]); ch.queue_purge('cq')
r3 = median([async_(N, 1000) for _ in range(3)]); ch.queue_purge('cq')
r0 = None
def no_confirm(N):
    cc = n.conn(); cch = cc.channel(); props = pika.BasicProperties(delivery_mode=2)
    t0 = time.perf_counter()
    for i in range(N): cch.basic_publish('', 'cq', b'x' * 100, props)
    cch.queue_declare('cq', passive=True); e = ms(t0); cc.close(); return e
r0 = median([no_confirm(N) for _ in range(3)]); ch.queue_purge('cq')
for name, v in (('不开 confirm(阻塞)', r0), ('每条同步等 confirm', r1), ('在途上限 100', r2), ('在途上限 1000', r3)):
    print(f'  {name:<16}{v:>8.0f} ms  {N / v * 1000:>8.0f} 条/秒')

print('== 四:单条 confirm 的延迟:持久化 vs 非持久化,同步等每条的 ack,各 2000 条取 p50 / p99')
def lat(persistent, N=2000):
    cc = n.conn(); cch = cc.channel(); cch.confirm_delivery(); props = pika.BasicProperties(delivery_mode=2 if persistent else 1)
    ts = []
    for i in range(N):
        t0 = time.perf_counter(); cch.basic_publish('', 'cq', b'x' * 100, props); ts.append(ms(t0))
    cc.close(); ts.sort(); return ts[len(ts) // 2], ts[int(len(ts) * 0.99)]
for pers in (False, True):
    a, b = lat(pers); print(f'  {"持久化" if pers else "非持久化"}:p50 = {a:.2f} ms,p99 = {b:.2f} ms')
ch.queue_purge('cq')

print('== 五:不可路由的消息:没有队列接收也会收到 Ack(confirm 只表示“broker 处理完了”,不表示“进了队列”);加 mandatory=True 则先收到 Basic.Return 再收到 Ack')
ch.exchange_declare('x.nobind', 'direct', durable=True)
cc = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); cch = cc.channel(); cch.confirm_delivery()
m = px.mark()
cch.basic_publish('x.nobind', 'k', b'lost')
print(f'  mandatory=False 发到没有绑定的 exchange,线上帧: {[e[2] for e in px.names(m) if e[0] == "S→C" or e[2].startswith("Basic.Publish")]}')
m = px.mark()
try: cch.basic_publish('x.nobind', 'k', b'lost', mandatory=True)
except Exception as e: err = f'{type(e).__name__}'
print(f'  mandatory=True,线上帧: {[e[2] for e in px.names(m) if e[0] == "S→C" or e[2].startswith("Basic.Publish")]};pika 抛出 {err}')
cc.close()

print('== 六:队列满且 overflow=reject-publish 时,broker 发 Basic.Nack:发布方知道这条没收下')
qdecl(ch, 'cq.small', arguments={'x-max-length': 3, 'x-overflow': 'reject-publish'}); ch.queue_purge('cq.small')
cc = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); cch = cc.channel(); cch.confirm_delivery()
m = px.mark(); out = []
for i in range(5):
    try: cch.basic_publish('', 'cq.small', f'm{i}'.encode()); out.append('ack')
    except Exception as e: out.append(type(e).__name__)
print(f'  x-max-length=3,连发 5 条的结果: {out}')
print(f'  线上 broker 发出的确认帧: {[e[2] for e in px.names(m, "S→C") if e[2].startswith("Basic.")]}')
print(f'  队列里最终有 {n.qinfo("cq.small")[0]} 条')
cc.close(); c.close(); px.close(); n.stop()
