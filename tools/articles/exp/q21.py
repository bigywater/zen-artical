import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q21'); reset()
n = Node('q21'); n.start()
px = Proxy(n.amqp)
def ev_(expr): return int(n.ctl_raw('eval', expr).stdout.strip())

print('== 一:channel 数的上限:broker 在 Connection.Tune 里给出 channel_max,客户端据此协商;看握手里的数值,以及开到上限之后再开一个会怎样')
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port))
print(f'  协商后连接上的 channel_max = {c._impl.params.channel_max}(pika 默认请求 0 = 不限制,由 broker 在 Connection.Tune 里给出的 2047 决定)')
chs = []
try:
    for i in range(3000): chs.append(c.channel())
    print('  开了 3000 个 channel 都成功')
except Exception as e:
    print(f'  成功开到第 {len(chs)} 个 channel 后,下一个失败: {type(e).__name__}: {str(e)[:150]}')
print(f'  list_connections 的 channels 列: {n.ctl("list_connections", "channels").splitlines()[-1]}')
for x in chs: 
    try: x.close()
    except Exception: pass
try: c.close()
except Exception: pass
px.close()

print('== 二:channel 的开销随数量线性增长:一条连接上开 100 / 1000 / 2000 个 channel,Erlang 进程数和内存的增量(每个 channel 约占多少)')
base_p = ev_('erlang:system_info(process_count).'); base_m = ev_('erlang:memory(total).')
c = n.conn(); chs = []
rows = []
for target in (100, 1000, 2000):
    while len(chs) < target: chs.append(c.channel())
    time.sleep(2)
    p = ev_('erlang:system_info(process_count).'); m = ev_('erlang:memory(total).')
    rows.append((target, p - base_p, (m - base_m) / 1048576))
print('  channel 数  Erlang 进程增量  内存增量     每个 channel')
for t, dp, dm in rows: print(f'  {t:<10}{dp:>12}{dm:>12.1f} MiB{dm * 1024 / t:>10.1f} KiB / {dp / t:.1f} 进程')
for x in chs:
    try: x.close()
    except Exception: pass
c.close(); time.sleep(1)

print('== 三:一条连接上开更多 channel 能不能提高吞吐?同一个进程里 1 / 4 / 16 / 64 个 channel 轮流发布 100000 条 100 字节消息(不开 confirm,3 轮中位数)')
def bench_multi(nch, N=100000):
    cc = n.conn(); cch = [cc.channel() for _ in range(nch)]
    cch[0].queue_declare(f'mq{nch}', durable=True); cch[0].queue_purge(f'mq{nch}')
    body = b'x' * 100
    t0 = time.perf_counter()
    for i in range(N): cch[i % nch].basic_publish('', f'mq{nch}', body)
    cch[0].queue_declare(f'mq{nch}', passive=True); e = ms(t0); cc.close(); return e
res3 = {k: median([bench_multi(k) for _ in range(3)]) for k in (1, 4, 16, 64)}
for k, v in res3.items(): print(f'  1 个连接 × {k:>2} 个 channel: {v:.0f} ms  {100000 / v * 1000:.0f} 条/秒')

print('== 四:加连接(每个客户端进程一条连接)能不能提高总吞吐:1 / 2 / 4 / 8 个客户端进程,各自 1 条连接,各发 50000 条到自己的队列')
def run_workers(k, N=50000, nchan=1):
    t0 = time.perf_counter()
    ps = [subprocess.Popen([sys.executable, str(HERE / 'qwork.py'), str(n.amqp), f'wq{k}.{i}', str(N), str(nchan)], stdout=subprocess.PIPE, text=True) for i in range(k)]
    outs = [float(p.communicate()[0].strip()) for p in ps]
    return ms(t0), max(outs)
res4 = {}
for k in (1, 2, 4, 8):
    xs = [run_workers(k) for _ in range(3)]
    res4[k] = median(x[1] for x in xs)
for k, v in res4.items(): print(f'  {k} 个连接(各 50000 条,共 {50000 * k} 条): 最慢的一个用了 {v:.0f} ms;合计 {50000 * k / v * 1000:.0f} 条/秒')
n.stop()
