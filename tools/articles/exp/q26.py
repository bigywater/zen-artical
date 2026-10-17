import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q26'); reset()
n = Node('q26'); n.start()
c = n.conn(); ch = c.channel()

def run(q, nconsumers, N=200, work=0.01, prefetch=1, requeue_some=False, args=None):
    """N 条消息(序号 0..N-1,按顺序发布)给 nconsumers 个并发消费者;返回各消息被处理完成的顺序 [(序号, 消费者)]"""
    ch.queue_delete(q); ch.queue_declare(q, durable=True, arguments=args); 
    for i in range(N): ch.basic_publish('', q, str(i).encode())
    ch.queue_declare(q, passive=True)
    done = []; lock = threading.Lock(); stop = threading.Event(); first = {}
    def worker(name):
        cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=prefetch)
        def cb(chn, m, p, b):
            i = int(b)
            time.sleep(work * (1 + (i * 7919 % 5)))      # 处理时间 1~5 倍不等(确定性的"随机"),模拟真实任务耗时不一
            with lock: done.append((i, name))
            chn.basic_ack(m.delivery_tag)
        cch.basic_consume(q, cb)
        while not stop.is_set(): cc.process_data_events(0.02)
        cc.close()
    ths = [threading.Thread(target=worker, args=(f'c{k}',), daemon=True) for k in range(nconsumers)]
    for t in ths: t.start()
    t0 = time.perf_counter()
    while len(done) < N and time.perf_counter() - t0 < 60: time.sleep(0.02)
    stop.set(); [t.join(3) for t in ths]
    return done
def inversions(order):
    seq = [i for i, _ in order]
    return sum(1 for a, b in zip(seq, seq[1:]) if b < a), sum(1 for k in range(len(seq)) for j in range(k + 1, len(seq)) if seq[j] < seq[k])

print('== 一:单个队列、单个消费者:严格按发布顺序处理(同一队列里消息本身是先进先出的)')
d = run('o1', 1, 100)
print(f'  100 条,1 个消费者:处理完成的顺序前 15 个 = {[i for i, _ in d][:15]};相邻逆序对数 {inversions(d)[0]},总逆序对数 {inversions(d)[1]}')

print('== 二:多个消费者并发处理同一个队列:消息按顺序“投递”,但处理时间不同,完成顺序就乱了(prefetch=1,200 条,处理耗时 10~50 ms)')
rows = []
for k in (1, 2, 4, 8):
    d = run(f'o2.{k}', k, 200)
    rows.append((k, inversions(d)[0], inversions(d)[1], [i for i, _ in d][:12]))
print('  消费者数  相邻逆序  总逆序对  完成顺序(前 12 个)')
for k, a, b, f in rows: print(f'  {k:<8}{a:>8}{b:>10}  {f}')

print('== 三:顺序可能被打乱的另一个原因:消息被 nack 并 requeue 后会重新投递。1 个消费者,每第 10 条先 nack(requeue)一次再处理')
ch.queue_delete('o3'); ch.queue_declare('o3', durable=True)
for i in range(30): ch.basic_publish('', 'o3', str(i).encode())
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=1); order = []; nacked = set()
def cb3(chn, m, p, b):
    i = int(b)
    if i % 10 == 5 and i not in nacked: nacked.add(i); chn.basic_nack(m.delivery_tag, requeue=True); return
    order.append(i); chn.basic_ack(m.delivery_tag)
cch.basic_consume('o3', cb3)
t0 = time.time()
while len(order) < 30 and time.time() - t0 < 20: cc.process_data_events(0.05)
print(f'  处理顺序: {order}')
print('  (prefetch=1 的单个消费者上 requeue 的消息被放回队首,所以顺序没有被打乱;下面用 prefetch=10 看区别)')
cc.close()
ch.queue_delete('o3b'); ch.queue_declare('o3b', durable=True)
for i in range(30): ch.basic_publish('', 'o3b', str(i).encode())
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=10); order = []; nacked = set()
def cb3b(chn, m, p, b):
    i = int(b)
    if i % 10 == 5 and i not in nacked: nacked.add(i); chn.basic_nack(m.delivery_tag, requeue=True); return
    order.append(i); chn.basic_ack(m.delivery_tag)
cch.basic_consume('o3b', cb3b)
t0 = time.time()
while len(order) < 30 and time.time() - t0 < 20: cc.process_data_events(0.05)
print(f'  prefetch=10 的处理顺序: {order}')
cc.close()

print('== 四:要保序就要“同一类消息交给同一个消费者”:按 key 分区——8 个队列(每个 1 个消费者),发布时用 hash(key) 选队列;同一个 key 内保持顺序,不同 key 之间不保证。100 个账户,每个账户 10 条消息(共 1000 条),4 个并发消费者各管 2 个队列')
import zlib
ch.exchange_declare('part.x', 'direct', durable=True)
P = 8
for p_ in range(P):
    ch.queue_delete(f'part.{p_}'); ch.queue_declare(f'part.{p_}', durable=True); ch.queue_bind(f'part.{p_}', 'part.x', str(p_))
msgs = []
for seq in range(10):
    for acct in range(100):
        msgs.append((acct, seq))
for acct, seq in msgs:
    ch.basic_publish('part.x', str(zlib.crc32(str(acct).encode()) % P), f'{acct}:{seq}'.encode())
for p_ in range(P): ch.queue_declare(f'part.{p_}', passive=True)
got = {}; lock = threading.Lock(); stop = threading.Event(); total = [0]
def pworker(qs):
    cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=1)
    def cb(chn, m, p, b):
        a, s = map(int, b.decode().split(':')); time.sleep(0.001 * (1 + (a * 31 % 5)))
        with lock: got.setdefault(a, []).append(s); total[0] += 1
        chn.basic_ack(m.delivery_tag)
    for q in qs: cch.basic_consume(q, cb)
    while not stop.is_set(): cc.process_data_events(0.02)
    cc.close()
ths = [threading.Thread(target=pworker, args=([f'part.{2 * k}', f'part.{2 * k + 1}'],), daemon=True) for k in range(4)]
for t in ths: t.start()
t0 = time.time()
while total[0] < 1000 and time.time() - t0 < 60: time.sleep(0.05)
stop.set(); [t.join(3) for t in ths]
bad = sum(1 for a, s in got.items() if s != sorted(s))
print(f'  处理了 {total[0]} 条;100 个账户里,每个账户内部顺序乱掉的有 {bad} 个(按 key 分区后,同一个账户总是进同一个队列、同一个消费者)')
print(f'  这 100 个账户被分到 8 个队列里的分布: {sorted(__import__("collections").Counter(zlib.crc32(str(a).encode()) % P for a in range(100)).values())}')
c.close(); n.stop()
