import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q13'); reset()
n = Node('q13'); n.start()
c = n.conn(); ch = c.channel()
def mk(name, **a):
    ch.queue_delete(name); qdecl(ch, name, arguments=a)
def getall(q):
    r = []
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=True)
        if mt is None: return r
        r.append(b.decode())
def pub_n(q, k, body=None, **kw):
    for i in range(k): ch.basic_publish('', q, body or f'm{i}'.encode(), pika.BasicProperties(**kw))
    ch.queue_declare(q, passive=True)

print('== 一:x-max-length=5,默认溢出策略 drop-head:发 10 条,留下的是最新的 5 条,最老的被丢(没有任何通知)')
mk('l1', **{'x-max-length': 5}); pub_n('l1', 10)
print(f'  队列里剩: {getall("l1")}')

print('== 二:x-overflow=reject-publish:队列满了之后新发布被拒绝。没开 confirm 时发布方不知道;开了 confirm 才收到 Nack')
mk('l2', **{'x-max-length': 5, 'x-overflow': 'reject-publish'}); pub_n('l2', 10)
print(f'  不开 confirm 发 10 条,队列里是: {getall("l2")}(最先到的 5 条,后 5 条悄悄丢了)')
mk('l2', **{'x-max-length': 5, 'x-overflow': 'reject-publish'})
cc = n.conn(); cch = cc.channel(); cch.confirm_delivery()
res = []
for i in range(10):
    try: cch.basic_publish('', 'l2', f'm{i}'.encode()); res.append('ack')
    except pika.exceptions.NackError: res.append('NACK')
print(f'  开 confirm 发 10 条的结果: {res}')
cc.close()

print('== 三:x-overflow=reject-publish-dlx:被拒绝的新消息不是丢弃而是进死信交换机,reason = maxlen')
ch.exchange_declare('dlx', 'fanout', durable=True); qdecl(ch, 'dlq'); ch.queue_bind('dlq', 'dlx', ''); ch.queue_purge('dlq')
mk('l3', **{'x-max-length': 3, 'x-overflow': 'reject-publish-dlx', 'x-dead-letter-exchange': 'dlx'}); pub_n('l3', 6)
time.sleep(0.3)
print(f'  主队列: {getall("l3")}')
dl = []
while True:
    mt, p, b = ch.basic_get('dlq', auto_ack=True)
    if mt is None: break
    dl.append((b.decode(), p.headers['x-death'][0]['reason']))
print(f'  死信队列: {dl}')
mk('l3b', **{'x-max-length': 3, 'x-dead-letter-exchange': 'dlx'}); pub_n('l3b', 6)
time.sleep(0.3)
dl = []
while True:
    mt, p, b = ch.basic_get('dlq', auto_ack=True)
    if mt is None: break
    dl.append((b.decode(), p.headers['x-death'][0]['reason']))
print(f'  对比 drop-head + 死信:主队列 {getall("l3b")};死信队列(被挤出去的最老的)是 {dl}')

print('== 四:x-max-length-bytes:限制的是什么大小?100 字节的消息体,限制 1000 字节,发 30 条后留下几条(队列长度字节数怎么算)')
mk('l4', **{'x-max-length-bytes': 1000}); pub_n('l4', 30, body=b'x' * 100)
left = getall('l4'); print(f'  留下 {len(left)} 条(100 字节/条,限制 1000 字节)')
mk('l4b', **{'x-max-length-bytes': 1000}); pub_n('l4b', 30, body=b'x' * 100, headers={'h' * 20: 'v' * 80}, message_id='abcdefgh')
left = getall('l4b'); print(f'  同样的消息体再加上约 100 字节的头/属性:留下 {len(left)} 条——限制只数消息体,不数属性')
mk('l4c', **{'x-max-length-bytes': 1000}); pub_n('l4c', 3, body=b'y' * 2000)
print(f'  单条 2000 字节(比限制大)发 3 条:留下 {len(getall("l4c"))} 条')

print('== 五:同时设了 x-max-length 和 x-max-length-bytes,以先到的为准;用 policy 设置限制与队列参数同时存在时取较小的')
mk('l5', **{'x-max-length': 10, 'x-max-length-bytes': 500}); pub_n('l5', 20, body=b'x' * 100)
print(f'  max-length=10 且 max-bytes=500,发 20 条 100 字节:留下 {len(getall("l5"))} 条(字节限制先到)')
mk('l6', **{'x-max-length': 10}); n.ctl('set_policy', 'lim', '^l6$', '{"max-length": 4}', '--apply-to', 'queues')
time.sleep(0.5); pub_n('l6', 20)
print(f'  队列参数 x-max-length=10 + policy max-length=4,发 20 条:留下 {len(getall("l6"))} 条;policy 查询: {n.ctl("list_policies").splitlines()[-1].split(chr(9))[:5]}')
n.ctl('clear_policy', 'lim')

print('== 六:未确认(unacked)的消息不算在长度里:max-length=3,消费者先拿走 3 条不 ack,再发 10 条,ready 里有几条')
mk('l7', **{'x-max-length': 3}); pub_n('l7', 3)
cc = n.conn(); cch = cc.channel(); got = [cch.basic_get('l7') for _ in range(3)]
print(f'  取走 3 条不 ack 后: (ready, unacked) = {n.qinfo("l7")}')
pub_n('l7', 10, body=b'new'); time.sleep(0.2)
print(f'  再发 10 条后: (ready, unacked) = {n.qinfo("l7")}(上限只管 ready 的)')
cc.close()

print('== 七:quorum 队列同样支持 x-max-length(drop-head / reject-publish),但 reject-publish 的限制是“大约”的:不开 confirm 连发 10 条会超过,开 confirm 逐条发则在略过上限后才开始拒绝')
mk('l8', **{'x-queue-type': 'quorum', 'x-max-length': 5}); pub_n('l8', 10); time.sleep(0.5)
print(f'  quorum + drop-head(连发 10 条,上限 5):留下 {getall("l8")}')
mk('l9', **{'x-queue-type': 'quorum', 'x-max-length': 5, 'x-overflow': 'reject-publish'}); pub_n('l9', 10); time.sleep(0.5)
print(f'  quorum + reject-publish,不开 confirm 连发 10 条(上限 5):留下 {len(getall("l9"))} 条')
mk('l9', **{'x-queue-type': 'quorum', 'x-max-length': 5, 'x-overflow': 'reject-publish'})
cc = n.conn(); cch = cc.channel(); cch.confirm_delivery(); r = []
for i in range(30):
    try: cch.basic_publish('', 'l9', f'm{i}'.encode()); r.append('A')
    except pika.exceptions.NackError: r.append('N')
    time.sleep(0.01)
print(f'  quorum + reject-publish,开 confirm 每条间隔 10 ms 发 30 条的结果: {"".join(r)}(A = Ack,N = Nack);队列里最后 {len(getall("l9"))} 条')
cc.close()
c.close(); n.stop()
