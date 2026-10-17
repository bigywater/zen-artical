import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q1'); reset()
n = Node('q1'); n.start()
px = Proxy(n.amqp)

def show(ev, w=3):
    """把帧序列按“方向 + 通道: 名称”折叠打印"""
    out = []
    for d, ch, name, sz in ev:
        out.append(f'{d} ch{ch} {name}({sz}B)')
    for i in range(0, len(out), w): print('    ' + ' | '.join(out[i:i + w]))

print('== 一:连接建立的线上字节:经过代理看 AMQP 0-9-1 的握手,每个帧一行(C→S 是客户端发给 broker,S→C 反过来;chN 是通道号,0 号通道专门管连接本身)')
m = px.mark()
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port, heartbeat=60))
ev = px.names(m)
for d, ch, name, sz in ev: print(f'  {d}  ch{ch}  {name:<22}{sz:>5} 字节')
print(f'  握手共 {len(ev)} 帧,客户端发 {sum(1 for e in ev if e[0] == "C→S")} 帧、broker 发 {sum(1 for e in ev if e[0] == "S→C")} 帧;连接上协商出来的 heartbeat = {c._impl.params.heartbeat} 秒,frame_max = {c._impl.params.frame_max}')
print(f'  broker 在 Connection.Start 里告知的产品和版本: {c._impl.server_properties["product"].decode() if isinstance(c._impl.server_properties["product"], bytes) else c._impl.server_properties["product"]} {c._impl.server_properties["version"]};它支持的能力(capabilities)里,值为 True 的有: {sorted(k for k, v in c._impl.server_properties["capabilities"].items() if v is True)}')

print('== 二:一个 channel 上声明 exchange、queue、binding 再发布、消费,线上每一步对应哪个方法帧')
ch = c.channel()
m = px.mark()
ch.exchange_declare('x.demo', 'direct', durable=True)
ch.queue_declare('q.demo', durable=True)
ch.queue_bind('q.demo', 'x.demo', 'k1')
ch.basic_publish('x.demo', 'k1', b'hello')
m_get = px.mark()
mt, props, body = ch.basic_get('q.demo', auto_ack=False)
ch.basic_ack(mt.delivery_tag)
c.process_data_events(0.1)
ev = px.names(m)
for d, chn, name, sz in ev: print(f'  {d}  ch{chn}  {name:<22}{sz:>5} 字节')
print(f'  发布 5 个字节的消息 b"hello" 用了三个帧:Basic.Publish(方法帧)+ ContentHeader(属性与消息总长度)+ ContentBody(消息体);收到的 body = {body!r}')

print('== 三:连接与 channel 的关系:同一条 TCP 连接上开 3 个 channel,rabbitmqctl 看到的是 1 个连接、3 个 channel(通道号 1、2、3)')
chs = [c.channel() for _ in range(2)]
n.sh('list_connections name state channels peer_port')
n.sh('list_channels number consumer_count messages_unacknowledged')
print(f'  pika 里三个 channel 的编号: {[ch.channel_number] + [x.channel_number for x in chs]}')

print('== 四:channel 级错误只关 channel,连接不受影响;协议级错误才关连接')
try:
    chs[0].queue_declare('q.nonexistent', passive=True)
except Exception as e:
    print(f'  对不存在的队列做 passive declare → {type(e).__name__}: {e}')
print(f'  channel 1 状态: is_open={ch.is_open};出错的 channel: is_open={chs[0].is_open};连接: is_open={c.is_open}')
n.sh('list_channels number consumer_count')
closed = []
chs[1]._impl.add_on_close_callback(lambda ch_, reason: closed.append(str(reason)))
m = px.mark()
chs[1].basic_ack(999999)
time.sleep(0.5)
for _ in range(3): c.process_data_events(0.3)
print(f'  对没发过的 delivery_tag 做 ack → channel 被关: {closed}')
print(f'  线上帧: {px.names(m)}')
print(f'  之后:出错的 channel is_open={chs[1].is_open};连接 is_open={c.is_open}')
c2 = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); ch2 = c2.channel()
try:
    ch2.exchange_declare('x.bad', 'nosuchtype')
except Exception as e:
    print(f'  声明一个不存在的 exchange 类型 → {type(e).__name__}: {e}')
print(f'  (broker 发的是 Channel.Close,reply-code 406;只关出错的 channel,连接 c2.is_open={c2.is_open})')
for tag, kw in (('连一个不存在的 vhost', dict(virtual_host='nope')), ('用错误的密码', dict(credentials=pika.PlainCredentials('guest', 'bad')))):
    try: pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', n.amqp, **kw))
    except Exception as e: print(f'  {tag} → {type(e).__name__}: {str(e)[:110]}')
print('  这两种是连接级错误:broker 发 Connection.Close(或直接断开),整条 TCP 连接都没了,上面所有 channel 一起作废')

print('== 五:exchange、queue、binding 三者在 broker 里的样子:rabbitmqctl 直接列出来')
n.sh('list_exchanges name type durable auto_delete')
n.sh('list_queues name durable messages')
n.sh('list_bindings source_name source_kind destination_name destination_kind routing_key')

print('== 六:每个对象在 broker 里的开销:开 N 个连接、每个连接 1 个 channel;对比 1 个连接开 N 个 channel,看 Erlang 进程数和内存的增长')
def ev_(expr):
    r = n.ctl_raw('eval', expr); return int(r.stdout.strip())
def procs():
    return ev_('erlang:system_info(process_count).'), ev_('erlang:memory(total).')
for cc in (c, c2):
    try: cc.close()
    except Exception: pass
time.sleep(1.5)
p0, m0 = procs()
conns = [pika.BlockingConnection(n.params()) for _ in range(100)]
for x in conns: x.channel()
time.sleep(5); p1, m1 = procs()
for x in conns: x.close()
time.sleep(3); p2, m2 = procs()
one = pika.BlockingConnection(n.params()); chl = [one.channel() for _ in range(100)]
time.sleep(5); p3, m3 = procs()
print(f'  基线: Erlang 进程 {p0},内存 {m0 / 1048576:.1f} MiB')
print(f'  100 个连接 × 1 个 channel: 进程 {p1}(+{p1 - p0}),内存 {m1 / 1048576:.1f} MiB(+{(m1 - m0) / 1048576:.1f})')
print(f'  关掉后回到: 进程 {p2},内存 {m2 / 1048576:.1f} MiB')
print(f'  1 个连接 × 100 个 channel: 进程 {p3}(+{p3 - p2}),内存 {m3 / 1048576:.1f} MiB(+{(m3 - m2) / 1048576:.1f})')
one.close()
px.close(); n.stop()
