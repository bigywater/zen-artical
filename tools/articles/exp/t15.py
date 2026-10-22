import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import ql, pika
from confluent_kafka import Producer, Consumer
tee('t15'); reset(); ql.reset()
M = MySQL('t15').start(); M.q('create database shop'); M.q('create table processed(id bigint auto_increment primary key, msg_id int, who int)', db='shop')
RQ = ql.Node('t15_rq'); RQ.start()
print(f'RabbitMQ {RQ.amqp}(pika 1.4.4,消费者是独立的子进程,可以被 kill -9)+ Kafka(第三节用)+ MySQL {M.q("select version()")[0][0]}(记录“处理了哪条消息”和第四、五节的业务状态)')
CHILD = r'''
import sys, time, os, pika, pymysql
port, q, variant, crash_at, sock = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
db = pymysql.connect(unix_socket=sock, user='root', password='', database='shop', autocommit=True); cur = db.cursor()
conn = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', int(port))); ch = conn.channel(); ch.basic_qos(prefetch_count=1)
def process(mid): cur.execute('insert into processed(msg_id, who) values (%s, %s)', (mid, os.getpid())); time.sleep(0.002)
def hang(): print('WAIT', flush=True); time.sleep(60)
if crash_at < 0:                                   # 收尾用的消费者:把队列里剩下的都处理完就退出
    for m, p, body in ch.consume(q, inactivity_timeout=2.0):
        if m is None: break
        process(int(body)); ch.basic_ack(m.delivery_tag)
    sys.exit(0)
def cb(c, m, p, body):
    mid = int(body)
    if variant == 'A':                             # 先处理,再 ack
        process(mid)
        if mid == crash_at: hang()
        c.basic_ack(m.delivery_tag)
    elif variant == 'B':                           # 先 ack,再处理
        c.basic_ack(m.delivery_tag)
        if mid == crash_at: hang()
        process(mid)
    else:                                          # auto-ack:broker 一发出去就当作成功,消费者慢慢处理
        process(mid)
        if mid == crash_at: hang()
ch.basic_consume(q, cb, auto_ack=(variant == 'C')); ch.start_consuming()
'''
(TT / 't15_child.py').write_text(CHILD)
def publish(q, n):
    c = RQ.conn(); ch = c.channel(); ch.queue_declare(q, durable=True)
    for i in range(n): ch.basic_publish('', q, str(i).encode(), pika.BasicProperties(delivery_mode=2))
    c.close()
def run_child(q, variant, crash_at):
    p = subprocess.Popen([sys.executable, str(TT / 't15_child.py'), str(RQ.amqp), q, variant, str(crash_at), M.sock], stdout=subprocess.PIPE, text=True)
    while True:
        l = p.stdout.readline()
        if l.startswith('WAIT') or l == '': break
    os.kill(p.pid, signal.SIGKILL); p.wait()

print('== 一:消费者在处理途中被 kill -9:300 条消息,处理到第 100 条时杀掉消费者进程,再起一个新消费者把队列处理完;三种确认方式')
rows = []
for variant, name in (('A', '先处理、再 ack(至少一次)'), ('B', '先 ack、再处理(至多一次)'), ('C', 'auto-ack(broker 一发出去就算成功)')):
    M.q('delete from processed', db='shop'); q = f'q1{variant}'; publish(q, 300); run_child(q, variant, 100); time.sleep(0.7)
    ready, unacked = [int(x) for x in [l for l in RQ.ctl('list_queues', 'name', 'messages_ready', 'messages_unacknowledged').splitlines() if l.startswith(q + '\t') or l.split()[:1] == [q]][0].split()[1:3]]
    p2 = subprocess.run([sys.executable, str(TT / 't15_child.py'), str(RQ.amqp), q, variant, '-1', M.sock], timeout=120)
    cnt = {r[0]: r[1] for r in M.q('select msg_id, count(*) from processed group by msg_id', db='shop')}
    lost = [i for i in range(300) if i not in cnt]; dup = [i for i, v in cnt.items() if v > 1]
    rows.append((name, f'被杀时队列:ready {ready} / unacked {unacked}', len(cnt), len(lost), (f'{lost[0]}~{lost[-1]}' if lost else '-'), f'{len(dup)}' + (f'(消息 {dup})' if dup else '')))
table(rows, ['确认方式', '消费者被杀之后 broker 里', '处理过的不同消息', '丢失', '丢失的编号', '被处理多次'])
print('  先处理再 ack:被杀时正在处理的那一条没有 ack,broker 把它重新投递给新消费者,它被处理了两次;先 ack 再处理:被杀时那一条已经确认却没处理,丢了;auto-ack:broker 已经把一大批消息推给了这个消费者,它们全丢')

