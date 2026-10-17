import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q20'); reset()
n = Node('q20'); n.start()
def ev_(expr): return int(n.ctl_raw('eval', expr).stdout.strip())
def rss_mib():
    pid = (n.d / 'pid').read_text().strip()
    return int(subprocess.run(['ps', '-o', 'rss=', '-p', pid], capture_output=True, text=True).stdout.strip()) / 1024
def mem(): return rss_mib() * 1048576
def alarms(): return n.ctl('alarms', tool='rabbitmq-diagnostics').strip() or '(无)'
c = n.conn(); ch = c.channel()
ch.queue_declare('fq', durable=True, arguments={'x-queue-type': 'quorum'})
body = b'x' * 1024

print('== 一:内存水位线:把 vm_memory_high_watermark 设成“当前使用量 + 40 MiB”,往 quorum 队列一直发布 1 KB 的消息,看什么时候被阻塞')
base = mem()
limit = int(base + 40 * 1048576)
st = [l.strip() for l in n.ctl('status').splitlines() if any(k in l for k in ('Total memory used', 'Calculation strategy', 'Memory high watermark setting'))]
print('  rabbitmqctl status 里的内存部分: ' + ' | '.join(st))
out = n.ctl('set_vm_memory_high_watermark', 'absolute', str(limit))
print(f'  当前 broker 进程内存(RSS,告警比较的就是这个口径)约 {base / 1048576:.1f} MiB;$ rabbitmqctl set_vm_memory_high_watermark absolute {limit // 1048576}MiB(当前 + 40 MiB)')
events = []
pc = pika.BlockingConnection(n.params())
pc.add_on_connection_blocked_callback(lambda conn, f: events.append(('blocked', time.perf_counter(), str(f.method.reason))))
pc.add_on_connection_unblocked_callback(lambda conn, f: events.append(('unblocked', time.perf_counter(), '')))
pch = pc.channel()
sent = 0; t0 = time.perf_counter(); stall = None
res = {}
def publisher():
    global sent
    try:
        while not res.get('stop'):
            for _ in range(50):
                pch.basic_publish('', 'fq', body, pika.BasicProperties(delivery_mode=2)); sent += 1
            pc.process_data_events(0)     # 让 pika 有机会处理 broker 发来的 Connection.Blocked / Unblocked
    except Exception as e: res['err'] = type(e).__name__
th = threading.Thread(target=publisher, daemon=True); th.start()
# 监视:每 0.2 s 记发了多少条、内存、告警
trace = []
for i in range(60):
    time.sleep(0.2)
    trace.append((round(time.perf_counter() - t0, 1), sent, round(mem() / 1048576, 1)))
    if len(trace) > 8 and trace[-1][1] == trace[-4][1] and trace[-1][1] > 0: break
print('  (秒, 已发条数, 内存 MiB) 的采样: ' + str(trace[::3] + ([trace[-1]] if trace[-1] not in trace[::3] else [])))
print(f'  发布线程停在 {sent} 条(之后不再前进);rabbitmq-diagnostics alarms:')
for l in alarms().splitlines(): print('    ' + l)
print(f'  list_connections 的 state: {n.ctl("list_connections", "state").splitlines()[-2:]}')

print('== 二:被阻塞时,客户端收到什么?Connection.Blocked(带原因);消费者不受影响——消费掉一部分,内存回落,告警解除,Connection.Unblocked')
print(f'  pika 回调记录: {[(e[0], e[2]) for e in events]}')
cc = n.conn(); cch = cc.channel(); got = 0
cch.basic_qos(prefetch_count=500)
def cb(chn_, m, p, b):
    global got
    got += 1; chn_.basic_ack(m.delivery_tag, multiple=True) if got % 100 == 0 else None
cch.basic_consume('fq', cb)
t1 = time.perf_counter(); freed = None
while time.perf_counter() - t1 < 40:
    cc.process_data_events(0.2)
    if any(e[0] == 'unblocked' for e in events) and freed is None: freed = (round(time.perf_counter() - t1, 1), got, round(mem() / 1048576, 1))
    if freed and time.perf_counter() - t1 > freed[0] + 1.5: break
print(f'  消费者运行中收到 Unblocked 的时刻(消费开始后秒数, 已消费条数, 内存 MiB): {freed}')
print(f'  事件序列: {[e[0] for e in events]};发布线程之后又继续发了 {sent} 条(累计)')
res['stop'] = True; cc.close()
try: pc.close()
except Exception: pass

print('== 三:磁盘水位线:disk_free_limit 设得比实际剩余空间大,所有发布者被阻塞(与内存告警同样的 Connection.Blocked)')
n.ctl('set_vm_memory_high_watermark', '0.6')
st = [l.strip() for l in n.ctl('status').splitlines() if any(k in l for k in ('Low free disk space watermark', 'Free disk space'))]
print('  rabbitmqctl status 里的磁盘部分: ' + ' | '.join(st))
logs = [l.split('] ', 1)[-1][:160] for l in n.logs('disk|Disk')][:4]
print('  broker 日志里关于磁盘监控的行:')
for l in logs: print('    ' + l)
free = int(subprocess.run(f"df -k {n.d} | tail -1 | awk '{{print $4}}'", shell=True, capture_output=True, text=True).stdout.strip()) * 1024
n.ctl('set_disk_free_limit', str(free + 5 * 1024**3))
time.sleep(15)
print(f'  操作系统 df 看到数据目录所在卷剩余 {free / 1024**3:.1f} GiB;把 disk_free_limit 设成比它多 5 GiB 后等 15 秒,rabbitmq-diagnostics alarms:')
for l in alarms().splitlines(): print('    ' + l)
n.ctl('set_disk_free_limit', '50MB')
print('  这台 macOS 上 broker 读不到磁盘剩余空间(Free disk space: not available),磁盘告警在这里无法触发,所以这一节只能验证到这里')

print('== 四:另一种流控:每条连接的信用流控(credit flow)。4 个全速发布的连接往一个经典队列发(持久化消息),在 broker 里用一次 eval 以 20 ms 间隔采样 200 次连接的 state')
ch.queue_delete('fq'); ch.queue_declare('fq4', durable=True); c.close()
n.ctl('set_vm_memory_high_watermark', '0.6')
stop = threading.Event(); cnt = [0]
def pub3():
    cc3 = n.conn(); c3 = cc3.channel()
    try:
        while not stop.is_set():
            c3.basic_publish('', 'fq4', body, pika.BasicProperties(delivery_mode=2)); cnt[0] += 1
    except Exception: pass
ths = [threading.Thread(target=pub3, daemon=True) for _ in range(4)]
for t in ths: t.start()
time.sleep(1)
expr = "F = fun F(0, Acc) -> Acc; F(N, Acc) -> L = [S || [{state, S}] <- rabbit_networking:connection_info_all([state])], timer:sleep(20), F(N-1, L ++ Acc) end, lists:foldl(fun(S, M) -> maps:update_with(S, fun(X) -> X+1 end, 1, M) end, #{}, F(200, []))."
r = n.ctl_raw('eval', expr, timeout=60).stdout.strip()
stop.set(); time.sleep(0.5)
print(f'  200 次采样累计(每次采样 4 条发布连接 + 偶尔 CLI 连接)看到的 state: {r};这段时间共发布 {cnt[0]} 条')
n.stop()
