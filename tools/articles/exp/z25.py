import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z25'); R = {}
KEEP = ('NIOServerCxnFactory', 'NIOWorkerThread', 'ProcessThread', 'SyncThread', 'CommitProcWorker', 'CommitProcessor', 'RequestThrottler', 'SessionTracker', 'FollowerRequestProcessor', 'LearnerHandler', 'QuorumPeer', 'LeaderRequestProcessor', 'ConnnectionExpirer', 'ContainerManager', 'QuorumPeer[', 'ProcessThread(sid', 'SendWorker', 'RecvWorker', 'ListenerHandler', 'QuorumCnxManager', 'Snapshot', 'WorkerSender', 'WorkerReceiver')
def short(names):
    out = []
    for x in names:
        base = re.sub(r'[\d]+', 'N', re.sub(r':/\S+', '', x)); base = re.sub(r'\(sid:.*$', '(sid:…)', base)
        if base not in out and any(k.split('(')[0] in x for k in KEEP): out.append(base)
    return out
print('== 一:单机节点的线程(jstack):请求从网络线程进入,经过 RequestThrottler → ProcessThread(Prep)→ SyncThread → (Final)')
n = Node('z25a', 7300).start(); z = client('127.0.0.1:7300'); [z.create(f'/n{i}', b'x') for i in range(50)]
th = short(threads(n)); print('  ', th); R['standalone'] = th
def metrics(node):
    m = kv(node.four('mntr')); keys = ['zk_avg_prep_process_time', 'zk_avg_sync_process_time', 'zk_avg_fsynctime', 'zk_avg_proposal_latency', 'zk_avg_commit_process_time', 'zk_avg_request_throttle_queue_time_ms']
    return {k.replace('zk_', ''): m.get(k) for k in keys}
rs = [z.create_async(f'/m{i}', b'x' * 100) for i in range(3000)]; [r.get() for r in rs]
print('  3000 次异步写之后的处理链耗时指标(平均,单位见 mntr):', metrics(n)); R['m_standalone'] = metrics(n)
z.stop(); n.stop()
print()
print('== 二:3 节点集群里 leader 与 follower 的线程不同')
e = Ensemble('z25e', 3, base=7310).start(); ld = e.leader(); fo = e.followers()[0]
z = client(f'127.0.0.1:{fo.cport}'); rs = [z.create_async(f'/m{i}', b'x' * 100) for i in range(3000)]; [r.get() for r in rs]
tl_, tf = short(threads(ld)), short(threads(fo))
print('  leader 特有的线程:', [x for x in tl_ if x not in tf]); print('  follower 特有的线程:', [x for x in tf if x not in tl_]); print('  两者共有:', [x for x in tl_ if x in tf])
R['leader_only'] = [x for x in tl_ if x not in tf]; R['follower_only'] = [x for x in tf if x not in tl_]; R['common'] = [x for x in tl_ if x in tf]
print()
print('== 三:连在 follower 上的客户端写 3000 次后,leader 与 follower 各自的处理链指标(平均)')
print('  leader  :', metrics(ld)); print('  follower:', metrics(fo)); R['m_leader'] = metrics(ld); R['m_follower'] = metrics(fo)
print()
print('== 四:读请求不进 leader:连在 follower 上读 3000 次,leader 的 zk_packets_received 增量')
p0 = int(kv(ld.four('mntr'))['zk_packets_received']); [z.get('/m1') for _ in range(3000)]; p1 = int(kv(ld.four('mntr'))['zk_packets_received'])
print(f'  3000 次读之后 leader 收到的包数增量 {p1 - p0}(读在 follower 本地完成,只有少量 ping / 同步包)'); R['read_local'] = p1 - p0
z.stop(); e.stop(); save('z25', R)
