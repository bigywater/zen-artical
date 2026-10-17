import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
import urllib.request
tee('q31'); reset()
n = Node('q31', plugins=['rabbitmq_prometheus', 'rabbitmq_top'], conf=['prometheus.tcp.port = 9590', 'prometheus.tcp.ip = 127.0.0.1'])
n.start()
c = n.conn(); ch = c.channel(); ch.queue_declare('mq', durable=True)

print('== 一:管理 API 一览:/api/overview、/api/nodes、/api/queues/%2F/<q> 里有哪些顶层字段。注意:节点刚启动、队列刚建好时,统计还没收集,字段是不全的')
def keys_of(d, pats): return sorted(k for k in d.keys() if any(p_ in k for p_ in pats))
ov = n.api('/overview'); nd = n.api('/nodes')[0]; q = n.api('/queues/%2F/mq')
print('  /api/overview 顶层键: ' + ', '.join(sorted(k for k in ov.keys() if k in ('rabbitmq_version', 'erlang_version', 'cluster_name', 'queue_totals', 'object_totals', 'message_stats', 'listeners', 'node'))))
print(f'  刚建好队列时 /api/queues/%2F/mq 一共 {len(q)} 个键: {sorted(q.keys())}(没有 messages、consumers 这些——统计还没来)')
time.sleep(12)
nd = n.api('/nodes')[0]; q = n.api('/queues/%2F/mq')
print(f'  过了 12 秒再读:/api/nodes[0] 里和资源有关的键: ' + ', '.join(keys_of(nd, ('mem_used', 'mem_limit', 'fd_used', 'sockets_used', 'proc_used', 'disk_free', 'run_queue', 'uptime'))))
print(f'  /api/queues/%2F/mq 的键(节选): ' + ', '.join(keys_of(q, ('messages', 'consumers', 'memory', 'state', 'type', 'node', 'message_stats'))))

print('== 二:管理 API 的数据不是实时的:collect_statistics_interval 默认 5000 ms。发布 1000 条消息后,同时用 rabbitmqctl list_queues(实时)和管理 API 读 mq 的消息数,每 0.5 秒一次,看多久才一致')
for i in range(1000): ch.basic_publish('', 'mq', b'x', pika.BasicProperties(delivery_mode=2))
ch.queue_declare('mq', passive=True)
t0 = time.perf_counter(); rows = []; seen_api = None
while time.perf_counter() - t0 < 15:
    ctl = n.qinfo('mq', ('messages',))[0]; api = n.api('/queues/%2F/mq').get('messages')
    rows.append((round(time.perf_counter() - t0, 1), ctl, api))
    if api == 1000 and seen_api is None: seen_api = rows[-1][0]
    if seen_api and len(rows) > 3 and rows[-1][0] > seen_api: break
    time.sleep(0.5)
print(f'  采样 (秒, rabbitmqctl, 管理 API): {rows[:4]} … {rows[-2:]}')
print(f'  rabbitmqctl 一开始就是 1000;管理 API 在 {seen_api} 秒后才显示 1000')
print('  $ rabbitmqctl eval "application:get_env(rabbit, collect_statistics_interval)."  →  ' + n.ctl_raw('eval', 'application:get_env(rabbit, collect_statistics_interval).').stdout.strip())

print('== 三:速率:message_stats.publish_details.rate 是怎么算的?以 200 条/秒的速率发布 20 秒,每秒读一次管理 API 的 publish_details.rate 和 queue 的 messages')
c2 = n.conn(); ch2 = c2.channel(); ch2.queue_declare('rq', durable=True)
stop = threading.Event()
def feeder():
    t0 = time.perf_counter(); i = 0
    while not stop.is_set():
        while time.perf_counter() - t0 < i / 200: time.sleep(0.0005)
        ch2.basic_publish('', 'rq', b'x'); i += 1
