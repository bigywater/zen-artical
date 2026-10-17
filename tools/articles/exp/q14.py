import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q14'); reset()
n = Node('q14'); n.start()
c = n.conn(); ch = c.channel()
def ev_(expr):
    r = n.ctl_raw('eval', expr); return int(r.stdout.strip())
def total_mem(): return ev_('erlang:memory(total).')
def mk(name, **a):
    ch.queue_delete(name); qdecl(ch, name, arguments=a)

print('== 一:x-queue-mode=lazy 在 4.3.6 里还被接受吗?效果是什么?声明、查看队列参数')
for mode in ('lazy', 'default'):
    try:
        mk(f'q.{mode}', **{'x-queue-mode': mode}); print(f'  x-queue-mode={mode}: 声明成功')
    except Exception as e: print(f'  x-queue-mode={mode}: {type(e).__name__}: {str(e)[:160]}'); c = n.conn(); ch = c.channel()
print(f'  rabbitmqctl list_queues 里的参数: {n.ctl("list_queues", "name", "arguments").splitlines()[-2:]}')
print(f'  list_queues 能看到的与内存相关的字段: messages_ram, message_bytes_ram, memory;是否有 queue_mode 一类的字段: {"mode" in n.ctl("list_queues", "--help")}')

print('== 二:往队列里放 100000 条 1 KB 消息(没有消费者),各队列在 broker 里实际占多少内存、有多少消息在内存里(messages_ram)')
def load(name, **a):
    mk(name, **a)
    body = b'x' * 1024
    for i in range(100000): ch.basic_publish('', name, body, pika.BasicProperties(delivery_mode=2))
    ch.queue_declare(name, passive=True); time.sleep(3)
    info = n.qinfo(name, ('messages', 'messages_ram', 'message_bytes_ram', 'message_bytes_persistent', 'memory'))
    return info
base = total_mem()
rows = []
for name, a in (('classic.default', {}), ('classic.lazy', {'x-queue-mode': 'lazy'})):
    m0 = total_mem(); info = load(name, **a); m1 = total_mem()
    rows.append((name, info, (m1 - m0) / 1048576))
print('  队列               messages  messages_ram  message_bytes_ram  队列进程内存    broker 总内存增量')
for name, info, dm in rows:
    print(f'  {name:<18}{info[0]:>8}{info[1]:>14}{info[2] / 1048576:>14.1f} MiB{info[4] / 1048576:>12.1f} MiB{dm:>12.1f} MiB')

print('== 三:quorum 队列同样放 100000 条 1 KB 消息')
m0 = total_mem(); info = load('quorum.q', **{'x-queue-type': 'quorum'}); m1 = total_mem()
print(f'  quorum.q: messages={info[0]} messages_ram={info[1]} message_bytes_ram={info[2] / 1048576:.1f} MiB 队列进程内存={info[4] / 1048576:.1f} MiB broker 总内存增量={(m1 - m0) / 1048576:.1f} MiB')

print('== 四:消费者来了之后内存怎么变:100000 条的 classic 队列,开一个消费者 prefetch=100、消费一小会儿(至少 1000 条)后看内存')
cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=100)
cnt = [0]
cch.basic_consume('classic.default', lambda chn, m, p, b: (cnt.__setitem__(0, cnt[0] + 1), chn.basic_ack(m.delivery_tag)))
while cnt[0] < 1000: cc.process_data_events(0.1)
time.sleep(1)
info = n.qinfo('classic.default', ('messages', 'messages_ram', 'message_bytes_ram', 'memory'))
print(f'  消费者确认了 {100000 - info[0]} 条后: messages={info[0]} messages_ram={info[1]} message_bytes_ram={info[2] / 1048576:.2f} MiB 队列进程内存={info[3] / 1048576:.1f} MiB')
cc.close()

print('== 五:重启后恢复:带 100000 条持久化消息的队列,正常重启 broker 到可用要多久,内存多少')
c.close()
t0 = time.perf_counter(); n.restart(); t_restart = time.perf_counter() - t0
info = n.qinfo('classic.default', ('messages', 'messages_ram', 'memory'))
print(f'  重启(关闭 + 启动 + await_startup)总共 {t_restart:.1f} s;重启后 classic.default: messages={info[0]} messages_ram={info[1]} 队列进程内存={info[2] / 1048576:.1f} MiB')
c = n.conn(); ch = c.channel()
t0 = time.perf_counter(); got = 0
while got < 100: mt, p, b = ch.basic_get('classic.default', auto_ack=True); got += 1
print(f'  取 100 条用了 {ms(t0):.0f} ms(重启后消息要从磁盘读)')
c.close(); n.stop()
