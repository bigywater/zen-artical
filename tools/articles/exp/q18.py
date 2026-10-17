import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q18'); reset()
nodes = cluster('q18n', 3)
n1, n2, n3 = nodes
def nm(t): return t.replace('q18n', 'n')

print('== 一:元数据(exchange、队列定义、绑定、用户……)在所有节点上都有:在 n1 上声明,从 n2、n3 上看到一样的东西;元数据存储是 Khepri(基于 Raft)')
c1 = n1.conn(); ch1 = c1.channel()
ch1.exchange_declare('x.meta', 'direct', durable=True); ch1.queue_declare('q.meta', durable=True); ch1.queue_bind('q.meta', 'x.meta', 'k')
for nd in nodes:
    ex = [l for l in nd.ctl('list_exchanges', 'name').splitlines() if l.startswith('x.')]
    qs = [l.split(chr(9))[0] + '@' + nm(l.split(chr(9))[1]) for l in nd.ctl('list_queues', 'name', 'leader').splitlines() if l.startswith('q.')]
    print(f'  {nm(nd.nodename)} 上看到 exchange {ex}、队列 {qs}')
import json as _j
ff = _j.loads(n1.ctl_raw('--quiet', 'list_feature_flags', '--formatter', 'json').stdout)
print('  feature flag khepri_db 的状态: ' + str([(f['name'], f['state']) for f in ff if f['name'] == 'khepri_db']))

print('== 二:消息不在所有节点上:经典队列 q.meta 在 n1,客户端连到 n3 发布 / 消费,消息要在节点间转发;比较“直连队列所在节点”与“连到别的节点”的同步 confirm 延迟(各 3000 条,p50 / p99)')
def lat(port, N=3000):
    cc = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', port)); cch = cc.channel(); cch.confirm_delivery()
    ts = []
    for i in range(N):
        t0 = time.perf_counter(); cch.basic_publish('x.meta', 'k', b'x' * 100); ts.append(ms(t0))
    cch.queue_purge('q.meta'); cc.close(); ts.sort(); return ts[N // 2], ts[int(N * 0.99)]
res = {}
for label, nd in (('连到队列所在的 n1', n1), ('连到 n2', n2), ('连到 n3', n3)):
    xs = [lat(nd.amqp) for _ in range(3)]
    res[label] = (median(x[0] for x in xs), median(x[1] for x in xs))
for label, (a, b) in res.items(): print(f'  {label}: p50 {a:.3f} ms,p99 {b:.3f} ms')

print('== 三:队列落在哪个节点:默认 queue_leader_locator=client-local(谁声明就在谁那);用 balanced 则按各节点现有队列数放置。分别从 n1、n2、n3 各连一个客户端各声明 3 个 quorum 队列')
def decl_from(nd, prefix, k=3):
    cc = nd.conn(); cch = cc.channel()
    for i in range(k): cch.queue_declare(f'{prefix}{nd.name[-1]}.{i}', durable=True, arguments={'x-queue-type': 'quorum'})
    cc.close()
for nd in nodes: decl_from(nd, 'loc.')
time.sleep(1)
def leaders(prefix):
    out = n1.ctl('list_queues', 'name', 'leader')
    from collections import Counter
    return Counter(nm(l.split(chr(9))[1]) for l in out.splitlines() if l.startswith(prefix))
print(f'  默认(client-local),每个节点上的客户端各声明 3 个,leader 的分布: {dict(leaders("loc."))}')
print(f'  其中 loc.1.* 是 n1 上的客户端声明的: ' + ', '.join(nm(l.split(chr(9))[1]) for l in n1.ctl('list_queues', 'name', 'leader').splitlines() if l.startswith('loc.1.')))
# 全部从 n1 声明 9 个,client-local → 全在 n1;设 balanced 后
for nd in nodes:
    nd.ctl('set_policy', 'bal', '^bal[.]', '{"queue-leader-locator":"balanced"}', '--apply-to', 'queues')
time.sleep(1)
cc = n1.conn(); cch = cc.channel()
for i in range(9): cch.queue_declare(f'bal.{i}', durable=True, arguments={'x-queue-type': 'quorum'})
for i in range(9): cch.queue_declare(f'cl.{i}', durable=True, arguments={'x-queue-type': 'quorum'})
time.sleep(1)
print(f'  全部从 n1 的客户端声明 9 个队列:policy queue-leader-locator=balanced → {dict(leaders("bal."))};不设 policy(client-local)→ {dict(leaders("cl."))}')
cc.close()

print('== 四:节点离开 / 加入集群:cluster_status 的 Running Nodes 变化;forget_cluster_node 把已经停掉的节点从集群里移除')
n3.stop()
out = n1.ctl('cluster_status').splitlines()
def sect(title):
    for k, l in enumerate(out):
        if l == title:
            r = []
            for m in out[k + 2:]:
                if not m.strip(): break
                r.append(nm(m.strip()))
            return r
print(f'  停掉 n3 之后:Disk Nodes {sect("Disk Nodes")};Running Nodes {sect("Running Nodes")}')
print('  $ rabbitmqctl forget_cluster_node ' + nm(n3.nodename))
print('    ' + nm(n1.ctl('forget_cluster_node', n3.nodename)).replace('\n', '\n    '))
out = n1.ctl('cluster_status').splitlines()
print(f'  forget 之后:Disk Nodes {sect("Disk Nodes")};Running Nodes {sect("Running Nodes")}')

print('== 五:Erlang cookie 不一致的节点加不进集群:新节点用另一个 HOME(另一个 .erlang.cookie)')
other_home = QT / '_home_other'; shutil.rmtree(other_home, ignore_errors=True); other_home.mkdir(exist_ok=True)
(other_home / '.erlang.cookie').write_text('DIFFERENTCOOKIE'); os.chmod(other_home / '.erlang.cookie', 0o400)
n4 = Node('q18x', env={'HOME': str(other_home)}); n4.start()
r = n4.ctl_raw('stop_app'); r2 = n4.ctl_raw('join_cluster', n1.nodename)
print('  $ rabbitmqctl -n ' + nm(n4.nodename) + ' join_cluster ' + nm(n1.nodename))
L = [l for l in nm(tidy(r2.stdout + r2.stderr)).splitlines() if l.strip()]
print('    ' + '\n    '.join(l for l in L if 'in function' not in l and 'in call' not in l)[:900])
n4.stop(kill=True)

print('== 六:元数据写需要多数派:3 个节点只剩 n1。已经存在的经典队列(在 n1 上)还能发布;声明新队列 / 新 exchange 会怎样')
n2.stop(kill=True)
try: n3.stop(kill=True)
except Exception: pass
time.sleep(2)
cx = n1.conn(); cxh = cx.channel(); cxh.confirm_delivery()
t0 = time.perf_counter()
try: cxh.basic_publish('x.meta', 'k', b'still-works'); r = f'成功({ms(t0):.0f} ms)'
except Exception as e: r = f'{type(e).__name__}: {str(e)[:100]}'
print(f'  往已有的 exchange / 队列发布一条(带 confirm): {r}')
res = {}
def decl():
    try:
        c_ = n1.conn(); c_.channel().queue_declare('q.new', durable=True); res['r'] = '成功'
    except Exception as e: res['r'] = f'{type(e).__name__}: {str(e)[:120]}'
t0 = time.perf_counter(); th = threading.Thread(target=decl, daemon=True); th.start(); th.join(20)
print(f'  声明新队列 q.new: {res.get("r", "20 秒内没有返回")}(用时 {time.perf_counter() - t0:.1f} s)')
for nd in nodes: nd.stop(kill=True)
