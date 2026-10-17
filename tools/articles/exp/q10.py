import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q10'); reset()
n = Node('q10'); n.start()
c = n.conn(); ch = c.channel()
def setup(main, dlx='dlx', dlq='dlq', args=None, dlq_key='#'):
    ch.exchange_declare(dlx, 'topic', durable=True)
    qdecl(ch, dlq); ch.queue_bind(dlq, dlx, dlq_key); ch.queue_purge(dlq)
    a = {'x-dead-letter-exchange': dlx}; a.update(args or {})
    ch.queue_delete(main); qdecl(ch, main, arguments=a)
def getall(q):
    r = []
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=True)
        if mt is None: return r
        r.append((mt, p, b.decode()))
def show_death(p, keys=('count', 'reason', 'queue', 'exchange', 'routing-keys')):
    xd = (p.headers or {}).get('x-death')
    if not xd: return 'x-death: (无)'
    out = []
    for d in xd:
        out.append('{' + ', '.join(f'{k}: {int(d[k]) if k == "count" else d[k]!r}' for k in keys if k in d) + '}')
    return 'x-death = [' + ', '.join(out) + ']'

print('== 一:被拒绝(reject / nack,requeue=False)的消息进入死信交换机;看它带上的 x-death 头')
setup('m1')
ch.basic_publish('', 'm1', b'bad-msg', pika.BasicProperties(headers={'k': 'v'}))
mt, p, b = ch.basic_get('m1'); ch.basic_reject(mt.delivery_tag, requeue=False); time.sleep(0.2)
(mt, p, b), = getall('dlq')
print(f'  死信队列收到: body={b!r},exchange={mt.exchange!r},routing_key={mt.routing_key!r}')
print(f'  {show_death(p)}')
print(f'  其它头: { {k: v for k, v in p.headers.items() if k != "x-death"} }')
xd = p.headers['x-death'][0]
print(f'  x-death[0] 的全部键: {sorted(xd.keys())}')

print('== 二:消息过期(TTL)也进死信:队列级 x-message-ttl 和单条消息的 expiration;reason = expired')
setup('m2', args={'x-message-ttl': 300})
ch.basic_publish('', 'm2', b'queue-ttl')
setup('m2b')
ch.basic_publish('', 'm2b', b'msg-ttl', pika.BasicProperties(expiration='300'))
time.sleep(0.8)
for q in ('m2', 'm2b'):
    pass
res = getall('dlq')
for mt, p, b in res: print(f'  {b!r}: {show_death(p)}')

print('== 三:队列长度超限(x-max-length=3,默认 overflow=drop-head):最老的被挤出去并死信,reason = maxlen')
setup('m3', args={'x-max-length': 3})
for i in range(6): ch.basic_publish('', 'm3', f'msg{i}'.encode())
time.sleep(0.3)
print(f'  主队列里剩: {[b for _, _, b in getall("m3")]}')
res = getall('dlq')
print(f'  死信队列收到: {[(b, p.headers["x-death"][0]["reason"]) for _, p, b in res]}')

print('== 四:x-dead-letter-routing-key:不设时死信沿用原来的 routing key,设了就用指定的;只有 DLX 上有对应绑定才会被收下')
ch.exchange_declare('dlx4', 'direct', durable=True)
qdecl(ch, 'dlq.a'); ch.queue_bind('dlq.a', 'dlx4', 'orig'); qdecl(ch, 'dlq.b'); ch.queue_bind('dlq.b', 'dlx4', 'fixed')
for q in ('dlq.a', 'dlq.b'): ch.queue_purge(q)
for name, extra in (('m4a', {}), ('m4b', {'x-dead-letter-routing-key': 'fixed'})):
    ch.queue_delete(name); qdecl(ch, name, arguments=dict({'x-dead-letter-exchange': 'dlx4'}, **extra))
ch.exchange_declare('src', 'direct', durable=True)
for name in ('m4a', 'm4b'):
    ch.queue_purge(name); ch.queue_bind(name, 'src', 'orig')
ch.queue_purge('m4a'); ch.queue_purge('m4b')
ch.basic_publish('src', 'orig', b'to-both')
time.sleep(0.2)
for name in ('m4a', 'm4b'):
    mt, p, b = ch.basic_get(name); ch.basic_reject(mt.delivery_tag, requeue=False)
time.sleep(0.3)
for q in ('dlq.a', 'dlq.b'):
    print(f'  {q}(绑定 key={"orig" if q.endswith("a") else "fixed"}) 收到: {[(b, p.headers["x-death"][0]["queue"], p.headers["x-death"][0]["routing-keys"]) for _, p, b in getall(q)]}')
