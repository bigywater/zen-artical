import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q7'); reset()
n = Node('q7', conf=['deprecated_features.permit.transient_nonexcl_queues = true']); n.start()
def conn(): 
    c = n.conn(); return c, c.channel()
def count_all():
    return {k: v[0] for k, v in n.qinfo(None, ('messages',)).items()}

print('== 一:4.x 默认不再允许“非持久、非排他”的队列;不改配置时声明会被拒(这一篇后面的实验用 deprecated_features.permit.transient_nonexcl_queues = true 打开)')
n2 = Node('q7b'); n2.start()
c2 = n2.conn(); ch2 = c2.channel()
try: ch2.queue_declare('tq', durable=False)
except Exception as e: print(f'  默认配置下 durable=False 的队列 → {type(e).__name__}: (541, {str(e).split(chr(92) + "n")[0][:90]!r}…) —— 注意是整条连接被关,不只是 channel')
c2 = n2.conn(); ch2 = c2.channel()
ch2.queue_declare('tq-excl', durable=False, exclusive=True); print('  exclusive=True 的非持久队列 → 成功(随连接消失)')
ch2.queue_declare('', durable=False, exclusive=True, auto_delete=True); print('  服务器命名 + exclusive + auto_delete 的队列 → 成功')
c2.close()
n2.stop()

print('== 二:2×2 矩阵 + 重启:队列 durable / 非 durable × 消息 persistent(delivery_mode=2)/ transient;各发 100 条,然后正常关闭 broker(rabbitmqctl shutdown)再启动,各队列还剩多少条')
c, ch = conn()
combos = [('dq.p', True, 2), ('dq.t', True, 1), ('tq.p', False, 2), ('tq.t', False, 1)]
for q, dur, dm in combos:
    ch.queue_declare(q, durable=dur); ch.confirm_delivery() if False else None
    for i in range(100): ch.basic_publish('', q, f'm{i}'.encode(), pika.BasicProperties(delivery_mode=dm))
ch.queue_declare('dq.p', passive=True)
print(f'  重启前: {count_all()}')
c.close(); n.restart()
print(f'  正常重启后: {count_all()}')
print('  规则:非持久队列重启后连队列本身都没了;持久队列里只有 persistent 消息还在,transient 消息没了(哪怕它所在的队列还在)')

print('== 三:kill -9 的结果(进程被杀,不走关闭流程):持久队列 + persistent 消息,发 5000 条,分三种情形杀:发完马上杀 / 等 confirm 全部回来再杀 / 发完等 2 秒再杀')
def kill_test(mode):
    c, ch = conn(); ch.queue_declare('kq', durable=True); ch.queue_purge('kq'); c.close()
    c, ch = conn()
    if mode == 'confirm': ch.confirm_delivery()
    props = pika.BasicProperties(delivery_mode=2)
    if mode == 'confirm':
        for i in range(5000): ch.basic_publish('', 'kq', b'x' * 100, props)   # 每条阻塞等到 ack
    else:
        for i in range(5000): ch.basic_publish('', 'kq', b'x' * 100, props)
        c._impl.ioloop if False else None
    if mode == 'wait2': time.sleep(2)
    n.stop(kill=True)
    try: c.close()
    except Exception: pass
    n.start()
    return count_all().get('kq')
for mode, desc in (('immediate', '发完马上 kill -9(不等任何确认)'), ('confirm', '每条等 confirm、全部回来后 kill -9'), ('wait2', '发完等 2 秒再 kill -9')):
    print(f'  {desc}: 重启后 kq 里有 {kill_test(mode)} 条(发了 5000 条)')
print('  注意:kill -9 只杀进程,操作系统页缓存里的数据不会丢;真正的掉电丢数据这里测不到')

print('== 四:磁盘上的样子:发 20000 条 1 KB 消息到持久队列,persistent 与 transient 各一次,看 broker 数据目录的增长')
def du_k(): return n.du()
c, ch = conn()
for q in ('kq', 'dq.p', 'dq.t'): ch.queue_delete(q)
base = du_k()
res = {}
for name, dm in (('persistent', 2), ('transient', 1)):
    q = f'disk.{name}'; ch.queue_declare(q, durable=True)
    b0 = du_k()
    for i in range(20000): ch.basic_publish('', q, b'x' * 1024, pika.BasicProperties(delivery_mode=dm))
    ch.queue_declare(q, passive=True); time.sleep(2)
    res[name] = du_k() - b0
print(f'  基线 {base} KiB;persistent 20000 条 × 1 KB 后增长 {res["persistent"]} KiB;transient 20000 条 × 1 KB 后增长 {res["transient"]} KiB')
vh = next((n.d / 'mnesia' / n.nodename / 'msg_stores' / 'vhosts').iterdir())
def sub(p): return int(subprocess.run(f'du -sk "{p}" | cut -f1', shell=True, capture_output=True, text=True).stdout.split()[0])
print('  vhost 数据目录(msg_stores/vhosts/<id>/)下各子目录的大小(KiB): ' + ', '.join(f'{x.name}={sub(x)}' for x in sorted(vh.iterdir()) if x.is_dir()))
qd = next((vh / 'queues').iterdir(), None)
print('  每个队列一个子目录(队列索引文件 .qi):队列目录数 = ' + str(len(list((vh / 'queues').iterdir()))) + ';其中一个队列目录里的文件: ' + str(sorted(f.name[-3:] for f in qd.iterdir()))) if qd else None
c.close()

print('== 五:durable 队列绑在非 durable 的 exchange 上,重启后:队列在不在?exchange 在不在?绑定在不在?')
c, ch = conn()
ch.exchange_declare('x.transient', 'direct', durable=False); ch.exchange_declare('x.durable', 'direct', durable=True)
ch.queue_declare('dq.bind', durable=True); ch.queue_declare('tq.bind', durable=False)
for q in ('dq.bind', 'tq.bind'):
    for x in ('x.transient', 'x.durable'): ch.queue_bind(q, x, 'k')
def binds(): return sorted(l.replace(chr(9), ' → ') for l in n.ctl('list_bindings', 'source_name', 'destination_name').splitlines() if ('x.' in l) and ('bind' in l))
def exs(): return sorted(l.replace(chr(9), '(durable=') + ')' for l in n.ctl('list_exchanges', 'name', 'durable').splitlines() if l.startswith('x.'))
print(f'  重启前 exchange: {exs()};绑定: {binds()}')
c.close(); n.restart()
print(f'  正常重启后 exchange: {exs()};绑定: {binds()}')
print(f'  重启后的队列: {sorted(n.qinfo(None, ("durable",)))}')
c, ch = conn(); ch.confirm_delivery()
ch.basic_publish('x.transient', 'k', b'after-restart', mandatory=True)
print(f'  向 x.transient 发布并路由: dq.bind 里现在有 {n.qinfo("dq.bind", ("messages",))[0]} 条')
try: c.close()
except Exception: pass
n.stop(kill=True); n.start()
print(f'  再 kill -9 重启后 exchange: {exs()};绑定: {binds()}')
n.stop()