print('== 二:乱序:RabbitMQ 队列本身是先进先出,但“处理完成的顺序”不一定是发布顺序')
def consume_log(q, plan, n, workers):
    """workers:[(每条消息处理时间秒, 第几条消息拒绝并重新入队一次或 None)];返回处理完成的消息编号序列。"""
    done = []; lk = threading.Lock(); stop = threading.Event()
    def w(delay, nack_at, nack_sleep=0.0):
        c = RQ.conn(); ch = c.channel(); ch.basic_qos(prefetch_count=1); seen = set()
        def cb(chn, m, p, body):
            mid = int(body)
            if nack_at is not None and mid == nack_at and mid not in seen: seen.add(mid); time.sleep(nack_sleep); chn.basic_nack(m.delivery_tag, requeue=True); return
            time.sleep(delay)
            with lk: done.append(mid)
            chn.basic_ack(m.delivery_tag)
        ch.basic_consume(q, cb)
        while not stop.is_set(): c.process_data_events(time_limit=0.05)
        c.close()
    ths = [threading.Thread(target=w, args=wk) for wk in workers]; [t.start() for t in ths]
    t0 = time.time()
    while len(done) < n and time.time() - t0 < 60: time.sleep(0.02)
    stop.set(); [t.join() for t in ths]; return done
def ooo(seq): 
    mx = -1; c = 0
    for x in seq:
        if x < mx: c += 1
        mx = max(mx, x)
    return c
publish('q2a', 60); a = consume_log('q2a', None, 60, [(0.001, 10)])
print(f'  (a) 单个消费者(prefetch=1),第 10 条被 nack 并重新入队一次:处理顺序 {a[8:14]}...,乱序的消息 {ooo(a)} 条(重新入队的消息回到原来的位置,所以仍然是 10 先于 11)')
publish('q2b', 200); b = consume_log('q2b', None, 200, [(0.02, None), (0.001, None)])
print(f'  (b) 两个消费者竞争同一个队列(一个每条 20 ms,一个每条 1 ms),200 条:处理完成的顺序前 20 个 {b[:20]},乱序的消息 {ooo(b)} 条')
publish('q2c', 200); c = consume_log('q2c', None, 200, [(0.005, 50, 0.1), (0.005, None)])
pos = {m: i for i, m in enumerate(c)}
print(f'  (c) 两个消费者(每条 5 ms),其中一个拿到第 50 条后卡了 100 ms 才 nack 重新入队:第 50 条是第 {pos[50] + 1} 个处理完的,排在它前面处理完的编号比 50 大的有 {sum(1 for m in c[:pos[50]] if m > 50)} 条(最大到 {max(c[:pos[50]])}),乱序的消息共 {ooo(c)} 条')

print('== 三:Kafka:只有同一个分区内才有顺序。3 个分区,20 个实体,每个实体 100 条递增的更新(共 2000 条),发布时各实体交错')
KN = ql.KafkaNode('t15k', port=9580).start()
def kafka_run(topic, keyed):
    KN.topics('--create', '--topic', topic, '--partitions', '3', '--replication-factor', '1')
    p = Producer({'bootstrap.servers': f'127.0.0.1:{KN.port}', 'partitioner': 'murmur2_random', 'log_level': 3}); rng = random.Random(15); rp = random.Random(99); seq = {e: 0 for e in range(20)}; order = []
    for i in range(2000):
        e = rng.choice([e for e in seq if seq[e] < 100]); seq[e] += 1; order.append((e, seq[e]))
        p.produce(topic, key=str(e).encode() if keyed else None, value=f'{e}:{seq[e]}'.encode(), partition=-1 if keyed else rp.randrange(3))   # 不设 key:没有 key 可以决定分区,这里每条消息随机指定一个分区(效果等同轮询 / 随机分区)
        if i % 200 == 0: p.poll(0)
    p.flush(10)
    c = Consumer({'bootstrap.servers': f'127.0.0.1:{KN.port}', 'group.id': f'g{time.time_ns()}', 'auto.offset.reset': 'earliest', 'enable.auto.commit': False, 'log_level': 3}); c.subscribe([topic]); got = []; t0 = time.time(); last = None
    while time.time() - t0 < 60 and (last is None or time.time() - last < 3):
        m = c.poll(0.3)
        if m is None or m.error(): continue
        e, s = map(int, m.value().decode().split(':')); got.append((e, s, m.partition())); last = time.time()
    c.close(); return order, got
rows = []
for keyed, name in ((True, '按实体 id 做 key'), (False, '不设 key(随机分区)')):
    order, got = kafka_run(f't3-{int(keyed)}', keyed)
    per_entity = sum(1 for e in range(20) if [s for ee, s, _ in got if ee == e] != sorted(s for ee, s, _ in got if ee == e))
    parts_per_entity = statistics.mean(len({pt for ee, _, pt in got if ee == e}) for e in range(20))
    pe_inv = 0
    for e in range(20):
        seqs = [s for ee, s, _ in got if ee == e]; mx = 0
        for s in seqs:
            if s < mx: pe_inv += 1
            mx = max(mx, s)
    rows.append((name, len(got), f'{parts_per_entity:.1f}', per_entity, pe_inv, ooo([order.index((e, s)) for e, s, _ in got])))
