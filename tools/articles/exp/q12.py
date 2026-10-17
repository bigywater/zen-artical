import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q12'); reset()
n = Node('q12'); n.start()
c = n.conn(); ch = c.channel()
def mk(name, **a):
    ch.queue_delete(name); qdecl(ch, name, arguments=a)
def getall(q, ack=True):
    r = []
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=ack)
        if mt is None: return r
        r.append((b.decode(), p.priority))

print('== 一:x-max-priority=10 的队列:乱序发 p1、p5、p10、p3、p0、无优先级、p7,basic_get 取出来的顺序')
mk('pq', **{'x-max-priority': 10})
for tag, pr_ in (('a', 1), ('b', 5), ('c', 10), ('d', 3), ('e', 0), ('f', None), ('g', 7), ('h', 5)):
    ch.basic_publish('', 'pq', tag.encode(), pika.BasicProperties(priority=pr_))
print(f'  发送顺序: a(p1) b(p5) c(p10) d(p3) e(p0) f(无) g(p7) h(p5)')
print(f'  取出顺序: {[x[0] + "(p" + str(x[1]) + ")" for x in getall("pq")]}')
print('  同一优先级内保持先进先出(b 在 h 前);没有优先级的消息按 0 算,在 p0 的 e 之后(它们同级、先进先出)')

print('== 二:优先级超过 x-max-priority 会被当成最大值;没设 x-max-priority 的普通队列完全忽略优先级')
mk('pq2', **{'x-max-priority': 5})
for tag, pr_ in (('a', 5), ('b', 200), ('c', 6), ('d', 1)):
    ch.basic_publish('', 'pq2', tag.encode(), pika.BasicProperties(priority=pr_))
print(f'  max-priority=5,发 a(p5) b(p200) c(p6) d(p1):取出 {[x[0] for x in getall("pq2")]}(a、b、c 都按 5 算,先进先出)')
mk('plain')
for tag, pr_ in (('a', 1), ('b', 9), ('c', 5)):
    ch.basic_publish('', 'plain', tag.encode(), pika.BasicProperties(priority=pr_))
print(f'  普通队列发 a(p1) b(p9) c(p5):取出 {[x[0] for x in getall("plain")]}(优先级被忽略)')

print('== 三:优先级只对“还在队列里”的消息起作用:消费者已经预取走的低优先级消息不会被后来的高优先级消息插队')
mk('pq3', **{'x-max-priority': 10})
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=20)
order = []
cch.basic_consume('pq3', lambda chn, m, p, b: (order.append(b.decode()), time.sleep(0.01), chn.basic_ack(m.delivery_tag)))
# 先启动消费者,再持续发低优先级;消费者每条处理 10 ms,预取 20
def feeder():
    f = n.conn(); fch = f.channel()
    for i in range(60): fch.basic_publish('', 'pq3', f'low{i}'.encode(), pika.BasicProperties(priority=1))
    time.sleep(0.01)
    fch.basic_publish('', 'pq3', b'HIGH', pika.BasicProperties(priority=10))
    f.close()
th = threading.Thread(target=feeder); th.start(); th.join()
t0 = time.time()
while time.time() - t0 < 4 and len(order) < 61: cc.process_data_events(0.05)
print(f'  prefetch=20,先发 60 条低优先级(p1)再发 1 条 HIGH(p10);HIGH 是第 {order.index("HIGH") + 1} 个被处理的(共 {len(order)} 条)')
cc.close()
mk('pq3b', **{'x-max-priority': 10})
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=1)
order = []
cch.basic_consume('pq3b', lambda chn, m, p, b: (order.append(b.decode()), time.sleep(0.01), chn.basic_ack(m.delivery_tag)))
th = threading.Thread(target=lambda: (lambda f: ([f.channel().basic_publish('', 'pq3b', f'low{i}'.encode(), pika.BasicProperties(priority=1)) for i in range(60)], time.sleep(0.01), f.channel().basic_publish('', 'pq3b', b'HIGH', pika.BasicProperties(priority=10)), f.close()))(n.conn())); th.start(); th.join()
t0 = time.time()
while time.time() - t0 < 4 and len(order) < 61: cc.process_data_events(0.05)
print(f'  prefetch=1:HIGH 是第 {order.index("HIGH") + 1} 个被处理的(共 {len(order)} 条)')
cc.close()

print('== 四:代价:发布 + 消费 20000 条(随机优先级),x-max-priority = 不设 / 10 / 255;3 轮取中位数')
def bench(maxp, k=20000):
    a = {'x-max-priority': maxp} if maxp else {}
    mk('pb', **a)
    pris = [random.randint(0, maxp or 1) for _ in range(k)]
    t0 = time.perf_counter()
    for i in range(k): ch.basic_publish('', 'pb', b'x' * 100, pika.BasicProperties(priority=pris[i] if maxp else None))
    t_pub = ms(t0)
    t0 = time.perf_counter(); cnt = 0
    while True:
        mt, p, b = ch.basic_get('pb', auto_ack=True)
        if mt is None: break
        cnt += 1
    return t_pub, ms(t0)
random.seed(1)
res = {}
for maxp in (0, 10, 255):
    xs = [bench(maxp) for _ in range(3)]
    res[maxp] = (median(x[0] for x in xs), median(x[1] for x in xs))
for maxp, (a, b) in res.items(): print(f'  x-max-priority={maxp or "不设":<4}: 发布 20000 条 {a:.0f} ms,basic_get 取完 {b:.0f} ms')

print('== 五:队列里有多少“内部子队列”?x-max-priority=10 的队列在空与有消息时的内存(rabbitmqctl list_queues memory)')
for maxp in (0, 10, 255):
    mk(f'mem{maxp}', **({'x-max-priority': maxp} if maxp else {}))
time.sleep(1)
m = n.qinfo(None, ('memory',))
print('  空队列内存(字节): ' + ', '.join(f'{"不设" if k == "mem0" else "max-priority=" + k[3:]}: {v[0]}' for k, v in sorted(m.items()) if k.startswith('mem')))

print('== 六:quorum 队列的优先级:4.3.6 里按完整的 0~255 排序,不是两档;但声明时不能带 x-max-priority(406)')
try:
    ch2 = n.conn().channel(); ch2.queue_declare('qp0', durable=True, arguments={'x-queue-type': 'quorum', 'x-max-priority': 5})
except Exception as e: print(f'  quorum + x-max-priority=5 → {type(e).__name__}: (406, "PRECONDITION_FAILED - invalid arg \'x-max-priority\' for queue … of queue type rabbit_quorum_queue")')
ch.queue_delete('qp'); qdecl(ch, 'qp', arguments={'x-queue-type': 'quorum'})
pris = [1, 9, 3, 5, 2, 10, 0, 7, 4, 6, 8, 12, 200, 5, 5]
for i, pr_ in enumerate(pris): ch.basic_publish('', 'qp', str(i).encode(), pika.BasicProperties(priority=pr_))
time.sleep(0.5)
print(f'  依次发优先级 {pris}')
print(f'  quorum 队列取出(序号:优先级): {[x[0] + ":" + str(x[1]) for x in getall("qp")]}')
print('  优先级从大到小排好,同级(三个 5)保持先进先出(序号 3、13、14);200 没有被截成 255 以内的某个值(quorum 没有 x-max-priority 这个上限)')
c.close(); n.stop()
