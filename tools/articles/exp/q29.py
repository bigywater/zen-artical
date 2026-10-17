import sys, os, uuid; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q29'); reset()
n = Node('q29'); n.start()
px = Proxy(n.amqp)
c0 = n.conn(); ch0 = c0.channel(); ch0.queue_declare('rpc_queue', durable=True)

print('== 一:RPC 的一次往返在线上的样子:客户端声明一个独占的回复队列,发请求时带 reply_to 和 correlation_id;服务端处理后把响应发到 reply_to 队列(经默认 exchange,routing key = reply_to),同样带上 correlation_id')
def server_loop(stop, delay=0.0):
    cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=1)
    def cb(chn, m, p, b):
        if delay: time.sleep(delay)
        chn.basic_publish('', p.reply_to, b'resp:' + b, pika.BasicProperties(correlation_id=p.correlation_id))
        chn.basic_ack(m.delivery_tag)
    cch.basic_consume('rpc_queue', cb)
    while not stop.is_set(): cc.process_data_events(0.02)
    cc.close()
stop = threading.Event(); st = threading.Thread(target=server_loop, args=(stop,), daemon=True); st.start()
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); ch = c.channel()
res = ch.queue_declare('', exclusive=True); rq = res.method.queue
got = []
tag1 = ch.basic_consume(rq, lambda chn, m, p, b: got.append((p.correlation_id, b.decode())), auto_ack=True)
cid = str(uuid.uuid4())
m = px.mark()
ch.basic_publish('', 'rpc_queue', b'ping', pika.BasicProperties(reply_to=rq, correlation_id=cid))
t0 = time.perf_counter()
while not got and time.perf_counter() - t0 < 5: c.process_data_events(0.01)
print(f'  客户端声明了独占队列 {rq[:8]}…(服务器生成的名字,前缀 amq.gen-);请求 correlation_id = {cid[:8]}…;收到响应 {got[0][1]!r},correlation_id 是否一致: {got[0][0] == cid};往返 {ms(t0):.1f} ms')
for d, chn, name, sz in px.names(m): 
    if name in ('Basic.Publish', 'Basic.Deliver', 'ContentHeader'): print(f'  {d}  ch{chn}  {name:<14}{sz:>4} 字节')

print('== 二:correlation_id 的作用:同一个回复队列上有多个未完成的请求,响应可能乱序到达,靠 correlation_id 对应。两个服务端实例(一个慢 300 ms、一个快 10 ms)共同消费 rpc_queue,客户端连发 6 个请求,看响应的到达顺序')
stop.set(); st.join(2); ch.basic_cancel(tag1)
stopA = threading.Event(); stopB = threading.Event()
threading.Thread(target=lambda: server_loop(stopA, 0.3), daemon=True).start()
threading.Thread(target=lambda: server_loop(stopB, 0.01), daemon=True).start()
time.sleep(0.5)
pending = {}
got2 = []
ch.basic_consume(rq, lambda chn, m, p, b: got2.append((p.correlation_id, b.decode())), auto_ack=True)
for k in range(6):
    cid_k = f'req-{k}'; pending[cid_k] = k
    ch.basic_publish('', 'rpc_queue', str(k).encode(), pika.BasicProperties(reply_to=rq, correlation_id=cid_k))
t0 = time.perf_counter()
while len(got2) < 6 and time.perf_counter() - t0 < 10: c.process_data_events(0.01)
print(f'  请求发送顺序: req-0 .. req-5;响应到达顺序: {[cid_ for cid_, _ in got2]};每个响应的 correlation_id 都能对回自己的请求: ' + str(all(pending[cid_] == int(b.split(":")[1]) for cid_, b in got2)))
time.sleep(0.5); stopA.set(); stopB.set(); time.sleep(0.5)