table(rows, ['写法', '收到', '每个实体平均分布在几个分区', '同一实体内顺序被打乱的实体数(共 20)', '实体内乱序的消息数', '相对发布顺序整体乱序的消息数'])
print('  按实体 id 做 key:同一实体的消息都进同一个分区,实体内部有序;不同实体之间(跨分区)没有顺序可言。不设 key:同一实体的消息被撒到多个分区,实体内部的顺序也没有了')
KN.stop(); ql.reset()

print('== 四:消费端的对策之一:消息带上版本号(同一实体单调递增),处理时只接受更新的版本(UPDATE ... WHERE version < ?);对照朴素的“来一条改一条”')
M.q('create table acct(id int primary key, status varchar(10), version int, counter int default 0)', db='shop'); M.q('create table seen(msg_id varchar(20) primary key)', db='shop')
def make_stream(seed, n_ent=100, per=20, window=300, dup_rate=0.1):
    rng = random.Random(seed); msgs = []
    for e in range(n_ent):
        for v in range(1, per + 1): msgs.append(dict(id=f'm{e}-{v}', ent=e, ver=v, status=f'S{v}', delta=1))
    base = sorted(msgs, key=lambda m: (m['ver'], m['ent']))                # 按“发布顺序”:版本轮流
    out = []
    for i in range(0, len(base), window):
        chunk = base[i:i + window]; rng.shuffle(chunk); out += chunk       # 每 50 条之内随机重排
    dups = [dict(m) for m in rng.sample(out, int(len(out) * dup_rate))]; pos = sorted(rng.sample(range(len(out) + len(dups)), len(dups)))
    res = []; it = iter(out); di = iter(dups); ps = set(pos)
    for i in range(len(out) + len(dups)): res.append(next(di) if i in ps else next(it))
    return res
STREAM = make_stream(4)
print(f'  测试流:100 个实体,每个实体 20 条更新;每条消息带两部分内容——“把 status 设成 S<版本>”(SET 类,后到的新版本覆盖旧的)和“counter 加 1”(累加类,每条消息只能算一次);发布顺序是各实体的版本轮流,每 300 条之内随机重排(相当于相邻 3 个版本的消息混在一起),再随机插入 200 条(10%)重复,共 {len(STREAM)} 条;正确的终态:每个实体 status = S20、counter = 20')
def apply(stream, use_version, use_dedup):
    M.q('delete from acct', db='shop'); M.q('delete from seen', db='shop')
    for e in range(100): M.q('insert into acct values (%s, %s, 0, 0)', (e, 'INIT'), db='shop')
    c = M.conn('shop', autocommit=False); cur = c.cursor()
    for m in stream:
        if use_dedup:
            cur.execute('insert ignore into seen values (%s)', (m['id'],))
            if cur.rowcount == 0: c.commit(); continue
        if use_version: cur.execute('update acct set status = %s, version = %s where id = %s and version < %s', (m['status'], m['ver'], m['ent'], m['ver']))     # SET 类:只接受更新的版本
        else: cur.execute('update acct set status = %s, version = %s where id = %s', (m['status'], m['ver'], m['ent']))                                             # 朴素:后到的覆盖先到的
        cur.execute('update acct set counter = counter + %s where id = %s', (m['delta'], m['ent']))                                                                    # 累加类:来一条加一次
        c.commit()
    c.close(); rows = M.q('select id, status, version, counter from acct', db='shop')
    return sum(1 for r in rows if r[1] != 'S20'), sum(1 for r in rows if r[3] != 20)
rows = []
for uv, ud, name in ((False, False, '朴素:来一条改一条'), (True, False, '只用版本号(WHERE version < ?)')):
    bad_status, bad_counter = apply(STREAM, uv, ud); rows.append((name, f'{bad_status} / 100', f'{bad_counter} / 100'))
table(rows, ['消费端的做法', 'status 最终不是 S20 的实体', 'counter 最终不是 20 的实体'])
print('  版本号能挡住乱序(旧版本晚到时被 WHERE 条件拒绝),status 全对;但累加类的 counter 不是“谁新谁覆盖”,重复消息每来一次就多加一次,版本号管不了')

print('== 五:乱序 + 重复同时来:版本号与去重(第 14 篇的去重表)合用才能两头都对')
rows = []
for uv, ud, name in ((False, False, '朴素'), (False, True, '只做去重(seen 表)'), (True, False, '只用版本号'), (True, True, '去重 + 版本号')):
    bad_status, bad_counter = apply(STREAM, uv, ud); rows.append((name, f'{bad_status} / 100', f'{bad_counter} / 100'))
table(rows, ['消费端的做法', 'status 最终不是 S20 的实体', 'counter 最终不是 20 的实体'])
print('  去重解决重复(累加类的 counter 对了),版本号解决乱序(SET 类的 status 对了);两种语义的字段各用各的办法,一起用才同时对')
reset(); ql.reset(); (TT / 't15_child.py').unlink(missing_ok=True)
shutil.rmtree(TT / 'my_t15', ignore_errors=True); shutil.rmtree(HERE / 'qtmp' / 't15_rq', ignore_errors=True); shutil.rmtree(HERE / 'qtmp' / 't15k', ignore_errors=True)