print('  m4a 没设 x-dead-letter-routing-key:死信带原来的 key orig,进了 dlq.a;m4b 设成 fixed:进了 dlq.b,x-death 里记的 routing-keys 仍是原来的 orig')

print('== 五:DLX 上没有匹配的绑定(或根本不存在):死信直接被丢掉,没有任何错误')
ch.queue_delete('m5'); qdecl(ch, 'm5', arguments={'x-dead-letter-exchange': 'dlx.nobind'})
ch.exchange_declare('dlx.nobind', 'direct', durable=True)
for i in range(3): ch.basic_publish('', 'm5', f'd{i}'.encode())
for i in range(3):
    mt, p, b = ch.basic_get('m5'); ch.basic_reject(mt.delivery_tag, requeue=False)
time.sleep(0.3)
print(f'  拒绝了 3 条,m5 里剩 {n.qinfo("m5")},没有绑定的 DLX 没有留下任何东西(消息消失)')
ch.queue_delete('m5'); qdecl(ch, 'm5', arguments={'x-dead-letter-exchange': 'dlx.ghost'})
ch.basic_publish('', 'm5', b'g'); mt, p, b = ch.basic_get('m5'); ch.basic_reject(mt.delivery_tag, requeue=False); time.sleep(0.3)
print(f'  DLX 指向一个不存在的 exchange:拒绝后 m5 里剩 {n.qinfo("m5")},channel 仍然 {"打开" if ch.is_open else "关闭"},消息消失')

print('== 六:用死信实现“重试”:main 被拒绝 → DLX → wait 队列(TTL 300 ms)→ 过期后死信回 main;看 x-death 的 count 怎么涨')
ch.exchange_declare('retry.dlx', 'direct', durable=True); ch.exchange_declare('main.dlx', 'direct', durable=True)
ch.queue_delete('main'); ch.queue_delete('wait')
qdecl(ch, 'main', arguments={'x-dead-letter-exchange': 'retry.dlx', 'x-dead-letter-routing-key': 'wait'})
qdecl(ch, 'wait', arguments={'x-dead-letter-exchange': 'main.dlx', 'x-dead-letter-routing-key': 'main', 'x-message-ttl': 300})
ch.queue_bind('wait', 'retry.dlx', 'wait'); ch.queue_bind('main', 'main.dlx', 'main')
ch.basic_publish('', 'main', b'retry-me')
attempts = []
t0 = time.perf_counter()
for _ in range(4):
    for _ in range(100):
        mt, p, b = ch.basic_get('main')
        if mt: break
        time.sleep(0.02)
    xd = (p.headers or {}).get('x-death')
    cnt_main = next((int(d['count']) for d in xd if d['queue'] == 'main'), 0) if xd else 0
    attempts.append((round((time.perf_counter() - t0) * 1000), cnt_main, mt.redelivered))
    ch.basic_reject(mt.delivery_tag, requeue=False)
print(f'  每次拿到消息的 (距开始 ms, x-death 里 main 的 count, redelivered): {attempts}')
time.sleep(0.5)
mt, p, b = ch.basic_get('main')
print(f'  第 5 次拿到时的 x-death: {show_death(p)}')
print(f'  first-death: queue={p.headers["x-first-death-queue"]!r} reason={p.headers["x-first-death-reason"]!r} exchange={p.headers["x-first-death-exchange"]!r}; last-death: queue={p.headers["x-last-death-queue"]!r} reason={p.headers["x-last-death-reason"]!r}')
ch.basic_ack(mt.delivery_tag)

print('== 七:死信自己绕回来的循环:A 的死信交换机把消息发回 A,TTL 到期死信 → 回 A → 再到期……无人拒绝时 RabbitMQ 会发现循环并丢弃')
ch.exchange_declare('loop.x', 'fanout', durable=True)
ch.queue_delete('loopq'); qdecl(ch, 'loopq', arguments={'x-dead-letter-exchange': 'loop.x', 'x-message-ttl': 200}); ch.queue_bind('loopq', 'loop.x', '')
ch.basic_publish('', 'loopq', b'around')
time.sleep(1.5)
print(f'  1.5 秒后 loopq 里剩 {n.qinfo("loopq", ("messages",))[0]} 条(TTL 200 ms,如果没有循环检测它会一直转下去)')
log = [l.split('] ', 1)[-1] if '] ' in l else l for l in n.logs('cycle|loopq')]
print('  broker 日志里关于这个循环的行:')
for l in log[:4]: print('    ' + l[:200])
c.close(); n.stop()
