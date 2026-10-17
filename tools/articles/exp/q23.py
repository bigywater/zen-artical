import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
import aio_pika
tee('q23'); reset()
n = Node('q23'); n.start()

print('== 一:pika 的 BlockingConnection 没有自动重连:broker 强制关闭连接(rabbitmqctl close_connection),消费者循环直接抛异常,什么也不会自己恢复')
c = n.conn(); ch = c.channel(); ch.queue_declare('rc', durable=True); ch.queue_purge('rc')
got = []
ch.basic_consume('rc', lambda chn, m, p, b: (got.append(b.decode()), chn.basic_ack(m.delivery_tag)))
pub = n.conn().channel(); pub.basic_publish('', 'rc', b'before')
for _ in range(10): c.process_data_events(0.1)
print(f'  消费者在线时收到: {got}')
lp = c._impl._transport._sock.getsockname()[1]
cn = [l.split(chr(9)) for l in n.ctl('list_connections', 'pid', 'peer_port').splitlines() if chr(9) in l and not l.startswith('pid')]
cpid = next(x[0] for x in cn if int(x[1]) == lp)
out = n.ctl('close_connection', cpid, 'closed by operator')
pub.basic_publish('', 'rc', b'after')
print('  $ rabbitmqctl close_connection "<pid>" "closed by operator"')
try:
    for _ in range(10): c.process_data_events(0.1)
    r = '没有异常'
except Exception as e: r = f'{type(e).__name__}: {str(e)[:110]}'
print(f'  之后 process_data_events: {r}')
time.sleep(0.3)
print(f'  连接状态: is_open={c.is_open};另一个连接又发了 "after" 一条,队列里现有 (ready, unacked) = {n.qinfo("rc")}——没有消费者了,消息停在队列里')
pub.queue_purge('rc')

print('== 二:aio-pika 的 connect_robust:断线后自动重连,并把 exchange / 队列 / 绑定 / 消费者重新声明。持续每 10 ms 发一条带序号的持久化消息(带 confirm),期间正常关闭 broker 再启动')
async def scenario():
    url = f'amqp://guest:guest@127.0.0.1:{n.amqp}/'
    conn = await aio_pika.connect_robust(url, reconnect_interval=1)
    rx = await conn.channel(); await rx.set_qos(prefetch_count=50)
    ex = await rx.declare_exchange('rx', aio_pika.ExchangeType.DIRECT, durable=True)
    q = await rx.declare_queue('rq', durable=True); await q.bind(ex, 'k')
    recv = []; redel = []
    async def on_msg(m: aio_pika.IncomingMessage):
        seq = int(m.body); recv.append((time.perf_counter(), seq)); 
        if m.redelivered: redel.append(seq)
        await m.ack()
    await q.consume(on_msg)
    pconn = await aio_pika.connect_robust(url, reconnect_interval=1)
    pch = await pconn.channel(publisher_confirms=True); pex = await pch.get_exchange('rx')
    sent = []; failed = []; stop = asyncio.Event()
    async def producer():
        i = 0
        while not stop.is_set():
            i += 1
            try:
                await asyncio.wait_for(pex.publish(aio_pika.Message(str(i).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT), routing_key='k'), 5)
                sent.append((time.perf_counter(), i))
            except Exception as e: failed.append((time.perf_counter(), i, type(e).__name__))
            await asyncio.sleep(0.01)
    pt = asyncio.create_task(producer())
    await asyncio.sleep(2)
    return conn, pconn, recv, redel, sent, failed, stop, pt
async def main2():
    conn, pconn, recv, redel, sent, failed, stop, pt = await scenario()
    t_stop = time.perf_counter()
    await asyncio.get_running_loop().run_in_executor(None, n.stop)
    t_down = time.perf_counter()
    await asyncio.sleep(3)
    await asyncio.get_running_loop().run_in_executor(None, n.start)
    t_up = time.perf_counter()
    await asyncio.sleep(8)
    stop.set(); await pt
    await asyncio.sleep(1)
    # 统计
    after = [r for r in recv if r[0] > t_up]
    first_after = after[0][0] - t_up if after else None
    got_seq = [s for _, s in recv]
    sent_seq = [s for _, s in sent]
    lost = sorted(set(sent_seq) - set(got_seq))
    dup = len(got_seq) - len(set(got_seq))
    print(f'  broker 关闭用了 {t_down - t_stop:.1f} s,重新启动到可用用了 {t_up - t_down:.1f} s')
    print(f'  broker 重新可用之后,消费者收到的第一条消息在 {first_after:.2f} s 后(reconnect_interval=1 s)')
    print(f'  发布端:确认成功 {len(sent)} 条,失败/超时 {len(failed)} 条(异常类型 {sorted(set(f[2] for f in failed))});消费端:共收到 {len(got_seq)} 条,重复 {dup} 条,redelivered=True 的 {len(redel)} 条')
    print(f'  已确认发送但没收到的序号: {lost[:10]}{"…" if len(lost) > 10 else ""}(共 {len(lost)} 条)')
    gaps = [b[0] - a[0] for a, b in zip(recv, recv[1:])]
    print(f'  消费端相邻两条消息的最大间隔: {max(gaps):.2f} s(= 停机 + 重连期间的中断)')
    await conn.close(); await pconn.close()
asyncio.run(main2())

print('== 三:队列被别人删掉(或所在节点故障)时,broker 主动取消消费者(consumer_cancel_notify):客户端会收到 Basic.Cancel')
n2 = Node('q23b'); n2.start()
c = n2.conn(); ch = c.channel(); ch.queue_declare('dq', durable=True)
cancelled = []
ch.add_on_cancel_callback(lambda frame: cancelled.append(type(frame.method).__name__))
ch.basic_consume('dq', lambda *a: None)
n2.conn().channel().queue_delete('dq')
for _ in range(10): c.process_data_events(0.1)
print(f'  另一个客户端删除队列 dq 之后,消费者收到: {cancelled}(Basic.Cancel);channel 仍然开着: is_open={ch.is_open}')
print('  这种取消不会触发连接级的重连逻辑,客户端必须自己监听 cancel 并重新声明队列、重新订阅')
c.close(); n2.stop()

print('== 四:robust 连接重启后的拓扑恢复:排他队列在 broker 重启后本身会消失,但 robust 客户端会按原名重新声明出来(aio-pika 的空队列名是客户端自己生成的 amq_<uuid>,不是服务器命名);里面原来的消息是没有的')
async def main4():
    conn = await aio_pika.connect_robust(f'amqp://guest:guest@127.0.0.1:{n.amqp}/', reconnect_interval=1)
    chn = await conn.channel()
    q = await chn.declare_queue('', exclusive=True)    # 服务器命名 + 排他
    qd = await chn.declare_queue('keepme', durable=True)
    name1 = q.name
    await asyncio.get_running_loop().run_in_executor(None, n.restart)
    await asyncio.sleep(5)
    chn2 = await conn.channel()
    try:
        info = await chn2.declare_queue(name1, passive=True); r = '存在(被 robust 客户端重新声明)'
    except Exception as e: r = f'不存在: {type(e).__name__}'
    print(f'  排他队列(aio-pika 生成的名字 amq_…)重启后按原名 passive 声明: {r}')
    print(f'  durable 的 keepme 重启后: {(await chn2.declare_queue("keepme", durable=True, passive=True)).name}(本来就在磁盘上)')
    await conn.close()
asyncio.run(main4())
n.stop()
