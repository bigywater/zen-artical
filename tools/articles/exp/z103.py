import sys, os, time, json, re, subprocess, shutil, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kfl import *
tee('z103'); R = {}
for d in ZDATA.glob('kafka-*'): shutil.rmtree(d, ignore_errors=True)
n = Node('z103', 7300, xmx=384, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
def bprops(i): return {'broker.id': i, 'listeners': f'PLAINTEXT://127.0.0.1:{7900 + i}', 'zookeeper.connect': '127.0.0.1:7300', 'zookeeper.session.timeout.ms': 6000, 'offsets.topic.replication.factor': 3, 'transaction.state.log.replication.factor': 3, 'transaction.state.log.min.isr': 2, 'replica.lag.time.max.ms': 10000, 'group.initial.rebalance.delay.ms': 0, 'num.partitions': 3, 'auto.create.topics.enable': 'false'}
B = {i: KNode(i, 7900 + i, bprops(i)) for i in (1, 2, 3)}
for i in B: B[i].start(wait_log='started \\(kafka.server.KafkaServer\\)')
BS = ','.join(f'127.0.0.1:{7900 + i}' for i in B)
print('== 一:启动 3 个 Kafka 3.9.2 broker(ZooKeeper 模式,连我的 ZooKeeper 3.9.6)后,Kafka 在 ZooKeeper 里建的顶层节点;以及一个 broker 的注册信息')
def tops(): return sorted(k for k in z.get_children('/') if k != 'zookeeper')
print('  顶层 znode:', tops()); R['tops'] = tops()
d, st = z.get('/brokers/ids/1'); print('  /brokers/ids/1 =', d.decode(), '| 临时节点:', st.ephemeralOwner != 0); R['b1'] = d.decode()
d, st = z.get('/controller'); print('  /controller =', d.decode(), '| 临时节点:', st.ephemeralOwner != 0); print('  /controller_epoch =', z.get('/controller_epoch')[0].decode(), '| /cluster/id =', json.loads(z.get('/cluster/id')[0])['id'])
print('  /brokers/ids 子节点:', sorted(z.get_children('/brokers/ids')))
print()
print('== 二:建一个 3 分区、3 副本的主题 t1:ZooKeeper 里的分配信息与分区状态;并确认消费组的 offset 不在 ZooKeeper 里')
print('  ' + kcmd('kafka-topics.sh', '--bootstrap-server', BS, '--create', '--topic', 't1', '--partitions', '3', '--replication-factor', '3').splitlines()[-1])
time.sleep(2)
print('  /brokers/topics/t1 =', z.get('/brokers/topics/t1')[0].decode())
for p in range(3): print(f'  /brokers/topics/t1/partitions/{p}/state =', z.get(f'/brokers/topics/t1/partitions/{p}/state')[0].decode())
from kafka import KafkaProducer, KafkaConsumer
pr = KafkaProducer(bootstrap_servers=BS, acks='all'); [pr.send('t1', f'm{i}'.encode()) for i in range(1000)]; pr.flush()
co = KafkaConsumer('t1', bootstrap_servers=BS, group_id='g1', auto_offset_reset='earliest', enable_auto_commit=True, consumer_timeout_ms=8000); got = sum(1 for _ in co); co.commit(); co.close()
print(f'  生产 1000 条、消费组 g1 消费 {got} 条并提交 offset')
def allpaths(p='/'):
    r = []
    for k in z.get_children(p):
        q = p.rstrip('/') + '/' + k
        if q.startswith('/zookeeper'): continue
        r.append(q); r += allpaths(q)
    return r
ap = allpaths()
print(f'  ZooKeeper 里共 {len(ap)} 个 znode(不含 /zookeeper);其中路径含消费组名 g1 的:{[x for x in ap if "g1" in x]};/consumers 的子节点:{z.get_children("/consumers")}(是空的;这个节点为什么还在,我没有查)')
print('  /brokers/topics 下的主题:', sorted(z.get_children('/brokers/topics')), '(__consumer_offsets 是 Kafka 自己存 offset 的内部主题,不在 ZooKeeper 里存 offset)')
R['topics'] = sorted(z.get_children('/brokers/topics'))
print()
print('== 三:kill -9 当前 controller broker:/controller 多久换成别的 broker、/controller_epoch 变化,以及主题 t1 所有分区的 leader 多久都不在死掉的 broker 上')
ctl = json.loads(z.get('/controller')[0])['brokerid']; ep0 = int(z.get('/controller_epoch')[0])
def leaders(): return {p: json.loads(z.get(f'/brokers/topics/t1/partitions/{p}/state')[0])['leader'] for p in range(3)}
l0 = leaders(); tk = time.time(); B[ctl].kill(); t_ctl = t_lead = None
while time.time() - tk < 60 and (t_ctl is None or t_lead is None):
    try:
        if t_ctl is None and json.loads(z.get('/controller')[0])['brokerid'] != ctl: t_ctl = time.time() - tk
    except Exception: pass
    if t_lead is None and all(v != ctl for v in leaders().values()): t_lead = time.time() - tk
    time.sleep(0.1)
print(f'  被杀的是 controller = broker {ctl};之前各分区 leader {l0}')
print(f'  /controller 在 {t_ctl:.1f} s 后变成 broker {json.loads(z.get("/controller")[0])["brokerid"]};/controller_epoch {ep0} → {z.get("/controller_epoch")[0].decode()};t1 所有分区 leader 都离开了 broker {ctl}:{t_lead:.1f} s 后;现在 {leaders()}')
R['ctl'] = dict(dead=ctl, t_ctl=t_ctl, t_lead=t_lead, ep0=ep0, ep1=int(z.get('/controller_epoch')[0]))
print('  /brokers/ids 现在:', sorted(z.get_children('/brokers/ids')))
print()
print('== 四:重新启动被杀的 broker')
B[ctl].start(wait_log='started \\(kafka.server.KafkaServer\\)'); time.sleep(3)
print('  重新启动 broker', ctl, '后 /brokers/ids =', sorted(z.get_children('/brokers/ids')), '| t1 的 ISR =', {p: json.loads(z.get(f"/brokers/topics/t1/partitions/{p}/state")[0])['isr'] for p in range(3)})
print()
print('== 五:这个空闲的 Kafka 集群给 ZooKeeper 带来的负载')
m = kv(n.four('mntr')); print(f'  zk_znode_count={m["zk_znode_count"]} zk_watch_count={m["zk_watch_count"]} zk_ephemerals_count={m["zk_ephemerals_count"]} zk_num_alive_connections={m["zk_num_alive_connections"]} zk_outstanding_requests={m["zk_outstanding_requests"]}')
R['mntr'] = {k: m[k] for k in ('zk_znode_count', 'zk_watch_count', 'zk_ephemerals_count', 'zk_num_alive_connections')}
for b in B.values(): b.kill()
z.stop(); n.stop(); save('z103', R); os._exit(0)
