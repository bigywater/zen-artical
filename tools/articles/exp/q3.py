import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q3'); reset()
n = Node('q3'); n.start()
c = n.conn(); ch = c.channel()
def err(fn):
    try: fn(); return '成功'
    except Exception as e: return type(e).__name__ + ('(pika 在客户端就拒绝了,字符串超过 255 字节,没有发给 broker)' if 'ShortString' in type(e).__name__ else f': {str(e)[:150]}')

print('== 一:默认 exchange(名字是空串)把消息按 routing key = 队列名直接投到队列,不需要声明任何 exchange 或 binding')
qdecl(ch, 'hello'); ch.queue_purge('hello')
ch.basic_publish('', 'hello', b'hi')
time.sleep(0.2)
n.sh('list_queues name messages')
print(f'  basic_get → {drain(ch, "hello")}')
n.sh('list_bindings source_name destination_name routing_key')
print('  list_bindings 里的第一列为空串,就是默认 exchange;这个绑定不是我建的,队列一声明就有')

print('== 二:routing key 是不存在的队列名:消息被丢弃;加 mandatory 并开 confirm 才会知道')
ch.basic_publish('', 'no-such-queue', b'lost')
print('  不加 mandatory:发布没有任何错误,消息也没有去哪(没有这个队列)')
ch2 = c.channel(); ch2.confirm_delivery()
print('  mandatory=True + confirm:', err(lambda: ch2.basic_publish('', 'no-such-queue', b'lost', mandatory=True)))
ch3 = c.channel(); ch3.confirm_delivery()
print('  对存在的队列 mandatory=True:', err(lambda: ch3.basic_publish('', 'hello', b'ok', mandatory=True)))
drain(ch, 'hello')

print('== 三:默认 exchange 是被保护的:不能删、不能绑、不能用别的类型重新声明')
def fresh(): return c.channel()
print('  exchange_delete(""):        ', err(lambda: fresh().exchange_delete('')))
print('  queue_bind("hello", "", k): ', err(lambda: fresh().queue_bind('hello', '', 'k')))
print('  queue_unbind(…, ""):        ', err(lambda: fresh().queue_unbind('hello', '', 'hello')))
print('  exchange_declare("", fanout):', err(lambda: fresh().exchange_declare('', 'fanout')))
print('  exchange_declare("amq.foo"): ', err(lambda: fresh().exchange_declare('amq.foo', 'direct')))
print('  管理 API 里它叫 amq.default:', {k: v for k, v in n.api('/exchanges/%2F/amq.default').items() if k in ('name', 'type', 'durable', 'internal')})

print('== 四:队列名里的细节:服务器生成的名字(空队列名)、含 . 或空格或中文的名字、255 字节上限;队列删除后默认绑定同时消失')
r = ch.queue_declare('', exclusive=True)
gen = r.method.queue
print(f'  queue_declare("") → 服务器生成名字 {gen[:8]}…(共 {len(gen)} 个字符,前缀 amq.gen-)')
ch.basic_publish('', gen, b'to-generated')
time.sleep(0.2)
print(f'  用生成的名字作 routing key 发布 → {drain(ch, gen)}')
for name in ('a.b.c', 'with space', '中文队列', 'UPPER'):
    qdecl(ch, name); ch.basic_publish('', name, b'x'); time.sleep(0.1)
    print(f'  队列 {name!r}: 通过默认 exchange 收到 {drain(ch, name)}')
print('  255 字节的名字:', err(lambda: fresh().queue_declare('x' * 255, durable=True)))
print('  256 字节的名字:', err(lambda: fresh().queue_declare('x' * 256, durable=True)))
print('  routing key 256 字节:', err(lambda: (lambda c_: (c_.basic_publish('', 'y' * 256, b'x'), c_.queue_declare('hello', passive=True)))(fresh())))
ch.queue_delete(gen)
ch.queue_delete('x' * 255)
has = lambda: 'a.b.c' in n.ctl('list_bindings', 'source_name', 'destination_name', 'routing_key')
before = has(); ch.queue_delete('a.b.c'); after = has()
print(f'  list_bindings 里有没有 a.b.c 那一行:删除队列前 {before},删除后 {after}')
n.sh('list_bindings source_name destination_name routing_key')

print('== 五:走默认 exchange 与走一个显式 direct exchange 有没有速度差别:各发 20000 条 100 字节的消息(不开 confirm,两种交替跑 7 轮取中位数)')
ch.exchange_declare('x.d', 'direct', durable=True); qdecl(ch, 'bq'); ch.queue_bind('bq', 'x.d', 'bq')
N = 20000
def once(ex):
    ch.queue_purge('bq'); t0 = time.perf_counter()
    for i in range(N): ch.basic_publish(ex, 'bq', b'x' * 100)
    ch.queue_declare('bq', passive=True); return ms(t0)
A, B = [], []
for _ in range(7):   # 两种交替跑 7 轮,抵消机器忽快忽慢
    A.append(once('')); B.append(once('x.d'))
print(f'  默认 exchange:中位数 {median(A):.0f} ms(最小 {min(A):.0f}、最大 {max(A):.0f});显式 direct exchange:中位数 {median(B):.0f} ms(最小 {min(B):.0f}、最大 {max(B):.0f})')
c.close(); n.stop()
