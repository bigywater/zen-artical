import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
from confluent_kafka import Producer, Consumer, TopicPartition
tee('q34'); reset()
n = Node('q34'); n.start()
k = KafkaNode('q34k'); k.start()
BS = f'127.0.0.1:{k.port}'
c = n.conn(); ch = c.channel()
def ktopic(name): 
    k.topics('--delete', '--topic', name); r = k.topics('--create', '--topic', name, '--partitions', '1', '--replication-factor', '1'); time.sleep(0.5)

print('== 一:对比的前提:同一台机器上各起一个单节点 broker——RabbitMQ 4.3.6(经典队列,持久化消息)与 Kafka 4.3.1(KRaft,1 个分区、1 副本);客户端库不同(pika 是纯 Python,confluent-kafka 是 C 实现的 librdkafka),所以绝对数字主要反映“客户端 + 默认批量策略”,只能看数量级和趋势')
print('  RabbitMQ: ' + n.ctl('version') + ';Kafka: ' + subprocess.run([f'{KAFKA_BIN}/kafka-topics', '--version'], capture_output=True, text=True).stdout.strip().splitlines()[-1])

print('== 二:发布吞吐:100000 条 100 字节的消息,RabbitMQ 用异步 confirm(在途 1000,持久化),Kafka 用 acks=all(单副本)。各 3 轮中位数')
N = 100000; body = b'x' * 100
ch.queue_declare('cmp', durable=True)
def rmq_pub():
    ch.queue_purge('cmp'); return async_publish(n.amqp, 'cmp', N, 1000, body, True)[0]
def kafka_pub(linger):
    ktopic('cmp'); p = Producer({'bootstrap.servers': BS, 'acks': 'all', 'linger.ms': linger, 'queue.buffering.max.messages': 1000000})
    t0 = time.perf_counter()
    for i in range(N):
        while True:
            try: p.produce('cmp', body); break
            except BufferError: p.poll(0.01)
        if i % 10000 == 0: p.poll(0)
    p.flush(60); return ms(t0)
r1 = median([rmq_pub() for _ in range(3)])
k1 = median([kafka_pub(5) for _ in range(3)]); k0 = median([kafka_pub(0) for _ in range(3)])
print(f'  RabbitMQ 异步 confirm: {r1:.0f} ms  {N / r1 * 1000:.0f} 条/秒')
print(f'  Kafka acks=all linger.ms=5: {k1:.0f} ms  {N / k1 * 1000:.0f} 条/秒')
print(f'  Kafka acks=all linger.ms=0: {k0:.0f} ms  {N / k0 * 1000:.0f} 条/秒')

