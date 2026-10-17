import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q19'); reset()
COOKIE = (QHOME / '.erlang.cookie').read_text().strip()
def nm(t): return t.replace('q19n', 'n').replace('q19p', 'n')
BAD = 'bad_cookie'
def ev(node, expr, bad=False):
    a = ['--erlang-cookie', BAD] if bad else []
    r = node.ctl_raw(*a, 'eval', expr, timeout=60); return (r.stdout + r.stderr).strip()
def partition(minority):
    """把一个节点隔离出去:改掉它自己的 Erlang cookie 并断开所有连接;别的节点连不上它,它也连不上别的节点(进程都还活着,模拟网络不通)"""
    ev(minority, f"erlang:set_cookie(node(), '{BAD}'), [erlang:disconnect_node(N) || N <- nodes()], ok.")
def heal(minority, others):
    ev(minority, f"erlang:set_cookie(node(), '{COOKIE}'), [net_kernel:connect_node(N) || N <- {[o.nodename for o in others]!r}], ok.".replace("'n", "'n"), bad=True)
def status(node, bad=False):
    a = ['--erlang-cookie', BAD] if bad else []
    out = tidy(node.ctl_raw(*a, 'cluster_status').stdout).splitlines()
    def sect(t):
        for k, l in enumerate(out):
            if l == t:
                r = []
                for m in out[k + 2:]:
                    if not m.strip(): break
                    r.append(nm(m.strip()))
                return r
        return None
    return sect('Running Nodes'), sect('Network Partitions')

def run(mode):
    conf = [] if mode == 'ignore' else [f'cluster_partition_handling = {mode}']
    nodes = cluster('q19n' if mode == 'ignore' else 'q19p', 3, conf=conf)
    n1, n2, n3 = nodes
    return nodes, n1, n2, n3

print('== 一:默认的分区处理策略,以及 4.3.6 里元数据已经是 Khepri(多数派)')
nodes, n1, n2, n3 = run('ignore')
print('  $ rabbitmqctl eval "application:get_env(rabbit, cluster_partition_handling)."  →  ' + ev(n1, 'application:get_env(rabbit, cluster_partition_handling).') + '(没有配置:不设就是 ignore 的行为)')
c3 = n3.conn(); ch3 = c3.channel()
ch3.queue_declare('cq3', durable=True)                       # 经典队列,在 n3 上
ch3.queue_declare('qq', durable=True, arguments={'x-queue-type': 'quorum'})
cq = n1.conn().channel(); cq.queue_declare('cq1', durable=True)   # 经典队列,在 n1 上
for q in ('cq3', 'qq', 'cq1'):
    for i in range(10): ch3.basic_publish('', q, f'{q}-{i}'.encode(), pika.BasicProperties(delivery_mode=2))
time.sleep(1)
print('  队列: ' + ' / '.join(nm(l.replace(chr(9), ' ')) for l in n1.ctl('list_queues', 'name', 'type', 'leader').splitlines()[-3:]))
c3.close()

print('== 二:制造分区 {n1, n2} | {n3}:把 n3 自己的 Erlang cookie 改掉并断开所有连接,于是 n3 和另外两个都连不上彼此(模拟网络不通,进程都还活着;rabbitmqctl 用 --erlang-cookie 仍能访问 n3)')
partition(n3); time.sleep(8)
for nd in (n1, n3):
    r, p = status(nd, bad=(nd is n3))
    print(f'  从 {nm(nd.nodename)} 看 cluster_status: Running Nodes = {r};Network Partitions = {p}')

print('== 三:分区期间两边各自能做什么:多数派一侧(n1、n2)与少数派一侧(n3)')
def tryit(label, fn, wait=15):
    res = {}
    def w():
        try: res['r'] = fn()
        except Exception as e: res['r'] = f'{type(e).__name__}: {str(e)[:90]}'
    t0 = time.perf_counter(); th = threading.Thread(target=w, daemon=True); th.start(); th.join(wait)
    print(f'  {label}: {res.get("r", f"{wait} 秒内没有返回")}' + (f'({time.perf_counter() - t0:.1f} s)' if 'r' in res else ''))
def decl(node, q, **kw):
    cc = node.conn(); cc.channel().queue_declare(q, durable=True, **kw); cc.close(); return '成功'
def pub_conf(node, q, body=b'x'):
    cc = node.conn(); chh = cc.channel(); chh.confirm_delivery(); chh.basic_publish('', q, body, pika.BasicProperties(delivery_mode=2)); cc.close(); return '成功(confirm 回来)'
tryit('多数派侧 n1:声明新队列 new.maj', lambda: decl(n1, 'new.maj'))
tryit('少数派侧 n3:声明新队列 new.min', lambda: decl(n3, 'new.min'))
tryit('n3 往本地的经典队列 cq3 发布', lambda: pub_conf(n3, 'cq3', b'during-partition'))
tryit('n1 往 n1 上的经典队列 cq1 发布', lambda: pub_conf(n1, 'cq1', b'during-partition'))
tryit('n1 往 quorum 队列 qq 发布(leader 原来在 n3)', lambda: pub_conf(n1, 'qq', b'from-majority'))
tryit('n3 往 quorum 队列 qq 发布', lambda: pub_conf(n3, 'qq', b'from-minority'), wait=10)
print('  list_queues(从 n1 看): ' + ' / '.join(nm(l.replace(chr(9), ' ')) for l in n1.ctl('list_queues', 'name', 'type', 'leader', 'online').splitlines()[-4:]))

print('== 四:恢复网络:cookie 改回来、重新连接,看 Network Partitions 是否还留着记录、消息有没有丢、有没有冲突')
heal(n3, [n1, n2]); time.sleep(10)
for nd in (n1, n3):
    r, p = status(nd)
    print(f'  愈合后从 {nm(nd.nodename)} 看: Running Nodes = {r};Network Partitions = {p}')
def count(node, q):
    cc = node.conn(); chh = cc.channel(); k = 0
    while True:
        mt, pp, b = chh.basic_get(q, auto_ack=True)
        if mt is None: break
        k += 1
    cc.close(); return k
print(f'  cq3(n3 上,分区期间 n3 本地发过 1 条): 取出 {count(n3, "cq3")} 条(10 + 1)')
print(f'  cq1(n1 上): 取出 {count(n1, "cq1")} 条')
tryit('愈合后从 n3 声明新队列 new.after', lambda: decl(n3, 'new.after'))
for nd in nodes: nd.stop(kill=True)

print('== 五:pause_minority:分区时少数派一侧的节点自己暂停(关掉监听端口),多数派继续;愈合后自动恢复')
nodes, n1, n2, n3 = run('pause_minority')
print('  $ rabbitmqctl eval "application:get_env(rabbit, cluster_partition_handling)."  →  ' + ev(n1, 'application:get_env(rabbit, cluster_partition_handling).'))
partition(n3); time.sleep(10)
for nd in (n1, n3):
    try: pika.BlockingConnection(nd.params(connection_attempts=1, socket_timeout=3)).close(); r = '可以连接'
    except Exception as e: r = f'连接失败: {type(e).__name__}'
    print(f'  客户端连 {nm(nd.nodename)} 的 AMQP 端口: {r}')
r, p = status(n1); print(f'  n1 看 Running Nodes = {r}')
heal(n3, [n1, n2]); time.sleep(12)
try: pika.BlockingConnection(n3.params(connection_attempts=1, socket_timeout=3)).close(); r = '可以连接(自动恢复)'
except Exception as e: r = f'连接失败: {type(e).__name__}'
print(f'  愈合后客户端连 n3: {r}')
for nd in nodes: nd.stop(kill=True)
