import sys, os, json as _j; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q30'); reset()
A = Node('q30a', plugins=['rabbitmq_shovel', 'rabbitmq_federation']); B = Node('q30b', plugins=['rabbitmq_federation'])
A.start(); B.start()
ca = A.conn(); cha = ca.channel(); cb_ = B.conn(); chb = cb_.channel()
def uri(nd): return f'amqp://guest:guest@127.0.0.1:{nd.amqp}'
def shovel_status():
    out = A.ctl('shovel_status', '--formatter', 'json')
    try: return _j.loads(out[out.index('['):])
    except Exception: return out

print('== 一:动态 shovel:在 A 上定义一个 shovel,把 A 的队列 src 里的消息搬到 B 的队列 dst(参数存在 runtime parameter 里,不用改配置文件)')
cha.queue_declare('src', durable=True); chb.queue_declare('dst', durable=True)
for i in range(1000): cha.basic_publish('', 'src', f'm{i}'.encode(), pika.BasicProperties(delivery_mode=2))
cha.queue_declare('src', passive=True)
defn = {'src-protocol': 'amqp091', 'src-uri': uri(A), 'src-queue': 'src', 'dest-protocol': 'amqp091', 'dest-uri': uri(B), 'dest-queue': 'dst', 'ack-mode': 'on-confirm'}
print('  $ rabbitmqctl set_parameter shovel my-shovel \'{"src-queue":"src","dest-queue":"dst","ack-mode":"on-confirm",…}\'')
out = A.ctl('set_parameter', 'shovel', 'my-shovel', _j.dumps(defn))
time.sleep(3)
st = shovel_status()
print('  shovel_status: ' + (str([{k: v for k, v in x.items() if k in ('name', 'state', 'type', 'source_protocol', 'destination_protocol')} for x in st]) if isinstance(st, list) else st[:200]))
print(f'  A.src 里剩 {A.qinfo("src")[0]} 条,B.dst 里有 {B.qinfo("dst")[0]} 条')

print('== 二:ack-mode 的吞吐:20000 条 100 字节持久化消息从 A.src 搬到 B.dst,三种 ack-mode(on-confirm / on-publish / no-ack),各 3 轮取中位数,计时从 shovel 创建到 B 上收齐')
def shovel_run(mode, N=20000):
    cha.queue_purge('src'); chb.queue_purge('dst'); A.ctl('clear_parameter', 'shovel', 'my-shovel')
    for _ in range(N // 1000): pass
    async_publish(A.amqp, 'src', N, 1000, b'x' * 100, True)
    d = dict(defn); d['ack-mode'] = mode
    t0 = time.perf_counter()
    A.ctl('set_parameter', 'shovel', 'my-shovel', _j.dumps(d))
    while True:
        k = B.qinfo('dst')[0]
        if k >= N: break
        time.sleep(0.02)
        if time.perf_counter() - t0 > 60: break
    e = ms(t0); A.ctl('clear_parameter', 'shovel', 'my-shovel'); return e
res = {m: median([shovel_run(m) for _ in range(3)]) for m in ('on-confirm', 'on-publish', 'no-ack')}
for m, v in res.items(): print(f'  {m:<11}{v:>7.0f} ms  {20000 / v * 1000:>8.0f} 条/秒')

print('== 三:目的端宕机:B 停掉,A 上的 shovel 怎么办?消息留在 A.src 里,shovel 隔 reconnect-delay(默认 5 s)重试;B 回来后继续搬')
cha.queue_purge('src'); chb.queue_purge('dst')
d = dict(defn); d['reconnect-delay'] = 1
A.ctl('set_parameter', 'shovel', 'my-shovel', _j.dumps(d)); time.sleep(2)
B.stop()
for i in range(500): cha.basic_publish('', 'src', f'd{i}'.encode(), pika.BasicProperties(delivery_mode=2))
cha.queue_declare('src', passive=True); time.sleep(3)
st = shovel_status()
print(f'  B 宕机期间 shovel_status: {[(x.get("name"), x.get("state")) for x in st] if isinstance(st, list) else st[:120]};A.src 里积压 {A.qinfo("src")[0]} 条')
B.start(); t0 = time.perf_counter()
chb = B.conn().channel(); chb.queue_declare('dst', durable=True)
while time.perf_counter() - t0 < 60 and B.qinfo('dst')[0] < 500: time.sleep(0.1)
print(f'  B 重新启动并可用之后 {time.perf_counter() - t0:.1f} s,B.dst 里有 {B.qinfo("dst")[0]} 条,A.src 里剩 {A.qinfo("src")[0]} 条')
A.ctl('clear_parameter', 'shovel', 'my-shovel')

print('== 四:交换机联邦(federated exchange):B 是上游,A 是下游。B 上发布到交换机 fx,A 上绑了队列的同名交换机 fx 也能收到(联邦链路把消息复制过来)')
chb.exchange_declare('fx', 'topic', durable=True)
cha.exchange_declare('fx', 'topic', durable=True); cha.queue_declare('fq_local', durable=True); cha.queue_bind('fq_local', 'fx', 'orders.#')
A.ctl('set_parameter', 'federation-upstream', 'up-b', _j.dumps({'uri': uri(B)}))
print('  $ rabbitmqctl set_parameter federation-upstream up-b \'{"uri":"amqp://…B"}\'')
A.ctl('set_policy', 'fed-x', '^fx$', '{"federation-upstream-set":"all"}', '--apply-to', 'exchanges')
print('  $ rabbitmqctl set_policy fed-x "^fx$" \'{"federation-upstream-set":"all"}\' --apply-to exchanges')
time.sleep(4)
for i in range(5): chb.basic_publish('fx', 'orders.new', f'o{i}'.encode())
chb.basic_publish('fx', 'other.x', b'ignored')
time.sleep(1)
print(f'  B 上发布 5 条 orders.new + 1 条 other.x;A.fq_local(绑定 orders.#)里有 {A.qinfo("fq_local")[0]} 条')
out = A.ctl('eval', 'rabbit_federation_status:status().') 
print('  联邦链路状态(eval rabbit_federation_status:status()): ' + out.replace('\n', ' ')[:260])

print('== 五:队列联邦(federated queue):消息留在上游 B,只有 A 上有消费者时才被拉过来')
chb.queue_declare('fqq', durable=True); cha.queue_declare('fqq', durable=True)
for i in range(100): chb.basic_publish('', 'fqq', f'p{i}'.encode(), pika.BasicProperties(delivery_mode=2))
chb.queue_declare('fqq', passive=True)
A.ctl('set_policy', 'fed-q', '^fqq$', '{"federation-upstream-set":"all"}', '--apply-to', 'queues')
time.sleep(4)
print(f'  建好联邦链路、A 上还没有消费者:A.fqq {A.qinfo("fqq")[0]} 条,B.fqq {B.qinfo("fqq")[0]} 条(消息都还在上游)')
got = []
cc = A.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=10)
cch.basic_consume('fqq', lambda chn, m, p, b: (got.append(b.decode()), chn.basic_ack(m.delivery_tag)))
t0 = time.time()
while len(got) < 100 and time.time() - t0 < 30: cc.process_data_events(0.05)
print(f'  A 上开一个消费者后,{time.time() - t0:.1f} s 收到 {len(got)} 条;B.fqq 里剩 {B.qinfo("fqq")[0]} 条(消息是被"搬"过去的,不是复制)')
cc.close(); ca.close(); A.stop(); B.stop()
