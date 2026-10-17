import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q15'); reset()
nodes = cluster('q15n', 3)
n1, n2, n3 = nodes
def nm_(t): return t.replace('q15n', 'n')
def short(out, keep):
    return '\n'.join(l for l in out.splitlines() if any(k in l for k in keep))

print('== 一:三个节点组成集群后 rabbitmqctl cluster_status 的关键部分(磁盘节点、正在运行的节点)')
out = n1.ctl('cluster_status').splitlines()
for k, l in enumerate(out):
    if l in ('Disk Nodes', 'Running Nodes', 'Versions'):
        print('  ' + l)
        for m in out[k + 2:]:
            if not m.strip(): break
            print('    ' + nm_(m.strip()))

print('== 二:在 n1 上声明经典队列和 quorum 队列,各放 1000 条持久化消息;list_queues 看类型、leader、成员')
c1 = n1.conn(); ch1 = c1.channel()
ch1.queue_declare('cq', durable=True, arguments={'x-queue-type': 'classic'})
ch1.queue_declare('qq', durable=True, arguments={'x-queue-type': 'quorum'})
ch1.confirm_delivery()
for q in ('cq', 'qq'):
    for i in range(1000): ch1.basic_publish('', q, f'm{i}'.encode(), pika.BasicProperties(delivery_mode=2))
time.sleep(1)
out = n1.ctl('list_queues', 'name', 'type', 'leader', 'members', 'online', 'messages')
for l in out.splitlines()[-3:]: print('  ' + l.replace('q15n', 'n'))

print('== 三:classic 队列的镜像(ha-mode)在 4.3.6 里已经移除:设置 ha-mode=all 的策略,看队列有没有变成多副本')
out = n1.ctl('set_policy', 'ha-all', '^cq$', '{"ha-mode":"all","ha-sync-mode":"automatic"}', '--apply-to', 'queues')
print('  $ rabbitmqctl set_policy ha-all "^cq$" \'{"ha-mode":"all","ha-sync-mode":"automatic"}\' --apply-to queues')
for l in out.splitlines()[1:]:
    if l.strip(): print('    ' + l)
time.sleep(1.5)
print('  list_policies: ' + ' | '.join(l.replace(chr(9), ' ') for l in n1.ctl('list_policies').splitlines()[-1:]))
out = n1.ctl('list_queues', 'name', 'type', 'leader', 'members', 'online')
print('  策略生效后 cq 仍是: ' + [l for l in out.splitlines() if l.startswith('cq')][0].replace('q15n', 'n'))
dep = n1.ctl_raw('--quiet', 'list_deprecated_features', '--formatter', 'json').stdout
import json as _j
print('  classic_queue_mirroring 的状态: ' + str([(d['deprecation_phase'], d['state']) for d in _j.loads(dep) if d['name'] == 'classic_queue_mirroring']))
logs = [l.split('] ', 1)[-1][:170] for l in n1.logs('mirror|ha-mode|ha-sync')]
print('  broker 日志里关于镜像的行: ' + (' / '.join(logs[:2]) if logs else '(无)'))
n1.ctl('clear_policy', 'ha-all')

print('== 四:kill -9 掉 n1(经典队列所在的节点,也是 quorum 队列声明时的 leader),从 n2 看两种队列还能不能用')
t_kill = time.perf_counter(); n1.stop(kill=True)
ok_at = None
while time.perf_counter() - t_kill < 60:
    try:
        ch2 = n2.conn().channel(); ch2.confirm_delivery(); ch2.basic_publish('', 'qq', b'after-kill', pika.BasicProperties(delivery_mode=2)); ok_at = (time.perf_counter() - t_kill) * 1000; break
    except Exception as e: time.sleep(0.02)
print(f'  quorum 队列 qq: 杀掉 n1 后第一次成功发布(带 confirm)在 {ok_at:.0f} ms 之后')
out = n2.ctl('list_queues', 'name', 'type', 'leader', 'members', 'online', 'messages')
for l in out.splitlines()[-3:]: print('  ' + l.replace('q15n', 'n'))
def try_(fn):
    try: fn(); return '成功'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:130]}'
t0 = time.perf_counter()
r = try_(lambda: n2.conn().channel().queue_declare('cq', passive=True))
print(f'  classic 队列 cq(它只在 n1 上,n1 已死): {r};这个调用等了 {time.perf_counter() - t0:.1f} s 才失败')
got = 0
chx = n2.conn().channel()
while True:
    mt, p, b = chx.basic_get('qq', auto_ack=True)
    if mt is None: break
    got += 1
print(f'  从 n2 把 qq 取空:共 {got} 条(1000 条原有 + 1 条 kill 之后发的)')

print('== 五:重启 n1:classic 队列回来,消息还在;quorum 队列的 n1 副本作为 follower 追上')
n1.start()
time.sleep(3)
out = n1.ctl('list_queues', 'name', 'type', 'leader', 'members', 'online', 'messages')
for l in out.splitlines()[-3:]: print('  ' + l.replace('q15n', 'n'))
chc = n1.conn().channel(); mt, p, b = chc.basic_get('cq', auto_ack=True); print(f'  从 cq 取一条: {b.decode()!r}(重启后 classic 队列的持久消息还在)')

print('== 六:复制的代价:同一个集群里,带 confirm 异步发布 20000 条 100 字节的持久化消息(在途 1000),classic(1 副本)与 quorum(3 副本)各 3 轮取中位数')
cc = n2.conn().channel()
for q, a in (('bench.classic', {'x-queue-type': 'classic'}), ('bench.quorum', {'x-queue-type': 'quorum'})):
    cc.queue_declare(q, durable=True, arguments=a)
res = {}
for q in ('bench.classic', 'bench.quorum'):
    ts = []
    for _ in range(3):
        el, a, nk, ok = async_publish(n2.amqp, q, 20000); ts.append(el); cc.queue_purge(q)
    res[q] = median(ts)
for q, v in res.items(): print(f'  {q:<14}{v:>7.0f} ms  {20000 / v * 1000:>7.0f} 条/秒')
for nd in nodes: nd.stop(kill=True)
