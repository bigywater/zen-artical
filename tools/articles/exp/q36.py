import sys, os, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q36'); reset()
n = Node('q36'); n.start()
px = Proxy(n.amqp)
c = n.conn(); ch = c.channel()
def fill(q, k, **a):
    ch.queue_delete(q); ch.queue_declare(q, durable=True, arguments=a)
    for i in range(k): ch.basic_publish('', q, f'm{i}'.encode(), pika.BasicProperties(delivery_mode=2))
    ch.queue_declare(q, passive=True)
def spawn(port, q, prefetch, ack_first, hb=60):
    p = subprocess.Popen([sys.executable, str(HERE / 'qcons.py'), str(port), q, str(prefetch), str(ack_first), str(hb)], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == 'READY'; return p
def wait_until(fn, limit=60, step=0.05):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limit:
        if fn(): return time.perf_counter() - t0
        time.sleep(step)
    return None

print('== 一:消费者进程被 kill -9:100 条未确认消息多久回到队列?(进程一死,操作系统会关掉 TCP 连接,broker 立刻发现)')
fill('r1', 200)
p = spawn(n.amqp, 'r1', 100, 0)
print(f'  kill 之前 (ready, unacked) = {n.qinfo("r1")}')
t0 = time.perf_counter(); os.kill(p.pid, signal.SIGKILL); p.wait()
e = wait_until(lambda: (n.qinfo('r1') or (0, 0))[1] == 0)
print(f'  kill -9 之后 {e * 1000:.0f} ms,unacked 变回 0;(ready, unacked) = {n.qinfo("r1")}')

print('== 二:先确认了一部分再崩溃:队列里共 150 条,消费者确认前 40 条、接下来 60 条没确认(prefetch=60)就被杀。被重新投递的是哪些?')
fill('r2', 150)
p = spawn(n.amqp, 'r2', 60, 40)
os.kill(p.pid, signal.SIGKILL); p.wait()
wait_until(lambda: (n.qinfo('r2') or (0, 0))[1] == 0)
cc = n.conn(); cch = cc.channel(); items = []
while True:
    mt, pr, b = cch.basic_get('r2', auto_ack=True)
    if mt is None: break
    items.append((b.decode(), mt.redelivered))
red = [x for x, r in items if r]; fresh = [x for x, r in items if not r]
print(f'  队列里剩 {len(items)} 条:redelivered=True 的 {len(red)} 条(m{red[0][1:]}~m{red[-1][1:]})、全新的 {len(fresh)} 条(m{fresh[0][1:]}~m{fresh[-1][1:]});前 40 条(m0~m39)已确认,没有再出现')
print(f'  顺序: {[x for x, _ in items[:5]]}……——被重新投递的回到了队首,原来的先后顺序保持不变')
cc.close()

print('== 三:网络黑洞(消费者进程还活着,但网络不通,没有 TCP 关闭):靠心跳发现。经过代理停止转发,heartbeat=3 的消费者持有 50 条未确认消息,多久回到队列?')
fill('r3', 100)
p = spawn(px.port, 'r3', 50, 0, hb=3)
print(f'  黑洞开始前 (ready, unacked) = {n.qinfo("r3")}')
px.hole = True; t0 = time.perf_counter()
e = wait_until(lambda: (n.qinfo('r3') or (0, 0))[1] == 0, limit=60, step=0.2)
print(f'  黑洞开始后 {e:.1f} s,unacked 回到 0;(ready, unacked) = {n.qinfo("r3")}(heartbeat=3 s,约 3 倍超时,和第 22 篇的黑洞检测时间一致)' if e else '  60 秒内 unacked 没有回到 0')
p.kill(); px.close()

print('== 四:poison 消息的重投次数:经典队列只有 redelivered 布尔值;quorum 队列有 x-delivery-count 头,并可以用 delivery-limit 限制重试次数。一条消息,消费者每次拿到就“崩溃”(断开连接),看 quorum 队列里它被投递几次、delivery-count 怎么变')
ch.queue_delete('r4'); ch.queue_declare('r4', durable=True, arguments={'x-queue-type': 'quorum', 'x-delivery-limit': 3})
ch.basic_publish('', 'r4', b'poison', pika.BasicProperties(delivery_mode=2)); time.sleep(0.3)
seen = []
for attempt in range(6):
    cc = n.conn(); cch = cc.channel(); mt, pr, b = cch.basic_get('r4', auto_ack=False)
    if mt is None: seen.append('(队列里已没有这条消息)'); cc.close(); break
    seen.append((mt.redelivered, (pr.headers or {}).get('x-delivery-count')))
    cc.close(); time.sleep(0.5)
print('  每次拿到时 (redelivered, x-delivery-count 头): ' + str(seen))
time.sleep(0.5)
print(f'  x-delivery-limit=3 的队列最终 (ready, unacked) = {n.qinfo("r4")}——超过次数之后消息被丢弃(这里没有配死信交换机)')

print('== 五:经典队列拿不到重投次数:同一条消息被拒绝 requeue 5 次,redelivered 和头里有什么')
fill('r6', 1)
cc = n.conn(); cch = cc.channel(); rs = []
for i in range(5):
    mt, pr, b = cch.basic_get('r6'); rs.append((mt.redelivered, (pr.headers or {}).get('x-delivery-count'))); cch.basic_nack(mt.delivery_tag, requeue=True)
print(f'  经典队列 5 次 (redelivered, x-delivery-count): {rs}')
cc.close(); c.close(); px.close(); n.stop()
