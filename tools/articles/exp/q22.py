import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q22'); reset()
n = Node('q22'); n.start()

print('== 一:心跳时间怎么协商:broker 默认 60 秒(Connection.Tune 里提出),客户端回 TuneOk 时给自己的值。客户端请求 None / 0 / 5 / 30 / 120 时最终生效的值')
for req in (None, 0, 5, 30, 120):
    kw = {} if req is None else {'heartbeat': req}
    c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', n.amqp, **kw))
    time.sleep(0.3)
    out = n.ctl('list_connections', 'timeout').splitlines()[-1]
    print(f'  客户端请求 heartbeat={req!s:<5}→ list_connections 的 timeout 列(协商结果): {out}')
    c.close()

print('== 二:心跳帧在线上的样子:经过代理,heartbeat=2 的空闲连接,10 秒里双方各发了多少个 Heartbeat 帧、间隔多少')
px = Proxy(n.amqp)
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port, heartbeat=2))
m = px.mark(); t0 = time.perf_counter()
while time.perf_counter() - t0 < 10: c.process_data_events(0.2)
hb = [e for e in px.events[m:] if e[3] == 'Heartbeat']
for d in ('C→S', 'S→C'):
    ts = [round(e[0] - px.events[m][0], 1) if False else round(e[0], 2) for e in hb if e[1] == d]
    gaps = [round(b - a, 2) for a, b in zip(ts, ts[1:])]
    print(f'  {d}: {len(ts)} 个 Heartbeat,每个 {hb[0][4]} 字节,相邻间隔(秒): {gaps}')
print('  间隔约 1 秒 = heartbeat 超时的一半(2 s ÷ 2);空闲时双方都在发,忙的时候别的帧也算“活着”,不再另发')

print('== 三:对端悄悄消失(网络黑洞)时,broker 多久发现?代理停止转发但不断开 TCP。沿用上面 heartbeat=2 的那条连接,记下黑洞开始到 broker 关闭连接的时间')
log0 = len(n.logs())
px.hole = True; t_hole = time.perf_counter()
seen = None
while time.perf_counter() - t_hole < 30:
    L = n.logs('missed heartbeats')
    if L: seen = time.perf_counter() - t_hole; break
    time.sleep(0.1)
print(f'  heartbeat=2 的连接,黑洞开始后 {seen:.1f} 秒,broker 日志出现: ' + (n.logs('missed heartbeats')[-1].split('] ', 1)[-1][-150:] if seen else '(无)'))
print(f'  list_connections 此时: {n.ctl("list_connections", "state").splitlines()[-1:] or ["(无连接)"]}')
try: c.close()
except Exception: pass
px.close()

print('== 四:不开心跳(heartbeat=0)时的黑洞:broker 完全发现不了,连接一直留在 list_connections 里')
px = Proxy(n.amqp)
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port, heartbeat=0))
px.hole = True
time.sleep(25)
print(f'  heartbeat=0,黑洞 25 秒后 list_connections: {n.ctl("list_connections", "state", "timeout").splitlines()[-2:]}(连接还在,state=running,timeout=0)')
px.close()

print('== 五:最常见的坑:客户端线程忙着做别的事(不调用 process_data_events),pika 的 BlockingConnection 不会自己发心跳。heartbeat=2,处理一个耗时 8 秒的任务,期间不收发')
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', n.amqp, heartbeat=2))
ch = c.channel()
n.logs()  # 刷新
k0 = len(n.logs('missed heartbeats'))
time.sleep(8)
print(f'  8 秒后 broker 日志里新增的 missed heartbeats 行数: {len(n.logs("missed heartbeats")) - k0};list_connections: {n.ctl("list_connections", "state").splitlines()[-1:] or ["(无连接)"]}')
try: ch.queue_declare('x', durable=True); r = '成功'
except Exception as e: r = f'{type(e).__name__}: {str(e)[:100]}'
print(f'  客户端醒来后再发一个命令: {r}')
print('  解决办法:耗时任务放在别的线程里、主线程继续 process_data_events;或者 BlockingConnection 里分段调用 process_data_events;或把 heartbeat 调大(但检测对端死亡也变慢)')
n.stop()
