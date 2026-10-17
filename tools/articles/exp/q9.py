import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q9'); reset()
n = Node('q9'); n.start()
c = n.conn(); ch = c.channel()
def fill(q, k, **kw):
    qdecl(ch, q, **kw); ch.queue_purge(q)
    for i in range(k): ch.basic_publish('', q, str(i).encode(), pika.BasicProperties(delivery_mode=2))
    ch.queue_declare(q, passive=True)

def run_consumers(q, specs, total, prefetch, timeout=60, stuck=(), probe=None, feeder=None):
    """specs: [(name, 处理耗时秒, consumer_arguments)];每个消费者一个线程一个连接;返回 ({name: 条数}, 总耗时 s, 顺序列表)"""
    counts = {s[0]: 0 for s in specs}; uniq = {s[0]: set() for s in specs}; order = []; lock = threading.Lock(); stop = threading.Event()
    done_total = [0]
    def worker(name, dur, args):
        cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=prefetch)
        def cb(chn, m, p, b):
            if name in stuck:
                with lock: counts[name] += 1; order.append(name)
                return     # 卡住:收到后既不处理也不 ack
            time.sleep(dur)
            chn.basic_ack(m.delivery_tag)
            with lock:
                uniq[name].add(b); counts[name] += 1; order.append(name); done_total[0] += 1
        cch.basic_consume(q, cb, arguments=args, consumer_tag=name)
        while not stop.is_set():
            cc.process_data_events(0.05)
        try: cc.close()
        except Exception: pass
    ths = [threading.Thread(target=worker, args=s, daemon=True) for s in specs]
    t0 = time.perf_counter()
    for t in ths: t.start()
    while done_total[0] < total and time.perf_counter() - t0 < timeout: time.sleep(0.02)
    el = time.perf_counter() - t0
    pr_ = probe() if probe else None
    with lock: snap = dict(counts); usnap = {k: len(v) for k, v in uniq.items()}   # 在停止消费者之前取快照:停止时卡住的消息会回队列被 A 重新拿走
    stop.set()
    for t in ths: t.join(5)
    run_consumers.uniq = usnap
    return (snap, el, order, pr_) if probe else (snap, el, order)

print('== 一:默认的分发顺序是轮询:2 个速度相同的消费者(各 5 ms 处理一条),prefetch=1,队列里 40 条,看前 12 条是怎么交替投递的')
fill('f1', 40)
cnt, el, order = run_consumers('f1', [('A', 0.005, None), ('B', 0.005, None)], 40, 1)
print(f'  投递给谁(按完成顺序前 12 条): {"".join(order[:12])};总计 {cnt}')

print('== 二:一快一慢(A 每条 2 ms,B 每条 20 ms),600 条:不同 prefetch 下谁拿走多少、多久处理完')
rows = []
for pf in (0, 100, 10, 1):
    fill('f2', 600)
    cnt, el, _ = run_consumers('f2', [('A快', 0.002, None), ('B慢', 0.02, None)], 600, pf)
    rows.append((pf, cnt['A快'], cnt['B慢'], el))
print('  prefetch     A 快(2 ms)  B 慢(20 ms)  总耗时')
for pf, a, b, el in rows: print(f'  {pf if pf else "0(无限)":<10}{a:>10}{b:>12}{el:>10.2f} s')
print(f'  理想情况(按速度比例分,没有空转)总耗时 ≈ 600 ÷ (500 + 50) 条/秒 = {600 / 550:.2f} s;全部均分时总耗时 ≈ 300 × 20 ms = {300 * 0.02:.1f} s')

print('== 三:一个卡住的消费者(收到消息不处理也不 ack)会扣住多少条?prefetch 越大扣得越多;另一个正常的消费者(A,2 ms)继续处理。8 秒后读队列状态')
rows = []
for pf in (1, 10, 100):
    qn = f'f3.{pf}'; fill(qn, 500)    # 每一轮用新队列:上一轮卡住的消费者断开后消息会异步回队列,不能和新一轮混在一起
    cnt, el, _, info = run_consumers(qn, [('A', 0.002, None), ('卡住', 0, None)], 500, pf, timeout=8, stuck=('卡住',), probe=lambda: n.qinfo(qn))
    rows.append((pf, run_consumers.uniq['A'], info))
    time.sleep(0.3)
print('  prefetch   A 处理完(按消息去重)   队列 (ready, unacked) = 卡住的消费者扣住的')
for pf, a, info in rows: print(f'  {pf:<10}{a:>10}{str(info):>30}')
print('  卡住的消费者断开(或超时)前,它手里的消息谁也拿不到;prefetch=1 时最多只有 1 条')

print('== 四:消费者优先级 x-priority:两个消费者(每条 20 ms,容量各约 50 条/秒,prefetch=1)订阅同一队列,A 优先级 10、B 优先级 0;按不同速率发布 200 条,看消息怎么在两个消费者之间溢出')
def paced(rate, k=200):
    qdecl(ch, 'f4'); ch.queue_purge('f4')
    def feeder():
        cc = n.conn(); cch = cc.channel(); t0 = time.perf_counter()
        for i in range(k):
            while time.perf_counter() - t0 < i / rate: time.sleep(0.0005)
            cch.basic_publish('', 'f4', b'x')
        cc.close()
    return feeder
rows = []
for rate in (20, 45, 80, 120):
    ft = threading.Thread(target=paced(rate), daemon=True)
    ft.start()
    cnt, el, _ = run_consumers('f4', [('A高', 0.02, {'x-priority': 10}), ('B低', 0.02, {'x-priority': 0})], 200, 1, timeout=30)
    ft.join(); rows.append((rate, cnt['A高'], cnt['B低']))
    time.sleep(0.3)
print('  发布速率(条/秒)   A 优先级 10   B 优先级 0')
for rate, a, b in rows: print(f'  {rate:<16}{a:>10}{b:>12}')
print('  速率低于 A 一个人的处理能力(约 50 条/秒)时,消息几乎都给 A;速率更高时,有些消息到达的瞬间 A 还在处理上一条(prefetch=1 已满),那些就改给 B')

print('== 五:消费者数量与分发:同一个队列 1、2、4、8 个相同消费者(每条 10 ms),prefetch=1,800 条,总耗时随消费者数的变化')
rows = []
for k in (1, 2, 4, 8):
    fill('f5', 800)
    cnt, el, _ = run_consumers('f5', [(f'c{i}', 0.01, None) for i in range(k)], 800, 1)
    rows.append((k, el, min(cnt.values()), max(cnt.values())))
print('  消费者数   总耗时    每个消费者处理条数(最少~最多)')
for k, el, lo, hi in rows: print(f'  {k:<8}{el:>8.2f} s   {lo}~{hi}')
c.close(); n.stop()
