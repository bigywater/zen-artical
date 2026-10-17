import sys, os, time, json, re, subprocess, shutil, threading, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kfl import *
tee('z104'); R = {}
for d in ZDATA.glob('kafka-*'): shutil.rmtree(d, ignore_errors=True)
n = Node('z104', 7300, xmx=384, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
def bprops(i): return {'broker.id': i, 'listeners': f'PLAINTEXT://127.0.0.1:{7900 + i}', 'zookeeper.connect': '127.0.0.1:7300', 'zookeeper.session.timeout.ms': 6000, 'offsets.topic.replication.factor': 3, 'transaction.state.log.replication.factor': 3, 'transaction.state.log.min.isr': 2, 'group.initial.rebalance.delay.ms': 0, 'auto.create.topics.enable': 'false'}
B = {i: KNode(i, 7900 + i, bprops(i)) for i in (1, 2, 3)}
for i in B: B[i].start(wait_log='started \\(kafka.server.KafkaServer\\)')
BS = ','.join(f'127.0.0.1:{7900 + i}' for i in B); cid = json.loads(z.get('/cluster/id')[0])['id']
cfgd = kcmd('kafka-configs.sh', '--bootstrap-server', BS, '--entity-type', 'brokers', '--entity-name', '1', '--describe', '--all'); dflt = re.search(r'zookeeper.session.timeout.ms=(\d+)', cfgd)
print('== 一:起点:ZooKeeper 模式的 3 broker 集群,3 个主题数据 + 一个消费组;后台持续写入的生产者')
for t in ('t1', 't2'): kcmd('kafka-topics.sh', '--bootstrap-server', BS, '--create', '--topic', t, '--partitions', '3', '--replication-factor', '3')
kcmd('kafka-topics.sh', '--bootstrap-server', BS, '--create', '--topic', 'mig', '--partitions', '3', '--replication-factor', '3')
from kafka import KafkaProducer, KafkaConsumer
pr0 = KafkaProducer(bootstrap_servers=BS, acks='all'); [pr0.send('t1', f'a{i}'.encode()) for i in range(500)]; [pr0.send('t2', f'b{i}'.encode()) for i in range(300)]; pr0.flush(); pr0.close()
co = KafkaConsumer('t1', bootstrap_servers=BS, group_id='g1', auto_offset_reset='earliest', enable_auto_commit=False, consumer_timeout_ms=6000); k = 0
for m in co:
    k += 1
    if k == 200: break
co.commit(); co.close()
def describe(): 
    o = kcmd('kafka-topics.sh', '--bootstrap-server', BS, '--describe'); return o
def group(): return kcmd('kafka-consumer-groups.sh', '--bootstrap-server', BS, '--describe', '--group', 'g1')
d0 = describe(); g0 = group()
def summarize(o): return sorted(re.findall(r'Topic: (\S+)\s+TopicId: \S+\s+PartitionCount: (\d+)\s+ReplicationFactor: (\d+)', o))
print('  主题:', summarize(d0)); print('  消费组 g1 的 t1 各分区 CURRENT-OFFSET:', re.findall(r'g1\s+t1\s+(\d)\s+(\d+)', g0))
R['d0'] = summarize(d0); R['g0'] = re.findall(r'g1\s+t1\s+(\d)\s+(\d+)', g0)
stop = threading.Event(); sent = []; errs = []; st_ = []
def producer():
    p = KafkaProducer(bootstrap_servers=BS, acks='all', retries=50, request_timeout_ms=15000, max_block_ms=60000); i = 0
    while not stop.is_set():
        try: p.send('mig', str(i).encode()).get(timeout=60); sent.append(i); st_.append(time.time()); i += 1
        except Exception as e: errs.append(type(e).__name__)
        time.sleep(0.02)
    p.close()
pt = threading.Thread(target=producer); pt.start(); time.sleep(2)
print(f'  后台生产者已写入 {len(sent)} 条(每 20 ms 一条,同步等待 acks=all)')
def zkstate():
    return dict(controller=(z.get('/controller')[0].decode() if z.exists('/controller') else None), migration=(z.exists('/migration') is not None), brokers=sorted(z.get_children('/brokers/ids')) if z.exists('/brokers/ids') else [])
print('  ZooKeeper 状态:', zkstate()); R['zk0'] = zkstate()
print()
print('== 二:启动 KRaft controller(迁移模式):node.id=3000,controller.quorum.voters=3000@127.0.0.1:7910,zookeeper.metadata.migration.enable=true,cluster id 与 ZooKeeper 里的一致')
CP = {'process.roles': 'controller', 'node.id': 3000, 'listeners': 'CONTROLLER://127.0.0.1:7910', 'controller.quorum.voters': '3000@127.0.0.1:7910', 'controller.listener.names': 'CONTROLLER', 'listener.security.protocol.map': 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT', 'zookeeper.connect': '127.0.0.1:7300', 'zookeeper.session.timeout.ms': 6000, 'zookeeper.metadata.migration.enable': 'true', 'inter.broker.protocol.version': '3.9'}
C = KNode(3000, 7910, CP, name='kafka-ctl'); C.write()
print('  ' + kcmd('kafka-storage.sh', 'format', '-t', cid, '-c', str(C.dir / 'server.properties')).splitlines()[-1][:200])
C.start(wait_log='Kafka Server started|Transitioned from STARTING to STARTED|\\[KafkaRaftServer nodeId=3000\\] Kafka Server started')
time.sleep(5); lg = C.log()
print('  controller 日志里与迁移有关的行:'); [print('    ' + re.sub(r'^\[[^\]]*\]\s*', '', l)[:210]) for l in [l for l in lg.splitlines() if re.search(r'igration|zk-migration|Became the active|ZK', l)][:8]]
print('  此时 ZooKeeper:', zkstate())
print()
print('== 三:滚动重启 3 个 broker,加入 controller.quorum.voters 与迁移开关(仍然是 ZooKeeper 模式的 broker)')
BM = {'controller.quorum.voters': '3000@127.0.0.1:7910', 'controller.listener.names': 'CONTROLLER', 'listener.security.protocol.map': 'PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT', 'zookeeper.metadata.migration.enable': 'true', 'inter.broker.protocol.version': '3.9'}
t_roll = time.time()
for i in (1, 2, 3):
    B[i].stop(); B[i].start(props=BM, wait_log='started \\(kafka.server.KafkaServer\\)'); time.sleep(3); print(f'  broker {i} 已用迁移配置重启({time.time() - t_roll:.0f} s)')
time.sleep(8); lg = C.log()
mg = [re.sub(r'^\[[^\]]*\]\s*', '', l)[:230] for l in lg.splitlines() if re.search(r'igrat', l)]
print('  controller 日志里迁移相关的行(最后 10 行):'); [print('    ' + l) for l in mg[-10:]]
print('  ZooKeeper 状态:', zkstate()); R['mig_log'] = mg[-10:]; R['zk1'] = zkstate()
print('  此时 /brokers/topics 仍是:', sorted(z.get_children('/brokers/topics')), '(controller 已进入 DUAL_WRITE:KRaft 的元数据变更同时写回 ZooKeeper,迁移未完成前还能回滚)')
q = kcmd('kafka-metadata-quorum.sh', '--bootstrap-controller', '127.0.0.1:7910', 'describe', '--status'); print('  kafka-metadata-quorum describe --status:'); [print('    ' + l) for l in q.splitlines()[:8]]
print()
print('== 四:把 broker 切换为纯 KRaft(process.roles=broker,去掉 zookeeper.*),逐个重启')
def kraft_props(i): return {'process.roles': 'broker', 'node.id': i, 'listeners': f'PLAINTEXT://127.0.0.1:{7900 + i}', 'controller.quorum.voters': '3000@127.0.0.1:7910', 'controller.listener.names': 'CONTROLLER', 'listener.security.protocol.map': 'PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT', 'offsets.topic.replication.factor': 3, 'transaction.state.log.replication.factor': 3, 'transaction.state.log.min.isr': 2, 'group.initial.rebalance.delay.ms': 0, 'auto.create.topics.enable': 'false', 'inter.broker.protocol.version': '3.9'}
for i in (1, 2, 3):
    B[i].stop(); B[i].props = kraft_props(i); B[i].start(wait_log='Kafka Server started|Transitioned from STARTING to STARTED|nodeId=%d\\] Kafka Server started' % i, timeout=120); time.sleep(4); print(f'  broker {i} 以 KRaft 模式重启')
time.sleep(5)
print('  ZooKeeper 状态:', zkstate())
print()
print('== 五:收尾:controller 去掉迁移配置与 zookeeper.connect 重启;停掉 ZooKeeper,集群仍然工作')
C.stop(); cp2 = {k: v for k, v in CP.items() if not k.startswith('zookeeper')}; C.props = cp2; C.start(wait_log='Kafka Server started|STARTED', timeout=90); time.sleep(6)
n.stop(); time.sleep(3); print('  ZooKeeper 已停止;后台生产者继续写:', end=' '); a = len(sent); time.sleep(4); print(f'{len(sent) - a} 条/4 s')
stop.set(); pt.join(); 
print(f'  生产者总共写入 {len(sent)} 条(同步确认),过程中出现的发送错误类型 {dict(collections.Counter(errs))}')
BS2 = BS
d1 = kcmd('kafka-topics.sh', '--bootstrap-server', BS2, '--describe'); print('  迁移后的主题:', summarize(d1), '| 与迁移前一致:', summarize(d1) == summarize(d0))
g1 = kcmd('kafka-consumer-groups.sh', '--bootstrap-server', BS2, '--describe', '--group', 'g1'); print('  消费组 g1 的 t1 各分区 CURRENT-OFFSET:', re.findall(r'g1\s+t1\s+(\d)\s+(\d+)', g1), '| 与迁移前一致:', re.findall(r'g1\s+t1\s+(\d)\s+(\d+)', g1) == R['g0'])
co = KafkaConsumer('mig', bootstrap_servers=BS2, auto_offset_reset='earliest', enable_auto_commit=False, consumer_timeout_ms=10000); vals = [int(m.value) for m in co]; co.close()
cnt = collections.Counter(vals); miss = [i for i in range(len(sent)) if i not in cnt]; dup = [i for i, c in cnt.items() if c > 1]
print(f'  主题 mig 读回 {len(vals)} 条:丢失(同步确认过的 id 里没读到){len(miss)} 条,重复 {len(dup)} 条')
gaps = [(st_[i + 1] - st_[i], st_[i]) for i in range(len(st_) - 1)]; mg_ = max(gaps); print(f'  生产者相邻两次确认之间的最长间隔 {mg_[0]:.1f} s(整个迁移过程;超过 1 s 的间隔共 {sum(1 for g, t in gaps if g > 1)} 个)'); R['gap'] = dict(max=mg_[0], over1=sum(1 for g, t in gaps if g > 1))
R['end'] = dict(sent=len(sent), read=len(vals), miss=len(miss), dup=len(dup), errs=dict(collections.Counter(errs)), same_topics=summarize(d1) == summarize(d0), same_offsets=re.findall(r'g1\s+t1\s+(\d)\s+(\d+)', g1) == R['g0'])
for b in B.values(): b.kill()
C.kill(); z.stop(); n.stop(); save('z104', R); os._exit(0)
