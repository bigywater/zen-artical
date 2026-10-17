import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q4'); reset()
n = Node('q4'); n.start()
c = n.conn(); ch = c.channel()
def fill(q, k, pre='m'):
    qdecl(ch, q); ch.queue_purge(q)
    for i in range(1, k + 1): ch.basic_publish('', q, f'{pre}{i}'.encode())
    time.sleep(0.15)
def lq(q): 
    time.sleep(0.2)
    return n.qinfo(q)
def get(chn, q):
    mt, p, b = chn.basic_get(q, auto_ack=False)
    return (mt, b.decode(), mt.redelivered) if mt else None

print('== 一:ack 之前消息处于“未确认”:取走 3 条不 ack,messages_ready 变少、messages_unacknowledged 变多;ack 之后才真正从队列消失')
fill('q.a', 5)
print(f'  初始 (ready, unacked) = {lq("q.a")}')
tags = [get(ch, 'q.a') for _ in range(3)]
print(f'  basic_get 取 3 条(m1 m2 m3),不 ack: {[t[1] for t in tags]};(ready, unacked) = {lq("q.a")}')
ch.basic_ack(tags[0][0].delivery_tag)
print(f'  ack m1 之后: (ready, unacked) = {lq("q.a")}')
ch.basic_ack(tags[2][0].delivery_tag, multiple=True)
print(f'  对 m3 的 tag 做 ack(multiple=True),m2 也一并确认: (ready, unacked) = {lq("q.a")}')

print('== 二:nack / reject 并 requeue=True:消息回到队列的什么位置?redelivered 标志变成 True')
ch2 = c.channel(); fill('q.b', 5)
m1 = get(ch2, 'q.b'); m2 = get(ch2, 'q.b')
print(f'  取到 {m1[1]}、{m2[1]},redelivered={m1[2]},{m2[2]}')
ch2.basic_nack(m1[0].delivery_tag, requeue=True)
nxt = [get(ch2, 'q.b') for _ in range(4)]
print(f'  nack(m1, requeue=True) 之后继续取 4 条的顺序: {[(x[1], x[2]) for x in nxt]}(m2 还没确认,不在里面)')
ch2.close(); ch2 = c.channel()
print(f'  channel 关闭后全部未确认的消息回到队列: (ready, unacked) = {lq("q.b")}')
print(f'  再取全部(顺序和 redelivered 标志): {[(x[1], x[2]) for x in [get(ch2, "q.b") for _ in range(5)] if x]}')

print('== 三:basic_reject 一次拒一条,basic_nack 可以 multiple=True 一次拒一批;requeue=False 就丢弃(没有死信 exchange 的话)')
ch3 = c.channel(); fill('q.c', 6)
ms_ = [get(ch3, 'q.c') for _ in range(6)]
ch3.basic_reject(ms_[0][0].delivery_tag, requeue=False)
print(f'  reject(m1, requeue=False): (ready, unacked) = {lq("q.c")}')
ch3.basic_nack(ms_[3][0].delivery_tag, multiple=True, requeue=False)
print(f'  nack(m4, multiple=True, requeue=False) 把 m2~m4 一起丢: (ready, unacked) = {lq("q.c")}')
ch3.basic_nack(ms_[5][0].delivery_tag, multiple=True, requeue=True)
print(f'  nack(m6, multiple=True, requeue=True) 把 m5、m6 放回: (ready, unacked) = {lq("q.c")}')
print(f'  队列里剩下: {[(x[1], x[2]) for x in [get(ch3, "q.c") for _ in range(2)]]}')

print('== 四:delivery tag 是每个 channel 自己的;换个 channel 去确认,会得到 406')
ch4 = c.channel(); ch5 = c.channel(); fill('q.d', 2)
m = get(ch4, 'q.d')
closed = []
ch5._impl.add_on_close_callback(lambda ch_, r: closed.append(str(r)))
ch5.basic_ack(m[0].delivery_tag)
time.sleep(0.4)
for _ in range(3): c.process_data_events(0.2)
print(f'  channel A 收到 tag={m[0].delivery_tag} 的消息;channel B 用同一个 tag 去 ack → B 被关: {closed}')
print(f'  channel A 仍可确认: {"ok" if (ch4.basic_ack(m[0].delivery_tag) or True) else ""};(ready, unacked) = {lq("q.d")}')

print('== 五:ack 不到的消息,连接断开之后会怎样:自动 ack(auto_ack=True)的消息随消费者死亡而丢失;手动 ack 的会回到队列')
for mode in (True, False):
    q = f'q.e.{int(mode)}'; fill(q, 4)
    cc = n.conn(); cch = cc.channel()
    got = [cch.basic_get(q, auto_ack=mode)[0] for _ in range(3)]
    cc.close()   # 消费者“崩溃”,3 条取走但没处理完
    print(f'  auto_ack={mode}:取走 3 条后连接关闭 → (ready, unacked) = {lq(q)}')

print('== 六:拒绝并 requeue=True 的“毒消息”会无限循环:一个总是 nack(requeue=True) 的消费者,1 秒内同一条消息被投递了多少次')
fill('q.f', 1, pre='poison')
cnt = [0]; red = []
def cb(chn, mt, props, body):
    cnt[0] += 1; red.append(mt.redelivered); chn.basic_nack(mt.delivery_tag, requeue=True)
ch6 = c.channel(); ch6.basic_consume('q.f', cb)
t0 = time.time()
while time.time() - t0 < 1.0: c.process_data_events(0.05)
print(f'  1 秒内同一条消息被投递了 {cnt[0]} 次;第 1 次 redelivered={red[0]},之后全部 redelivered={all(red[1:])}')
print('  经典队列只带一个 redelivered 布尔值,没有计数——数不出已经重试了几次(quorum 队列有 x-delivery-count,见后面的文章)')
c.close(); n.stop()
