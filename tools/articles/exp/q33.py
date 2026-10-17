import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q33'); reset()
n = Node('q33'); n.start()
c = n.conn(); ch = c.channel()
def mk(q, **a):
    ch.queue_delete(q); ch.queue_declare(q, durable=True, arguments=a)
def ready(q): return (n.qinfo(q) or (None,))[0]
def drain(q):
    r = []
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=True)
        if mt is None: return r
        r.append(b.decode())

print('== 一:消息 TTL 到点就从 ready 里消失吗?10 条消息 expiration=1000 ms,每 0.25 s 看一次队列里的条数')
mk('t1')
for i in range(10): ch.basic_publish('', 't1', f'm{i}'.encode(), pika.BasicProperties(expiration='1000'))
t0 = time.perf_counter(); tr = []
while time.perf_counter() - t0 < 2.0: tr.append((round(time.perf_counter() - t0, 2), ready('t1'))); time.sleep(0.25)
print(f'  (秒, ready): {tr}')

print('== 二:队头阻塞造成的“僵尸消息”:1 条没有 expiration 的消息排在队头,后面 10 条 expiration=500 ms;3 秒后队列里还有几条?消费者能收到几条?')
mk('t2'); ch.basic_publish('', 't2', b'head-no-ttl')
for i in range(10): ch.basic_publish('', 't2', f'z{i}'.encode(), pika.BasicProperties(expiration='500'))
time.sleep(3)
print(f'  3 秒后 ready = {ready("t2")}(11 条:队头没有过期,后面已经过期的 10 条不会被清掉)')
got = drain('t2')
print(f'  basic_get 取空,实际拿到: {got}(已过期的 10 条在到达队头时被丢掉,消费者看不到)')

print('== 三:队列 TTL 和消息 TTL 同时设:取较小的。x-message-ttl=2000 的队列,消息 expiration=500 / 5000 ms,各发一条,看它们各自何时消失')
mk('t3', **{'x-message-ttl': 2000})
ch.basic_publish('', 't3', b'exp500', pika.BasicProperties(expiration='500'))
t0 = time.perf_counter(); tr = []
while time.perf_counter() - t0 < 3.0: tr.append((round(time.perf_counter() - t0, 1), ready('t3'))); time.sleep(0.5)
ch.basic_publish('', 't3', b'exp5000', pika.BasicProperties(expiration='5000'))
t1_ = time.perf_counter(); tr2 = []
while time.perf_counter() - t1_ < 3.0: tr2.append((round(time.perf_counter() - t1_, 1), ready('t3'))); time.sleep(0.5)
print(f'  exp500(队列 TTL 2000):{tr}')
print(f'  exp5000(队列 TTL 2000):{tr2}——较小的 2000 ms 生效')

print('== 四:expiration=0 的特殊含义:只有消息能立刻投给消费者才保留。没有消费者时发布 → 立即丢;有一个空闲消费者时发布 → 收到')
mk('t4')
ch.basic_publish('', 't4', b'no-consumer', pika.BasicProperties(expiration='0')); time.sleep(0.3)
print(f'  无消费者 + expiration=0:队列里 ready = {ready("t4")}')
cc = n.conn(); cch = cc.channel(); got = []
cch.basic_consume('t4', lambda chn, m, p, b: (got.append(b.decode()), chn.basic_ack(m.delivery_tag)))
cc.process_data_events(0.3)
ch.basic_publish('', 't4', b'with-consumer', pika.BasicProperties(expiration='0'))
for _ in range(10): cc.process_data_events(0.1)
print(f'  有一个空闲消费者 + expiration=0:消费者收到 {got}')
cc.close()

print('== 五:队列 TTL(x-expires):队列在“没人用”之后多久被自动删除。x-expires=3000 ms;“用”包括有消费者、basic_get、重新声明(哪怕是 passive 声明)')
def listed(q): return q in n.ctl('list_queues', 'name')      # 只读元数据,不会碰队列进程
mk('t5', **{'x-expires': 3000})
t0 = time.perf_counter(); r = []
while time.perf_counter() - t0 < 5.0:
    r.append((round(time.perf_counter() - t0, 1), listed('t5'))); time.sleep(0.5)
print(f'  声明后什么都不做,用 rabbitmqctl list_queues(不算“使用”)每 0.5 s 看一次: {r}')
mk('t5b', **{'x-expires': 3000}); t0 = time.perf_counter(); r2 = []
for s_ in (1, 2, 3, 4, 5, 6):
    while time.perf_counter() - t0 < s_: time.sleep(0.05)
    ch2 = n.conn().channel(); ch2.queue_declare('t5b', passive=True, durable=True); r2.append((s_, listed('t5b')))
print(f'  每秒做一次 passive 声明: {r2}——passive 声明也重置了计时,队列一直在')
mk('t5c', **{'x-expires': 3000}); cc = n.conn(); cch = cc.channel(); cch.basic_consume('t5c', lambda *a: None); time.sleep(5)
print(f'  有一个消费者连着时,5 秒后队列还在: {listed("t5c")}')
cc.close(); t0 = time.perf_counter(); r3 = []
while time.perf_counter() - t0 < 5.0:
    r3.append((round(time.perf_counter() - t0, 1), listed('t5c'))); time.sleep(0.5)
print(f'  消费者断开后,每 0.5 s 看一次: {r3}')

print('== 六:TTL 在 broker 重启后:持久化消息 expiration=8000 ms,发布后 2 秒关闭 broker,停 8 秒再启动(已超过 TTL),消息还在吗')
mk('t6')
ch.basic_publish('', 't6', b'persist', pika.BasicProperties(expiration='8000', delivery_mode=2))
time.sleep(2); c.close(); n.stop(); time.sleep(8); n.start()
time.sleep(1)
print(f'  重启后队列 t6 的 ready = {ready("t6")}')
n.stop()