print('== 三:端到端延迟:每秒 500 条的低速率下,从 produce 到消费者回调/poll 返回的延迟,各 2000 条(消息里放发送时刻),p50 / p99')
def rmq_lat(K=2000):
    ch.queue_purge('cmp'); cc = n.conn(); cch = cc.channel(); cch.confirm_delivery(); lat = []
    pc = n.conn(); pch = pc.channel(); pch.confirm_delivery()
    cch.basic_consume('cmp', lambda chn, m, p, b: (lat.append((time.perf_counter() - float(b)) * 1000), chn.basic_ack(m.delivery_tag)))
    t0 = time.perf_counter()
    for i in range(K):
        while time.perf_counter() - t0 < i / 500: cc.process_data_events(0.0005)
        pch.basic_publish('', 'cmp', repr(time.perf_counter()).encode(), pika.BasicProperties(delivery_mode=2))
    t1 = time.perf_counter()
    while len(lat) < K and time.perf_counter() - t1 < 10: cc.process_data_events(0.01)
    cc.close(); pc.close(); lat.sort(); return lat[len(lat) // 2], lat[int(len(lat) * 0.99)]
def kafka_lat(K=2000):
    ktopic('cmp'); p = Producer({'bootstrap.servers': BS, 'acks': 'all', 'linger.ms': 0})
    cons = Consumer({'bootstrap.servers': BS, 'group.id': 'lat' + str(time.time()), 'auto.offset.reset': 'latest', 'fetch.wait.max.ms': 5, 'fetch.min.bytes': 1})
    cons.subscribe(['cmp']); 
    for _ in range(40):
        cons.poll(0.25)
        if cons.assignment(): break
    time.sleep(1); lat = []; t0 = time.perf_counter(); sent = 0
    while len(lat) < K and time.perf_counter() - t0 < K / 500 + 15:
        while sent < K and time.perf_counter() - t0 >= sent / 500:
            p.produce('cmp', repr(time.perf_counter()).encode()); sent += 1
        p.poll(0)
        m = cons.poll(0.001)
        if m is not None and not m.error(): lat.append((time.perf_counter() - float(m.value())) * 1000)
    cons.close(); lat.sort(); return lat[len(lat) // 2], lat[int(len(lat) * 0.99)]
a = rmq_lat(); b = kafka_lat()
print(f'  RabbitMQ(推送 + confirm):p50 {a[0]:.2f} ms,p99 {a[1]:.2f} ms')
print(f'  Kafka(acks=all,linger.ms=0,拉取):p50 {b[0]:.2f} ms,p99 {b[1]:.2f} ms')

print('== 四:一份数据给 3 个独立的下游:RabbitMQ 要 fanout exchange + 3 个队列(存 3 份),Kafka 是 1 个 topic、3 个 consumer group 各读各的(存 1 份)。写入 50000 条 1 KB 后的数据目录大小')
ch.exchange_declare('fan', 'fanout', durable=True)
for i in range(3): ch.queue_delete(f'fq{i}'); ch.queue_declare(f'fq{i}', durable=True); ch.queue_bind(f'fq{i}', 'fan', '')
d0 = n.du()
for i in range(50000): ch.basic_publish('fan', '', b'x' * 1024, pika.BasicProperties(delivery_mode=2))
for i in range(3): ch.queue_declare(f'fq{i}', passive=True)
time.sleep(2)
rd = n.du() - d0
ktopic('fanout'); kd0 = k.du()
p = Producer({'bootstrap.servers': BS, 'acks': 'all', 'linger.ms': 5})
for i in range(50000):
    while True:
        try: p.produce('fanout', b'x' * 1024); break
        except BufferError: p.poll(0.01)
p.flush(60); time.sleep(2)
kd = k.du() - kd0
print(f'  RabbitMQ(3 个队列各存一份): 数据目录增长 {rd / 1024:.0f} MiB')
print(f'  Kafka(1 个 topic,3 个 group 共读): 数据目录增长 {kd / 1024:.0f} MiB')

print('== 五:读完能不能再读?20000 条消息消费完(RabbitMQ 手动 ack,Kafka 一个 group 读完)之后,从头再读一遍,各能读到多少条')
ch.queue_purge('cmp')
async_publish(n.amqp, 'cmp', 20000, 1000, body, True)
def rmq_read():
    cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=500); got = [0]
    cch.basic_consume('cmp', lambda chn, m, p, b: (got.__setitem__(0, got[0] + 1), chn.basic_ack(m.delivery_tag)))
    t0 = time.time()
    while time.time() - t0 < 3: cc.process_data_events(0.05)
    cc.close(); return got[0]
ktopic('cmp'); p = Producer({'bootstrap.servers': BS, 'acks': 'all'})
for i in range(20000):
    while True:
        try: p.produce('cmp', body); break
        except BufferError: p.poll(0.01)
p.flush(60)
def kafka_read(group):
    cons = Consumer({'bootstrap.servers': BS, 'group.id': group, 'auto.offset.reset': 'earliest', 'enable.auto.commit': False}); cons.subscribe(['cmp']); got = 0; t0 = time.time()
    while time.time() - t0 < 6:
        m = cons.poll(0.2)
        if m is not None and not m.error(): got += 1
        if got >= 20000: break
    cons.close(); return got
a1 = rmq_read(); a2 = rmq_read()
b1 = kafka_read('first'); b2 = kafka_read('second-group')
print(f'  RabbitMQ 经典队列:第一次读 {a1} 条,第二次读 {a2} 条(消息被 ack 之后就删除了)')
print(f'  Kafka:第一个 group 读 {b1} 条,另一个 group(或重置 offset)再从头读 {b2} 条(日志保留着,读取不删除)')
c.close(); n.stop(); k.stop()
