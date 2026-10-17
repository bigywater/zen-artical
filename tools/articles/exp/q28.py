import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q28'); reset()
n = Node('q28'); n.start()
c0 = n.conn(); ch0 = c0.channel()
for q, a in (('mc', {}), ('mq', {'x-queue-type': 'quorum'})):
    ch0.queue_declare(q, durable=True, arguments=a)
def tput(queue, size, N, persistent=True, rounds=3):
    """异步 confirm 发布 N 条,返回 (中位耗时 ms, 条/秒, MiB/秒)"""
    ts = []
    for _ in range(rounds):
        ch0.queue_purge(queue)
        ts.append(async_publish(n.amqp, queue, N, 1000, b'x' * size, persistent)[0])
    t = median(ts); return t, N / t * 1000, N * size / (t / 1000) / 1048576

print('== 一:消息大小与吞吐(经典队列,持久化,带 confirm 异步发布,在途 1000;每种大小发 30000 条或总量封顶 300 MB,3 轮取中位数)')
rows = []
for size in (10, 100, 1024, 10 * 1024, 100 * 1024, 1024 * 1024):
    N = min(30000, max(300, 300 * 1024 * 1024 // size))
    t, mps, mbps = tput('mc', size, N)
    rows.append((size, N, t, mps, mbps))
print('  消息大小      条数      耗时     条/秒     MiB/秒')
for size, N, t, mps, mbps in rows:
    lab = f'{size} B' if size < 1024 else (f'{size // 1024} KiB' if size < 1048576 else '1 MiB')
    print(f'  {lab:<10}{N:>8}{t:>9.0f} ms{mps:>10.0f}{mbps:>10.1f}')

print('== 二:同样的大小扫描,quorum 队列(3 副本的代价这里没有,单节点)')
rows2 = []
for size in (10, 100, 1024, 10 * 1024, 100 * 1024):
    N = min(30000, max(300, 300 * 1024 * 1024 // size))
    t, mps, mbps = tput('mq', size, N)
    rows2.append((size, N, t, mps, mbps))
print('  消息大小      条数      耗时     条/秒     MiB/秒')
for size, N, t, mps, mbps in rows2:
    lab = f'{size} B' if size < 1024 else f'{size // 1024} KiB'
    print(f'  {lab:<10}{N:>8}{t:>9.0f} ms{mps:>10.0f}{mbps:>10.1f}')

print('== 三:帧大小:一条 300 KiB 的消息要拆成多个 ContentBody 帧(frame_max 协商值)。经过代理发一条 300 KiB 的消息,看线上帧')
px = Proxy(n.amqp)
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); ch = c.channel()
print(f'  协商的 frame_max = {c._impl.params.frame_max}')
m = px.mark(); ch.basic_publish('', 'mc', b'x' * (300 * 1024))
ch.queue_declare('mc', passive=True)
ev = [e for e in px.names(m) if e[0] == 'C→S']
bodies = [e for e in ev if e[2] == 'ContentBody']
print(f'  一条 {300} KiB 的消息:Basic.Publish 1 个帧 + ContentHeader 1 个帧 + ContentBody {len(bodies)} 个帧(每个最大 {max(e[3] for e in bodies)} 字节,最后一个 {bodies[-1][3]} 字节)')
c.close(); px.close()

print('== 四:消息大小上限:max_message_size 默认 16 MiB(4.x),超过会被拒绝。发 1、16、17、130 MiB 的消息各一条')
def try_pub(size):
    cc = n.conn(); cch = cc.channel(); cch.confirm_delivery()
    try:
        cch.basic_publish('', 'mc', b'x' * size); r = '成功'
    except Exception as e: r = f'{type(e).__name__}: {str(e)[:110]}'
    try: cc.close()
    except Exception: pass
    return r
for s_ in (1, 16, 17, 130):
    print(f'  {s_} MiB: {try_pub(s_ * 1048576)}')
print('  $ rabbitmqctl eval "application:get_env(rabbit, max_message_size)."  →  ' + n.ctl_raw('eval', 'application:get_env(rabbit, max_message_size).').stdout.strip())

print('== 五:大消息对内存和磁盘的影响:在一个全新的节点上往经典队列放 1000 条 1 MiB 的持久化消息(共 1000 MiB),看 broker 进程 RSS 和数据目录的变化')
c0.close(); n.stop()
n2 = Node('q28b'); n2.start()
cc = n2.conn(); cch = cc.channel(); cch.queue_declare('big', durable=True)
pid = (n2.d / 'pid').read_text().strip()
def rss(): return int(subprocess.run(['ps', '-o', 'rss=', '-p', pid], capture_output=True, text=True).stdout.strip()) / 1024
r0 = rss(); d0 = n2.du()
async_publish(n2.amqp, 'big', 1000, 100, b'x' * 1048576, True)
time.sleep(3)
info = n2.qinfo('big', ('messages', 'messages_ram', 'memory'))
print(f'  放入前:broker RSS {r0:.0f} MiB,数据目录 {d0 / 1024:.1f} MiB')
print(f'  1000 条 × 1 MiB 之后:broker RSS {rss():.0f} MiB,数据目录 {n2.du() / 1024:.0f} MiB;队列 messages={info[0]} messages_ram={info[1]} 队列进程内存={info[2] / 1048576:.1f} MiB')
cc.close(); n2.stop()