print('== 三:回复队列的三种做法的代价:(a) 每次请求新建一个独占队列;(b) 复用一个独占回复队列 + correlation_id;(c) direct reply-to(amq.rabbitmq.reply-to,伪队列,不需要声明)。每种做 2000 次顺序调用,服务端立即回复,看每次往返的耗时')
stop3 = threading.Event(); threading.Thread(target=server_loop, args=(stop3,), daemon=True).start()
time.sleep(0.3)
def rpc_new_queue(K=2000):
    cc = n.conn(); cch = cc.channel(); ts = []
    for i in range(K):
        t0 = time.perf_counter()
        rq_ = cch.queue_declare('', exclusive=True).method.queue; box = []
        tag = cch.basic_consume(rq_, lambda chn, m, p, b: box.append(1), auto_ack=True)
        cch.basic_publish('', 'rpc_queue', b'x', pika.BasicProperties(reply_to=rq_, correlation_id=str(i)))
        while not box: cc.process_data_events(0.0005)
        cch.basic_cancel(tag); cch.queue_delete(rq_); ts.append(ms(t0))
    cc.close(); return ts
def rpc_reuse(K=2000):
    cc = n.conn(); cch = cc.channel(); rq_ = cch.queue_declare('', exclusive=True).method.queue; box = []
    cch.basic_consume(rq_, lambda chn, m, p, b: box.append(p.correlation_id), auto_ack=True); ts = []
    for i in range(K):
        t0 = time.perf_counter(); box.clear()
        cch.basic_publish('', 'rpc_queue', b'x', pika.BasicProperties(reply_to=rq_, correlation_id=str(i)))
        while not box: cc.process_data_events(0.0005)
        ts.append(ms(t0))
    cc.close(); return ts
def rpc_direct(K=2000):
    cc = n.conn(); cch = cc.channel(); box = []
    cch.basic_consume('amq.rabbitmq.reply-to', lambda chn, m, p, b: box.append(p.correlation_id), auto_ack=True); ts = []
    for i in range(K):
        t0 = time.perf_counter(); box.clear()
        cch.basic_publish('', 'rpc_queue', b'x', pika.BasicProperties(reply_to='amq.rabbitmq.reply-to', correlation_id=str(i)))
        while not box: cc.process_data_events(0.0005)
        ts.append(ms(t0))
    cc.close(); return ts
def pct(ts, p): ts = sorted(ts); return ts[int(len(ts) * p)]
for label, fn in (('(a) 每次新建独占队列', rpc_new_queue), ('(b) 复用独占回复队列', rpc_reuse), ('(c) direct reply-to', rpc_direct)):
    ts = fn()
    print(f'  {label:<18} p50 {pct(ts, 0.5):.3f} ms,p99 {pct(ts, 0.99):.3f} ms,{len(ts) / (sum(ts) / 1000):.0f} 次/秒')

print('== 四:服务端不在线时请求会怎样?请求留在 rpc_queue 里,客户端永远等不到回复——RPC 必须自己设超时;给请求加 expiration 也不一定能让它及时消失')
stop3.set(); time.sleep(0.5)
ch0.queue_purge('rpc_queue')
cc = n.conn(); cch = cc.channel(); rq_ = cch.queue_declare('', exclusive=True).method.queue; box = []
cch.basic_consume(rq_, lambda chn, m, p, b: box.append(b), auto_ack=True)
cch.basic_publish('', 'rpc_queue', b'x', pika.BasicProperties(reply_to=rq_, correlation_id='dead'))
cch.basic_publish('', 'rpc_queue', b'y', pika.BasicProperties(reply_to=rq_, correlation_id='dead2', expiration='1000'))
t0 = time.perf_counter()
while not box and time.perf_counter() - t0 < 3: cc.process_data_events(0.05)
time.sleep(0.5)
print(f'  没有服务端,客户端等了 3 秒,收到回复: {len(box)} 条')
print(f'  发了两个请求:一个没有 expiration、一个 expiration=1000 ms。3.5 秒后 rpc_queue 里剩 {n.qinfo("rpc_queue")[0]} 条(没有 expiration 的那条当然还在;带 expiration 的那条排在它后面,出不了队头,也没有被丢掉——这就是第 11 篇的队头阻塞)')
cc.close(); c.close(); px.close(); n.stop()
