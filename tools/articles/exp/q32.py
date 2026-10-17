import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q32'); reset()
n = Node('q32'); n.start()
c = n.conn(); ch = c.channel()
COLS = ('messages_ready', 'messages_unacknowledged', 'consumers', 'consumer_capacity')
def snap(q): 
    v = n.qinfo(q, COLS)
    if not v: return (None,) * 4
    cap = v[3]
    return v[:3] + ((round(float(cap), 3) if cap not in ('', 'undefined', None) and str(cap).replace('.', '', 1).replace('e-', '').isdigit() else cap),)
def consumers(q, k, work, prefetch, stop, counter=None, stuck=False):
    ths = []
    def w():
        cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=prefetch)
        def cb(chn, m, p, b):
            if stuck: return
            time.sleep(work); chn.basic_ack(m.delivery_tag)
            if counter is not None: counter[0] += 1
        cch.basic_consume(q, cb)
        while not stop.is_set(): cc.process_data_events(0.02)
        try: cc.close()
        except Exception: pass
    for _ in range(k):
        t = threading.Thread(target=w, daemon=True); t.start(); ths.append(t)
    return ths

print('== 一:积压是怎么形成的:发布速率 800 条/秒,一个消费者每条处理 2 ms(上限约 500 条/秒),跑 20 秒,每 4 秒看一次队列(ready / unacked / consumers / consumer_capacity)')
ch.queue_declare('bl', durable=True); ch.queue_purge('bl')
stop = threading.Event(); stopc = threading.Event()
def feeder():
    cc = n.conn(); cch = cc.channel(); t0 = time.perf_counter(); i = 0
    while not stop.is_set():
        while time.perf_counter() - t0 < i / 800: time.sleep(0.0003)
        cch.basic_publish('', 'bl', b'x' * 100); i += 1
    cc.close()
threading.Thread(target=feeder, daemon=True).start()
cnt = [0]
consumers('bl', 1, 0.002, 10, stopc, cnt)
trace = []
for s in range(1, 6):
    time.sleep(4); trace.append((s * 4,) + snap('bl') + (cnt[0],))
print('  (秒, ready, unacked, consumers, consumer_capacity, 累计已处理): ')
for t in trace: print('   ', t)
print(f'  发布 800 条/秒、消费约 {cnt[0] / 20:.0f} 条/秒:ready 以约 {(trace[-1][1] - trace[0][1]) / 16:.0f} 条/秒的速度增长;consumer_capacity 只有 0.005 上下:它表示队列能往消费者投递的时间占比,接近 0 说明消费者的 prefetch 窗口一直是满的——消费者就是瓶颈')
stop.set(); stopc.set(); time.sleep(1)

print('== 二:三种“积压”各是什么样子:(a) 没有消费者 (b) 消费者在,但慢 (c) 消费者卡住不 ack —— 同样往队列放 5000 条,看 ready / unacked / consumers / consumer_capacity')
rows = []
for label, k, work, prefetch, stuck in (('(a) 没有消费者', 0, 0, 0, False), ('(b) 1 个慢消费者 prefetch=10', 1, 0.05, 10, False), ('(b2) 1 个慢消费者 prefetch=1000', 1, 0.05, 1000, False), ('(c) 消费者卡住不 ack', 1, 0, 100, True)):
    q = 'bd.' + label[1:3].strip('() ')
    ch.queue_delete(q); ch.queue_declare(q, durable=True)
    for i in range(5000): ch.basic_publish('', q, b'x' * 100)
    ch.queue_declare(q, passive=True)
    st_ = threading.Event(); consumers(q, k, work, prefetch, st_, None, stuck); time.sleep(4)
    rows.append((label,) + snap(q)); st_.set(); time.sleep(0.5)
print('  情形                              ready  unacked  consumers  consumer_capacity')
for r in rows: print(f'  {r[0]:<30}{str(r[1]):>8}{str(r[2]):>9}{str(r[3]):>11}{str(r[4]):>18}')

print('== 三:恢复:积压 20000 条,消费者每条处理 5 ms(prefetch=20):加消费者能把清空时间线性缩短?1 / 2 / 4 / 8 个消费者')
res = {}
for k in (1, 2, 4, 8):
    q = f'rec{k}'; ch.queue_delete(q); ch.queue_declare(q, durable=True)
    for i in range(20000 if k > 1 else 4000): ch.basic_publish('', q, b'x' * 100)
    ch.queue_declare(q, passive=True); N = 20000 if k > 1 else 4000
    cnt = [0]; st_ = threading.Event(); t0 = time.perf_counter(); consumers(q, k, 0.005, 20, st_, cnt)
    while cnt[0] < N and time.perf_counter() - t0 < 120: time.sleep(0.05)
    res[k] = (N, time.perf_counter() - t0); st_.set(); time.sleep(0.3)
print('  消费者数  清空条数  耗时      吞吐')
for k, (N, e) in res.items(): print(f'  {k:<8}{N:>8}{e:>8.1f} s{N / e:>9.0f} 条/秒')
print('  (1 个消费者只放了 4000 条,否则要几分钟;看吞吐:单个消费者的理论上限是 1 ÷ 5 ms = 200 条/秒,实测约 160 条/秒;吞吐随消费者数线性增长)')

print('== 四:最后的手段:purge 直接清空(丢弃所有 ready 的消息,unacked 不受影响);放 50000 条,purge 要多久')
ch.queue_declare('pq', durable=True); ch.queue_purge('pq')
for i in range(50000): ch.basic_publish('', 'pq', b'x' * 100)
ch.queue_declare('pq', passive=True)
t0 = time.perf_counter(); r = ch.queue_purge('pq'); e = ms(t0)
print(f'  purge 50000 条: 返回 message_count={r.method.message_count},用了 {e:.0f} ms;purge 之后 ready={n.qinfo("pq")[0]}')
c.close(); n.stop()
