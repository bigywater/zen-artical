import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q11'); reset()
n = Node('q11'); n.start()
c = n.conn(); ch = c.channel()
ch.exchange_declare('dlx', 'fanout', durable=True)
def mkq(name, qtype='classic', ttl=None, extra=None):
    a = {'x-dead-letter-exchange': 'dlx', 'x-queue-type': qtype}
    if ttl: a['x-message-ttl'] = ttl
    a.update(extra or {})
    ch.queue_delete(name); qdecl(ch, name, arguments=a)
def collector(q='dlq'):
    """后台线程:在死信队列上消费,记下 (收到的相对时间 ms, body)"""
    got = []; t0 = time.perf_counter(); stop = threading.Event()
    def run():
        cc = n.conn(); cch = cc.channel(); cch.basic_consume(q, lambda chn, m, p, b: (got.append((round((time.perf_counter() - t0) * 1000), b.decode())), chn.basic_ack(m.delivery_tag)))
        while not stop.is_set(): cc.process_data_events(0.01)
        cc.close()
    th = threading.Thread(target=run, daemon=True); th.start()
    return got, t0, stop, th
qdecl(ch, 'dlq'); ch.queue_bind('dlq', 'dlx', '')

print('== 一:延迟消息的常见做法:消息发进一个没人消费的队列,靠 TTL 过期后死信到真正的消费队列。队列级 TTL = 1000 ms,发 3 条(间隔 300 ms),看它们到达死信队列的时刻')
ch.queue_purge('dlq'); mkq('delay.q', ttl=1000)
got, t0, stop, th = collector()
sent = []
for i in range(3):
    sent.append(round((time.perf_counter() - t0) * 1000)); ch.basic_publish('', 'delay.q', f'm{i}'.encode()); time.sleep(0.3)
time.sleep(1.5); stop.set(); th.join()
print(f'  发送时刻(ms): {sent}')
print(f'  到达时刻(ms): {[g[0] for g in got]};实际延迟(到达 − 发送): {[g[0] - s for g, s in zip(got, sent)]} ms')

print('== 二:队头阻塞:单条消息的 expiration 不同的话,队列只检查“队头”——先发一条 expiration=3000 ms 的,再发一条 expiration=300 ms 的,后者要等前者过期才死信')
for qtype in ('classic', 'quorum'):
    ch.queue_purge('dlq'); mkq(f'hol.{qtype}', qtype=qtype)
    got, t0, stop, th = collector()
    ch.basic_publish('', f'hol.{qtype}', b'long(3000ms)', pika.BasicProperties(expiration='3000'))
    ch.basic_publish('', f'hol.{qtype}', b'short(300ms)', pika.BasicProperties(expiration='300'))
    time.sleep(4.5); stop.set(); th.join()
    print(f'  {qtype} 队列:到达死信队列的 (时刻 ms, 消息): {got}')

print('== 三:反过来先发短的再发长的就没问题:短的在队头,到点就走;长的随后走')
ch.queue_purge('dlq'); mkq('hol.rev')
got, t0, stop, th = collector()
ch.basic_publish('', 'hol.rev', b'short(300ms)', pika.BasicProperties(expiration='300'))
ch.basic_publish('', 'hol.rev', b'long(3000ms)', pika.BasicProperties(expiration='3000'))
time.sleep(4.0); stop.set(); th.join()
print(f'  到达死信队列的 (时刻 ms, 消息): {got}')

print('== 四:每种延迟一个队列(队列级 TTL)就避开了阻塞:300 ms、1000 ms、2000 ms 三个延迟队列,交错发布,每个队列里是同一个 TTL,先进先出就是先过期')
ch.queue_purge('dlq')
for d in (300, 1000, 2000): mkq(f'delay.{d}', ttl=d)
got, t0, stop, th = collector()
order = [(2000, 'a'), (300, 'b'), (1000, 'c'), (300, 'd'), (2000, 'e'), (1000, 'f')]
for d, tag in order: ch.basic_publish('', f'delay.{d}', f'{tag}({d})'.encode())
time.sleep(3.2); stop.set(); th.join()
print(f'  几乎同时发出,到达死信队列的 (时刻 ms, 消息): {got}')

print('== 五:延迟精度:队列 TTL=500 ms,每隔 50 ms 发一条共 200 条,延迟(到达 − 发送)的分布')
ch.queue_purge('dlq'); mkq('prec.q', ttl=500)
got, t0, stop, th = collector()
sent = {}
for i in range(200):
    sent[f'p{i}'] = (time.perf_counter() - t0) * 1000; ch.basic_publish('', 'prec.q', f'p{i}'.encode()); time.sleep(0.05)
time.sleep(1.5); stop.set(); th.join()
d = sorted(g[0] - sent[g[1]] for g in got)
print(f'  收到 {len(got)} 条;延迟 min {d[0]:.0f} / p50 {d[len(d)//2]:.0f} / p99 {d[int(len(d)*0.99)]:.0f} / max {d[-1]:.0f} ms(目标 500)')

print('== 六:大量延迟消息的内存/磁盘:往 TTL=60 s 的队列塞 50000 条 1 KB 的消息,队列里一直躺着,看 broker 内存与队列状态')
mkq('big.q', ttl=60000)
body = b'x' * 1024
for i in range(50000): ch.basic_publish('', 'big.q', body, pika.BasicProperties(delivery_mode=2))
ch.queue_declare('big.q', passive=True); time.sleep(2)
info = n.qinfo('big.q', ('messages', 'memory', 'message_bytes'))
print(f'  big.q: messages={info[0]} memory={info[1] / 1048576:.1f} MiB message_bytes={info[2] / 1048576:.1f} MiB')
print('  队列进程自己占的内存很小(消息体在磁盘上),但 50000 条、约 48.8 MiB 的数据要在队列里一直躺 60 秒;没有单独的“延迟存储”')
c.close(); n.stop()
