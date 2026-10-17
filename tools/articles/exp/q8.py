import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q8'); reset()
n = Node('q8'); n.start()
c = n.conn(); ch = c.channel()
def fill(q, k, size=100):
    qdecl(ch, q); ch.queue_purge(q)
    body = b'x' * size
    for i in range(k): ch.basic_publish('', q, body, pika.BasicProperties(delivery_mode=2))
    ch.queue_declare(q, passive=True)
def ready_unacked(q): time.sleep(0.2); return n.qinfo(q)

print('== 一:prefetch 的含义:broker 最多给一个消费者推多少条“还没 ack”的消息。prefetch=5、队列里 20 条,消费者收到就不 ack')
fill('p1', 20)
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=5)
got = []
cch.basic_consume('p1', lambda chn, m, p, b: got.append(m.delivery_tag))
for _ in range(5): cc.process_data_events(0.1)
print(f'  消费者收到了 {len(got)} 条;(ready, unacked) = {ready_unacked("p1")}')
cch.basic_ack(got[0])
for _ in range(5): cc.process_data_events(0.1)
print(f'  ack 了第 1 条之后又收到 {len(got) - 5} 条(总共 {len(got)});(ready, unacked) = {ready_unacked("p1")}')
cch.basic_ack(got[-1], multiple=True)
for _ in range(5): cc.process_data_events(0.1)
print(f'  再 ack 到最后一条(multiple=True)之后共收到 {len(got)} 条;(ready, unacked) = {ready_unacked("p1")}')
n.sh('list_channels prefetch_count messages_unacknowledged consumer_count')
cc.close()

print('== 二:两个消费者在同一个 channel 上,basic.qos 的 global 标志不同:global=False 是每个消费者各 5;global=True 理论上是整个 channel 共享 5——4.3.6 默认把 global_qos 列为被拒绝的废弃特性')
import json as _json
dep = _json.loads(n.ctl_raw('--quiet', 'list_deprecated_features', '--formatter', 'json').stdout)
print('  list_deprecated_features(摘取): ' + ', '.join(f"{d['name']}={d['deprecation_phase']}/{d['state']}" for d in dep if d['name'] in ('global_qos', 'transient_nonexcl_queues', 'classic_queue_mirroring')))
n2 = Node('q8g', conf=['deprecated_features.permit.global_qos = true']); n2.start()
def two_consumers(node, glob):
    qdecl(node.conn().channel(), 'p2')
    cc = node.conn(); cch = cc.channel(); cch.queue_purge('p2')
    for i in range(40): cch.basic_publish('', 'p2', b'x', pika.BasicProperties(delivery_mode=2))
    cch.queue_declare('p2', passive=True)
    cch.basic_qos(prefetch_count=5, global_qos=glob)
    g = {'a': 0, 'b': 0}
    cch.basic_consume('p2', lambda chn, m, p, b: g.__setitem__('a', g['a'] + 1), consumer_tag='a')
    cch.basic_consume('p2', lambda chn, m, p, b: g.__setitem__('b', g['b'] + 1), consumer_tag='b')
    for _ in range(5): cc.process_data_events(0.1)
    time.sleep(0.2); st = node.qinfo('p2'); cc.close(); time.sleep(0.3)
    return g, st
for label, node, glob in (('默认配置 global=False', n, False), ('默认配置 global=True', n, True), ('打开 permit.global_qos 后 global=True', n2, True)):
    g, st = two_consumers(node, glob)
    print(f'  {label}: 两个消费者各收到 {g},合计 {g["a"] + g["b"]};(ready, unacked) = {st}')
print('  默认配置下 global=True 没有报错,效果和 global=False 一样(每个消费者各 5);只有显式打开 permit.global_qos,两个消费者才共享 5')
n2.stop()

print('== 三:自动确认(no_ack)的消费者不受 prefetch 限制:设了 prefetch=5 也会一口气被推完')
fill('p3', 1000)
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=5)
cnt = [0]
cch.basic_consume('p3', lambda chn, m, p, b: cnt.__setitem__(0, cnt[0] + 1), auto_ack=True)
for _ in range(10): cc.process_data_events(0.1)
print(f'  prefetch=5 + auto_ack=True:收到 {cnt[0]} 条;(ready, unacked) = {ready_unacked("p3")}')
cc.close()

print('== 四:prefetch 与吞吐(loopback,几乎没有网络延迟):预先放 20000 条 100 字节消息,消费者每条处理完立刻 ack;各 prefetch 值跑 3 次取中位数')
N = 20000
def consume_all(port, prefetch, n_msgs=N, multiple=False):
    cc = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', port)); cch = cc.channel()
    cch.basic_qos(prefetch_count=prefetch)
    cnt = [0]
    def cb(chn, m, p, b):
        cnt[0] += 1; chn.basic_ack(m.delivery_tag)
    t0 = time.perf_counter()
    cch.basic_consume('pb', cb)
    while cnt[0] < n_msgs: cc.process_data_events(1)
    e = ms(t0); cc.close(); return e
def bench(port, prefetches, k=N, rounds=3):
    r = {}
    for pf in prefetches:
        ts = []
        for _ in range(rounds):
            fill('pb', k); ts.append(consume_all(port, pf, k))
        r[pf] = median(ts)
    return r
res = bench(n.amqp, [1, 10, 100, 1000, 0])
print('  prefetch    耗时      吞吐')
for pf, v in res.items(): print(f'  {pf if pf else "0(无限)":<10}{v:>7.0f} ms  {N / v * 1000:>7.0f} 条/秒')

print('== 五:加上网络延迟后差别才真正显出来:经过代理,每个方向加 5 ms(往返约 10 ms),消费 2000 条;每个 prefetch 值 1 次(prefetch=1 很慢)')
px = Proxy(n.amqp); px.delay = 0.005
K = 2000
r5 = {}
for pf in (1, 10, 100, 1000):
    fill('pb', K); r5[pf] = consume_all(px.port, pf, K)
print('  prefetch    耗时      吞吐        理论上限(= prefetch ÷ 往返 10 ms)')
for pf, v in r5.items(): print(f'  {pf:<10}{v:>8.0f} ms  {K / v * 1000:>7.0f} 条/秒   {pf / 0.010:>8.0f} 条/秒')
px.close()

print('== 六:prefetch 很大(或 0)时,消费者崩溃会让一大批消息同时回到队列:prefetch=1000、队列 5000 条,消费者收到后不 ack 就断开')
fill('p6', 5000)
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=1000)
cch.basic_consume('p6', lambda chn, m, p, b: None)
for _ in range(10): cc.process_data_events(0.1)
print(f'  消费者在线时 (ready, unacked) = {ready_unacked("p6")}')
cc.close(); time.sleep(0.3)
print(f'  消费者断开之后 (ready, unacked) = {ready_unacked("p6")}')
red = 0
for i in range(5000):
    mt, p_, b_ = ch.basic_get('p6', auto_ack=True)
    if mt is None: break
    red += bool(mt.redelivered)
print(f'  把 5000 条全取出来,其中 redelivered=True 的有 {red} 条(正好是被推给那个崩溃消费者的 1000 条)')
c.close(); n.stop()
