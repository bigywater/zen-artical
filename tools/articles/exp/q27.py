import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q27'); reset()
n = Node('q27'); n.start()
px = Proxy(n.amqp)
c0 = n.conn(); ch0 = c0.channel(); ch0.queue_declare('tq', durable=True); ch0.queue_declare('tq2', durable=True)

print('== 一:事务模式在线上的样子:Tx.Select → 发布 3 条 → Tx.Commit → Tx.CommitOk;回滚则是 Tx.Rollback。提交之前别的客户端看不到这些消息')
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); ch = c.channel()
m = px.mark()
ch.tx_select()
for i in range(3): ch.basic_publish('', 'tq', f'm{i}'.encode(), pika.BasicProperties(delivery_mode=2))
time.sleep(0.3)
print(f'  提交之前别的连接看到队列 tq 里有 {n.qinfo("tq")[0]} 条')
ch.tx_commit()
for d, chn, name, sz in px.names(m): print(f'  {d}  ch{chn}  {name:<16}{sz:>4} 字节')
print(f'  提交之后队列 tq 里有 {n.qinfo("tq")[0]} 条')
c.close(); px.close()

print('== 二:回滚:发布 3 条再 rollback,队列不变;跨队列的事务:一个事务里往 tq、tq2 各发 1 条,提交后同时可见')
ch0.queue_purge('tq'); ch0.queue_purge('tq2')
c = n.conn(); ch = c.channel(); ch.tx_select()
for i in range(3): ch.basic_publish('', 'tq', b'x')
ch.tx_rollback()
print(f'  发布 3 条后 rollback:tq 里有 {n.qinfo("tq")[0]} 条')
ch.basic_publish('', 'tq', b'a'); ch.basic_publish('', 'tq2', b'b')
ch.tx_commit(); time.sleep(0.3)
print(f'  一个事务里往两个队列各发一条并提交:tq {n.qinfo("tq")[0]} 条、tq2 {n.qinfo("tq2")[0]} 条')
print('  事务里的消费确认也能回滚:')
mt, p, b = ch.basic_get('tq'); ch.basic_ack(mt.delivery_tag); ch.tx_rollback(); time.sleep(0.3)
print(f'    取一条并 ack 后 tx_rollback:tq (ready, unacked) = {n.qinfo("tq")}(ack 被撤销,消息仍是未确认,回滚不会让它回到 ready;关闭 channel 后才回队列)')
c.close(); time.sleep(0.3)
print(f'    关闭连接后: {n.qinfo("tq")}')

print('== 三:吞吐对比:5000 条 100 字节持久化消息发到持久队列。事务每 N 条提交一次(N = 1 / 10 / 100 / 1000),与 publisher confirm(同步逐条、异步窗口 1000)、不确认。每种 3 轮中位数')
N = 5000; body = b'x' * 100; props = pika.BasicProperties(delivery_mode=2)
def tx_run(batch):
    ch0.queue_purge('tq'); cc = n.conn(); cch = cc.channel(); cch.tx_select()
    t0 = time.perf_counter()
    for i in range(N):
        cch.basic_publish('', 'tq', body, props)
        if (i + 1) % batch == 0: cch.tx_commit()
    e = ms(t0); cc.close(); return e
def confirm_sync():
    ch0.queue_purge('tq'); cc = n.conn(); cch = cc.channel(); cch.confirm_delivery()
    t0 = time.perf_counter()
    for i in range(N): cch.basic_publish('', 'tq', body, props)
    e = ms(t0); cc.close(); return e
def confirm_async():
    ch0.queue_purge('tq'); return async_publish(n.amqp, 'tq', N, 1000, body, True)[0]
def noconf():
    ch0.queue_purge('tq'); cc = n.conn(); cch = cc.channel()
    t0 = time.perf_counter()
    for i in range(N): cch.basic_publish('', 'tq', body, props)
    cch.queue_declare('tq', passive=True); e = ms(t0); cc.close(); return e
rows = []
for label, fn in (('事务,每条提交', lambda: tx_run(1)), ('事务,每 10 条提交', lambda: tx_run(10)), ('事务,每 100 条提交', lambda: tx_run(100)), ('事务,每 1000 条提交', lambda: tx_run(1000)),
                  ('confirm,同步逐条等', confirm_sync), ('confirm,异步窗口 1000', confirm_async), ('不确认(阻塞)', noconf)):
    rows.append((label, median([fn() for _ in range(3)])))
print('  方式                      耗时      吞吐')
for label, v in rows: print(f'  {label:<22}{v:>8.0f} ms{N / v * 1000:>10.0f} 条/秒')

print('== 四:单次提交的延迟(每次 1 条消息 + commit,持久化,2000 次):事务提交 vs confirm 同步等 ack,p50 / p99')
def lat_tx(K=2000):
    cc = n.conn(); cch = cc.channel(); cch.tx_select(); ts = []
    for i in range(K):
        t0 = time.perf_counter(); cch.basic_publish('', 'tq', body, props); cch.tx_commit(); ts.append(ms(t0))
    cc.close(); ts.sort(); return ts[K // 2], ts[int(K * 0.99)]
def lat_cf(K=2000):
    cc = n.conn(); cch = cc.channel(); cch.confirm_delivery(); ts = []
    for i in range(K):
        t0 = time.perf_counter(); cch.basic_publish('', 'tq', body, props); ts.append(ms(t0))
    cc.close(); ts.sort(); return ts[K // 2], ts[int(K * 0.99)]
a = lat_tx(); b = lat_cf()
print(f'  事务 publish+commit:p50 {a[0]:.3f} ms,p99 {a[1]:.3f} ms')
print(f'  confirm publish+等 ack:p50 {b[0]:.3f} ms,p99 {b[1]:.3f} ms')
c0.close(); n.stop()
