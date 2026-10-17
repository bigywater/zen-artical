import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q16'); reset()
nodes = cluster('q16n', 3)
n1, n2, n3 = nodes
def nm(t): return t.replace('q16n', 'n')
import json as _j
def qs(node, q='rq'):
    out = node.queues_cmd('--formatter', 'json', 'quorum_status', q)
    rows = _j.loads(out[out.index('['):])
    print(f'    {"节点":<6}{"Raft 状态":<14}{"Term":>5}{"Last Log":>10}{"Commit":>8}{"Applied":>9}')
    for r in rows:
        g = lambda k: str(r.get(k, '-'))
        print(f'    {nm(r["Node Name"]).split("@")[0]:<6}{g("Raft State"):<14}{g("Term"):>5}{g("Last Log Index"):>10}{g("Commit Index"):>8}{g("Last Applied"):>9}')
c1 = n1.conn(); ch1 = c1.channel()
ch1.queue_declare('rq', durable=True, arguments={'x-queue-type': 'quorum'})
ch1.confirm_delivery()

print('== 一:quorum_status:刚建好的队列,3 个成员各自的 Raft 状态、term、日志下标')
print('  $ rabbitmq-queues quorum_status rq')
qs(n1)

print('== 二:发布 1000 条消息之后,每个成员的 log index / commit index 怎么变(leader 和 follower 差多少)')
for i in range(1000): ch1.basic_publish('', 'rq', f'm{i}'.encode(), pika.BasicProperties(delivery_mode=2))
time.sleep(1)
qs(n1)
leader = [l for l in n1.ctl('list_queues', 'name', 'leader').splitlines() if l.startswith('rq')][0].split('\t')[1]
print(f'  当前 leader: {nm(leader)}')

print('== 三:杀掉 leader 所在节点,选举要多久、term 变成多少、新 leader 是谁')
leader_node = next(x for x in nodes if x.nodename == leader)
others = [x for x in nodes if x is not leader_node]
t_kill = time.perf_counter(); leader_node.stop(kill=True)
ch_o = others[0].conn().channel(); ch_o.confirm_delivery()
ok_at = None
while time.perf_counter() - t_kill < 30:
    try:
        ch_o = others[0].conn().channel(); ch_o.confirm_delivery(); ch_o.basic_publish('', 'rq', b'after', pika.BasicProperties(delivery_mode=2)); ok_at = (time.perf_counter() - t_kill) * 1000; break
    except Exception: time.sleep(0.02)
print(f'  杀掉 leader 后,第一次成功发布(confirm 回来)在 {ok_at:.0f} ms 之后')
new_leader = [l for l in others[0].ctl('list_queues', 'name', 'leader', 'online').splitlines() if l.startswith('rq')][0].replace(chr(9), ' | ')
print(f'  list_queues: {nm(new_leader)}')
qs(others[0])

print('== 四:多数派:3 个成员只剩 1 个(再杀一个),发布不会得到 confirm——写必须多数派(2/3)落盘;读(basic_get)也要经过 leader,同样不可用')
second = others[0] if nm(new_leader).split(' | ')[1] != nm(others[0].nodename) else others[1]
# 再杀一个:杀掉不是 leader 的那个,只剩 leader 一个
cur_leader = next(x for x in others if x.nodename in new_leader)
victim = next(x for x in others if x is not cur_leader)
victim.stop(kill=True)
time.sleep(1)
cx = cur_leader.conn(); chx = cx.channel(); chx.confirm_delivery()
res = {}
def try_pub():
    try: chx.basic_publish('', 'rq', b'no-quorum', pika.BasicProperties(delivery_mode=2)); res['r'] = 'ack'
    except Exception as e: res['r'] = type(e).__name__
th = threading.Thread(target=try_pub, daemon=True); th.start(); th.join(8)
print(f'  只剩 1/3 个节点时发布一条(带 confirm),等 8 秒: {res.get("r", "仍在等待 confirm,没有 ack 也没有 nack")}')
th2_res = {}
def try_get():
    try:
        cc = cur_leader.conn(); cch = cc.channel(); mt, p, b = cch.basic_get('rq', auto_ack=True); th2_res['r'] = 'got' if mt else 'empty'
    except Exception as e: th2_res['r'] = type(e).__name__ + ': ' + str(e)[:80]
th2 = threading.Thread(target=try_get, daemon=True); th2.start(); th2.join(8)
print(f'  同样条件 basic_get 取一条: {th2_res.get("r", "8 秒内没有返回")}')

print('== 五:把被杀的两个节点都启动,日志追平,服务恢复;之前挂起的那条发布会不会得到 confirm,最后队列里有多少条')
victim.start(); leader_node.start()
time.sleep(1)
th.join(30)
print(f'  之前挂起的那条发布最终结果: {res.get("r", "仍无结果")}')
time.sleep(2)
qs(cur_leader)
got = 0; cz = cur_leader.conn().channel()
while True:
    mt, p, b = cz.basic_get('rq', auto_ack=True)
    if mt is None: break
    got += 1
print(f'  队列里最后共有 {got} 条;另外之前挂起的 basic_get(auto_ack)在恢复后取走了 {1 if th2_res.get("r") == "got" else 0} 条——共发布 1000 + 1(选举后)+ 1(无多数派时)= 1002 条')

print('== 六:写路径的代价:同一集群里,quorum 队列的副本数 1 / 3(成员数)对带 confirm 发布 20000 条的耗时影响')
for x in nodes:
    try: x.start() if x.p.poll() is not None else None
    except Exception: pass
time.sleep(3)
ccc = n2.conn().channel()
for q, a in (('rq3', {'x-queue-type': 'quorum'}), ('rq1', {'x-queue-type': 'quorum', 'x-quorum-initial-group-size': 1})):
    ccc.queue_delete(q); ccc.queue_declare(q, durable=True, arguments=a)
time.sleep(1)
for q in ('rq1', 'rq3'):
    mem = [l for l in n2.ctl('list_queues', 'name', 'members').splitlines() if l.startswith(q)][0].split('\t')[1]
    print(f'  {q}: members = {nm(mem)}')
res = {}
for q in ('rq1', 'rq3'):
    ts = []
    for _ in range(3):
        el, a, nk, ok = async_publish(n2.amqp, q, 20000); ts.append(el); ccc.queue_purge(q)
    res[q] = median(ts)
for q, v in res.items(): print(f'  {q}: {v:.0f} ms  {20000 / v * 1000:.0f} 条/秒')
for x in nodes: x.stop(kill=True)
