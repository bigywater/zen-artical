import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q6'); reset()
n = Node('q6'); n.start()
px = Proxy(n.amqp)
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); ch = c.channel()
ch.exchange_declare('x.d', 'direct', durable=True); qdecl(ch, 'qd'); ch.queue_bind('qd', 'x.d', 'ok'); ch.queue_purge('qd')
returned = []
ch.add_on_return_callback(lambda chn, m, p, b: returned.append((m.reply_code, m.reply_text, m.exchange, m.routing_key, p, b)))
def pump(t=0.5):
    for _ in range(int(t / 0.1)): c.process_data_events(0.1)

print('== 一:mandatory=True 且消息无法路由:broker 发回 Basic.Return,带 reply-code 312 NO_ROUTE,以及原来的 exchange、routing key、属性和消息体')
m = px.mark()
props = pika.BasicProperties(message_id='id-42', content_type='text/plain', headers={'trace': 'abc'}, delivery_mode=2)
ch.basic_publish('x.d', 'nomatch', b'hello-return', props, mandatory=True)
pump()
print(f'  线上帧: {[(e[1], e[2]) for e in px.names(m)]}')
code, text, ex, rk, p, b = returned[0]
print(f'  Basic.Return: reply-code={code} reply-text={text!r} exchange={ex!r} routing-key={rk!r}')
print(f'  退回的属性: message_id={p.message_id} content_type={p.content_type} headers={p.headers} delivery_mode={p.delivery_mode};body={b!r}')

print('== 二:没有开 confirm 时 Return 是异步的:发 1000 条无法路由的 mandatory 消息,发布调用立刻返回,Return 稍后才陆续到达')
returned.clear()
t0 = time.perf_counter()
for i in range(1000): ch.basic_publish('x.d', 'nomatch', f'm{i}'.encode(), mandatory=True)
t_pub = ms(t0)
got0 = len(returned)
pump(1.0)
print(f'  1000 条发布调用本身花了 {t_pub:.0f} ms,这时已处理的 Return 回调 {got0} 个;再处理 1 秒的网络事件之后共收到 {len(returned)} 个,顺序是否与发布一致: {[r[5].decode() for r in returned] == [f"m{i}" for i in range(1000)]}')

print('== 三:哪些情形算“不可路由”:四种 exchange 各一次;可路由到队列的不会被退回')
ch.exchange_declare('x.f', 'fanout', durable=True)               # 没有绑定的 fanout
ch.exchange_declare('x.t', 'topic', durable=True); qdecl(ch, 'qt'); ch.queue_bind('qt', 'x.t', 'a.*')
ch.exchange_declare('x.h', 'headers', durable=True); qdecl(ch, 'qh'); ch.queue_bind('qh', 'x.h', '', arguments={'x-match': 'all', 'k': 'v'})
cases = [('direct 有绑定 key 匹配', 'x.d', 'ok', None), ('direct key 不匹配', 'x.d', 'bad', None), ('fanout 没有任何绑定', 'x.f', '', None), ('topic 匹配 a.*', 'x.t', 'a.b', None),
         ('topic 不匹配', 'x.t', 'b.c', None), ('headers 匹配', 'x.h', '', {'k': 'v'}), ('headers 不匹配', 'x.h', '', {'k': 'w'}), ('exchange 不存在', 'nope.x', 'k', None)]
for name, ex, rk, hd in cases:
    returned.clear()
    cc = c.channel(); rr = []
    cc.add_on_return_callback(lambda chn, m, p, b: rr.append(m.reply_code))
    cc.basic_publish(ex, rk, b'x', pika.BasicProperties(headers=hd) if hd else None, mandatory=True)
    for _ in range(4): c.process_data_events(0.1)
    state = f'退回 {rr[0]}' if rr else ('channel 被关' if cc.is_closed else '已路由')
    print(f'  {name:<22}→ {state}')
for q in ('qd', 'qt', 'qh'): ch.queue_purge(q)

print('== 四:备用交换机 alternate-exchange:主 exchange 路由不到时转给它;转得到就不算不可路由,mandatory 也就不会退回')
ch.exchange_declare('x.ae', 'fanout', durable=True); qdecl(ch, 'q.ae'); ch.queue_bind('q.ae', 'x.ae', ''); ch.queue_purge('q.ae')
ch.exchange_declare('x.main', 'direct', durable=True, arguments={'alternate-exchange': 'x.ae'}); qdecl(ch, 'q.main'); ch.queue_bind('q.main', 'x.main', 'ok'); ch.queue_purge('q.main')
returned.clear()
for k in ('ok', 'ok', 'stray1', 'stray2', 'stray3'): ch.basic_publish('x.main', k, k.encode(), mandatory=True)
pump(0.6)
print(f'  发了 5 条 mandatory(2 条能路由、3 条路由不到):q.main = {n.qinfo("q.main")[0]} 条,q.ae = {n.qinfo("q.ae")[0]} 条,被退回 {len(returned)} 条')
print(f'  q.ae 里的消息: {drain(ch, "q.ae")}')
print('  如果备用交换机本身也路由不到,才会退回:')
ch.exchange_declare('x.ae2', 'fanout', durable=True)
ch.exchange_declare('x.main2', 'direct', durable=True, arguments={'alternate-exchange': 'x.ae2'})
returned.clear(); ch.basic_publish('x.main2', 'stray', b's', mandatory=True); pump(0.6)
print(f'    x.main2 → x.ae2(没有绑定): 被退回 {len(returned)} 条,reply-code={returned[0][0] if returned else None}')

print('== 五:mandatory 的代价:向一个可路由的队列发 20000 条,mandatory=False / True 交替 7 轮取中位数(都不开 confirm)')
qdecl(ch, 'qb'); ch.queue_bind('qb', 'x.d', 'bench')
c3 = n.conn(); ch3 = c3.channel()   # 直连 broker,不经过代理
def once(mand):
    ch3.queue_purge('qb'); t0 = time.perf_counter()
    for i in range(20000): ch3.basic_publish('x.d', 'bench', b'x' * 100, mandatory=mand)
    ch3.queue_declare('qb', passive=True); return ms(t0)
A, B = [], []
for _ in range(7): A.append(once(False)); B.append(once(True))
print(f'  mandatory=False 中位数 {median(A):.0f} ms(最小 {min(A):.0f});mandatory=True 中位数 {median(B):.0f} ms(最小 {min(B):.0f})')
c.close(); px.close(); n.stop()