th = threading.Thread(target=feeder, daemon=True); th.start()
trace = []
for s in range(20):
    time.sleep(1)
    qd = n.api('/queues/%2F/rq'); ms_ = qd.get('message_stats', {})
    trace.append((s + 1, round(ms_.get('publish_details', {}).get('rate', 0), 1), qd.get('messages')))
stop.set(); th.join(2)
print('  (第几秒, publish_details.rate, messages): ' + str(trace[::3]))
print(f'  最后 5 次读数的 rate: {[t[1] for t in trace[-5:]]}(真实速率 200 条/秒;rate 是按统计周期平滑出来的)')

print('== 四:Prometheus 插件:/metrics 在另一个端口(这里 9590),是在被抓取时才计算;看有多少行指标、关键指标的样子')
r = urllib.request.urlopen('http://127.0.0.1:9590/metrics', timeout=10).read().decode()
lines = [l for l in r.splitlines() if l and not l.startswith('#')]
print(f'  /metrics 返回 {len(r)} 字节,{len(lines)} 行指标(不含注释)')
for pat in ('rabbitmq_queue_messages_ready ', 'rabbitmq_queue_messages_unacked ', 'rabbitmq_connections ', 'rabbitmq_channels ', 'rabbitmq_process_resident_memory_bytes', 'rabbitmq_global_messages_received_total'):
    m = next((l for l in lines if l.split(' ')[0].split('{')[0] == pat.strip()), None)
    print(f'  {pat.strip():<44}→ {m[:90] if m else "(没有这行)"}')
t0 = time.perf_counter(); urllib.request.urlopen('http://127.0.0.1:9590/metrics', timeout=10).read(); print(f'  抓取一次 /metrics 用了 {ms(t0):.0f} ms')
t0 = time.perf_counter(); n.api('/overview'); print(f'  请求一次 /api/overview 用了 {ms(t0):.0f} ms')
r2 = urllib.request.urlopen('http://127.0.0.1:9590/metrics/per-object', timeout=20).read().decode()
print(f'  /metrics/per-object 返回 {len(r2)} 字节,默认 /metrics 返回 {len(r)} 字节(这里只有 3 个队列、2 条连接,差别很小;对象多了 per-object 会按对象数线性变大)')

print('== 五:告警里最该盯的几个数(都能从上面两种接口拿到):堆积 messages_ready、未确认 messages_unacknowledged、消费者数 consumers、内存/文件描述符/socket 占用')
nd = n.api('/nodes')[0]
print(f'  这个节点: mem_used {nd["mem_used"] / 1048576:.0f} MiB / mem_limit {nd["mem_limit"] / 1048576:.0f} MiB;proc_used {nd["proc_used"]} / proc_total {nd["proc_total"]}')
print(f'  macOS 上的 fd_used={nd["fd_used"]}、sockets_used={nd["sockets_used"]}、disk_free={nd.get("disk_free", "(没有)")}:这三个读数在这台机器上拿不到真实值(显示 0),监控它们要在 Linux 上做')
q = n.api('/queues/%2F/rq')
print(f'  队列 rq: messages_ready {q["messages_ready"]}, messages_unacknowledged {q["messages_unacknowledged"]}, consumers {q["consumers"]}')

print('== 六:统计的开销:启用管理插件(收集并聚合统计)与不启用时,发布 + 消费 20000 条的耗时(同一台机器、同样的客户端,3 轮中位数)')
c.close(); c2.close(); n.stop()
def bench(mgmt):
    nd_ = Node('q31m' if mgmt else 'q31n', mgmt=mgmt); nd_.start()
    cc = nd_.conn(); cch = cc.channel(); cch.queue_declare('b', durable=True)
    ts = []
    for _ in range(3):
        cch.queue_purge('b'); ts.append(async_publish(nd_.amqp, 'b', 20000, 1000, b'x' * 100, True)[0])
    cc.close(); nd_.stop(); return median(ts)
a = bench(True); b = bench(False)
print(f'  带管理插件: {a:.0f} ms;不带管理插件: {b:.0f} ms')
