import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q24'); reset()
n = Node('q24', conf=['consumer_timeout = 10000']); n.start()
def ev(e): return n.ctl_raw('eval', e, timeout=60).stdout.strip()
def err(fn):
    try: fn(); return '成功'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:170]}'

print('== 一:consumer_timeout 的默认值与配置:默认 1800000 ms(30 分钟);这里在 rabbitmq.conf 里改成 10000 ms')
n0 = Node('q24d'); n0.start()
print('  不改配置的节点:  $ rabbitmqctl eval "application:get_env(rabbit, consumer_timeout)."  →  ' + n0.ctl_raw('eval', 'application:get_env(rabbit, consumer_timeout).').stdout.strip())
n0.stop()
print('  改了配置的节点:  同样的命令  →  ' + ev('application:get_env(rabbit, consumer_timeout).'))

print('== 二:单个队列的覆盖:队列参数 x-consumer-timeout(经典队列 vs quorum 队列),以及 policy consumer-timeout')
c = n.conn(); ch = c.channel()
print('  经典队列带 x-consumer-timeout=2000: ', err(lambda: n.conn().channel().queue_declare('ctc', durable=True, arguments={'x-consumer-timeout': 2000})))
print('  quorum 队列带 x-consumer-timeout=2000: ', err(lambda: n.conn().channel().queue_declare('ctq', durable=True, arguments={'x-queue-type': 'quorum', 'x-consumer-timeout': 2000})))
print('  $ rabbitmqctl set_policy ct-pol "^ctp$" \'{"consumer-timeout":3000}\' --apply-to queues  →  ' + (n.ctl('set_policy', 'ct-pol', '^ctp$', '{"consumer-timeout":3000}', '--apply-to', 'queues').replace('\n', ' ')[-90:]))
print('  list_policies: ' + n.ctl('list_policies').splitlines()[-1].replace(chr(9), ' | '))

print('== 三:一个收到消息却不确认的消费者,超时是 10 s;等 7 分钟看 channel 会不会被 broker 关掉(经典队列与 quorum 队列各一个消费者,prefetch=10,心跳 60 s 正常)')
res = {}
def trial(name, args):
    cc = pika.BlockingConnection(n.params()); chh = cc.channel(); chh.queue_declare(name, durable=True, arguments=args); chh.queue_purge(name); chh.basic_publish('', name, b'm')
    chh.basic_qos(prefetch_count=10)
    box = {}; closed = []
    chh.basic_consume(name, lambda chn, m, p, b: box.setdefault('t', time.perf_counter()))
    chh._impl.add_on_close_callback(lambda chh_, r: closed.append((time.perf_counter(), str(r))))
    t0 = time.perf_counter()
    while not closed and time.perf_counter() - t0 < 420: cc.process_data_events(0.1)
    res[name] = (round(closed[0][0] - box['t'], 1), closed[0][1][:200]) if closed else None
    res[name + '.unacked'] = n.qinfo(name)
ths = [threading.Thread(target=trial, args=('ct.classic', {})), threading.Thread(target=trial, args=('ct.quorum', {'x-queue-type': 'quorum'}))]
for t in ths: t.start()
for t in ths: t.join(450)
for name in ('ct.classic', 'ct.quorum'):
    r = res.get(name)
    print(f'  {name}: ' + (f'收到消息后 {r[0]} s channel 被关: {r[1]}' if r else f'420 s 内 channel 没有被关;此时队列 (ready, unacked) = {res.get(name + ".unacked")}'))
logs = [l.split('] ', 1)[-1][:150] for l in n.logs('consumer|delivery acknowledgement')][:3]
print(f'  broker 日志里和消费者超时有关的行: {logs or "(无)"}')
print('  结论(仅限这次实验):consumer_timeout=10 s 的配置读到了,可是 7 分钟内没有观察到 broker 因为未确认而关闭 channel;我没有找到原因——文档说这个检查是周期性的(以分钟计),可是 7 分钟已经跨过了好几个周期')
n.stop()
