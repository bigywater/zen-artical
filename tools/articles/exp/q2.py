import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q2'); reset()
n = Node('q2'); n.start()
c = n.conn(); ch = c.channel()
def setup(ex, typ, binds, qs=None):
    ch.exchange_declare(ex, typ, durable=True)
    qs = qs or sorted({b[0] for b in binds})
    for q in qs: qdecl(ch, q); ch.queue_purge(q)
    for b in binds:
        ch.queue_bind(b[0], ex, b[1], arguments=b[2] if len(b) > 2 else None)
def pub(ex, key, body, headers=None):
    ch.basic_publish(ex, key, body.encode(), pika.BasicProperties(headers=headers) if headers else None)
def got(qs):
    return {q: drain(ch, q) for q in qs}
def table(res, msgs):
    for q, L in res.items(): print(f'  {q:<10} 收到 {len(L)} 条: {L}')

print('== 一:direct:routing key 必须与绑定 key 完全相等;d.a 绑 red,d.b 绑 blue,d.c 绑 red 和 blue 两个 key')
setup('x.direct', 'direct', [('d.a', 'red'), ('d.b', 'blue'), ('d.c', 'red'), ('d.c', 'blue')])
for k in ('red', 'blue', 'green', 'Red', 'red '): pub('x.direct', k, f'key={k!r}')
time.sleep(0.2)
table(got(['d.a', 'd.b', 'd.c']), None)
print('  发布了 5 条(red、blue、green、Red、"red "):green、Red(大小写不同)和 "red "(末尾空格)没有任何绑定,直接丢弃;d.c 绑了两个 key,red 和 blue 各收一条')

print('== 二:fanout:忽略 routing key,所有绑定的队列各收一份;绑定时给的 key 也被忽略')
setup('x.fanout', 'fanout', [('f.a', 'k1'), ('f.b', 'k2'), ('f.c', '')])
for k in ('anything', '', 'k1'): pub('x.fanout', k, f'key={k!r}')
time.sleep(0.2)
table(got(['f.a', 'f.b', 'f.c']), None)
print('  3 条消息 × 3 个队列 = 每个队列都收到 3 条,与发布时和绑定时的 routing key 都无关')

print('== 三:topic:key 是用 . 分隔的单词;* 匹配恰好一个单词,# 匹配零个或多个单词。绑定:t.orange=*.orange.*,t.rabbit=*.*.rabbit,t.lazy=lazy.#,t.all=#')
setup('x.topic', 'topic', [('t.orange', '*.orange.*'), ('t.rabbit', '*.*.rabbit'), ('t.lazy', 'lazy.#'), ('t.all', '#')])
keys = ['quick.orange.rabbit', 'lazy.orange.elephant', 'quick.orange.fox', 'lazy.brown.fox', 'lazy.pink.rabbit', 'quick.brown.fox', 'orange', 'quick.orange.male.rabbit', 'lazy.orange.male.rabbit', 'lazy']
for k in keys: pub('x.topic', k, k)
time.sleep(0.2)
res = got(['t.orange', 't.rabbit', 't.lazy', 't.all'])
print(f'  {"routing key":<26}' + ''.join(f'{q:<10}' for q in res))
for k in keys:
    print(f'  {k:<26}' + ''.join(f'{"✓" if k in L else "·":<10}' for L in res.values()))
print('  各队列收到的条数: ' + ', '.join(f'{q}={len(L)}' for q, L in res.items()))

print('== 四:headers:按消息头路由,忽略 routing key。x-match=all 要求全部匹配,x-match=any 只要一个匹配')
setup('x.headers', 'headers', [('h.all', '', {'x-match': 'all', 'format': 'pdf', 'type': 'report'}), ('h.any', '', {'x-match': 'any', 'format': 'pdf', 'type': 'report'})])
msgs = [({'format': 'pdf', 'type': 'report'}, 'pdf+report'), ({'format': 'pdf', 'type': 'log'}, 'pdf+log'), ({'format': 'txt', 'type': 'report'}, 'txt+report'), ({'format': 'txt'}, 'txt only'), ({'format': 'pdf', 'type': 'report', 'extra': 1}, 'pdf+report+extra'), ({}, '无头')]
for h, b in msgs: pub('x.headers', 'ignored-key', b, h)
time.sleep(0.2)
res = got(['h.all', 'h.any'])
print(f'  {"消息头":<28}' + ''.join(f'{q:<10}' for q in res))
for h, b in msgs: print(f'  {b:<28}' + ''.join(f'{"✓" if b in L else "·":<10}' for L in res.values()))

print('== 五:同一条消息命中同一个队列的多个绑定,队列里只有一份;但命中不同队列各一份')
setup('x.dup', 'topic', [('u.q', 'a.*'), ('u.q', '#'), ('u.q', 'a.b'), ('u.q2', 'a.b')])
pub('x.dup', 'a.b', 'a.b 这一条')
time.sleep(0.2)
table(got(['u.q', 'u.q2']), None)
print('  u.q 有 3 个绑定(a.*、#、a.b)都匹配 a.b,队列里仍只有 1 份')

print('== 六:路由查找的代价:1 个队列绑 B 个 key(headers 是 B 组不同的头),每次发布命中其中一个;发布 10000 条的耗时(不开 confirm,取 3 次中位数)')
N = 10000
def bench(typ, B):
    ex = f'b.{typ}.{B}'
    ch.exchange_declare(ex, typ, durable=True); qdecl(ch, 'bench'); ch.queue_purge('bench')
    for i in range(B):
        if typ == 'direct': ch.queue_bind('bench', ex, f'key{i}')
        elif typ == 'topic': ch.queue_bind('bench', ex, f'key.{i}.#')
        else: ch.queue_bind('bench', ex, '', arguments={'x-match': 'all', 'k': i})
    if typ == 'direct': pubs = [(f'key{i}', None) for i in range(B)]
    elif typ == 'topic': pubs = [(f'key.{i}.z', None) for i in range(B)]
    else: pubs = [('', pika.BasicProperties(headers={'k': i})) for i in range(B)]
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        for i in range(N):
            k, pr_ = pubs[i % B]; ch.basic_publish(ex, k, b'x', pr_)
        ch.queue_declare('bench', passive=True)
        ts.append(ms(t0)); ch.queue_purge('bench')
    ch.exchange_delete(ex)
    return median(ts)
res = {typ: {B: bench(typ, B) for B in (10, 100, 1000)} for typ in ('direct', 'topic', 'headers')}
print(f'  {"绑定数 B":<10}' + ''.join(f'{B:>12}' for B in (10, 100, 1000)))
for typ, d in res.items(): print(f'  {typ:<10}' + ''.join(f'{d[B]:>9.0f} ms' for B in d))
c.close(); n.stop()
