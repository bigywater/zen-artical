import sys, os, re, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import ql
from outbox import mk_producer, read_all
from confluent_kafka import Consumer
tee('t12'); reset(); ql.reset()
P = PG('t12', conf={'wal_level': 'logical', 'max_replication_slots': 10, 'max_wal_senders': 10}).start()
KN = ql.KafkaNode('t12k', port=9580).start()
P.q('create table outbox(id bigserial primary key, aggregate_id text, payload text, sent boolean not null default false, created timestamptz default now())')
P.q('create index outbox_unsent on outbox(id) where not sent')
def topic(name): KN.topics('--create', '--topic', name, '--partitions', '1', '--replication-factor', '1'); return name
print(f'PostgreSQL {P.q("select version()")[0][0].split(",")[0]}(wal_level=logical,outbox 表 + (id) WHERE NOT sent 的部分索引)+ Kafka {KN.port};轮询和 CDC 用的是同一个数据库、同一张表,CDC 是 PostgreSQL 自带的逻辑解码(pg_recvlogical + test_decoding 插件,我写的解析程序把解码出来的行发到 Kafka)')

class Sink(threading.Thread):
    """后台消费者:记录每条消息收到的时刻,和消息里携带的“事务提交前一刻”的时刻相减就是端到端延迟。"""
    def __init__(self, tp):
        super().__init__(daemon=True); self.tp = tp; self.lat = []; self.ids = []; self.stop_ = threading.Event(); self.ready = threading.Event(); self.warm = threading.Event()
    def run(self):
        c = Consumer({'bootstrap.servers': f'127.0.0.1:{KN.port}', 'group.id': f'g{time.time_ns()}', 'auto.offset.reset': 'earliest', 'enable.auto.commit': False, 'log_level': 3, 'fetch.wait.max.ms': 5}); c.subscribe([self.tp])
        while not self.stop_.is_set():
            m = c.poll(0.01)
            if not self.ready.is_set() and c.assignment(): self.ready.set()
            if m is None or m.error(): continue
            now = time.time(); d = json.loads(m.value())
            if d['i'] < 0: self.warm.set(); continue          # 热身消息不计,但收到它说明整条链路(生产者 → broker → 消费者)已经热了
            self.lat.append(now - d['t']); self.ids.append(d['i'])
        c.close()
def load(n, gap, tag='x'):
    """n 个事件,每个是一个独立的小事务(autocommit),相邻两个之间间隔 gap 秒(带抖动)。"""
    c = P.conn(); rng = random.Random(3)
    for i in range(n):
        t = time.time(); c.execute('insert into outbox(aggregate_id, payload) values (%s, %s)', (f'{tag}{i}', json.dumps({'i': i, 't': t}))); time.sleep(gap * (0.5 + rng.random()))
    c.close()
def pct(l, p): return sorted(l)[max(int(len(l) * p) - 1, 0)]
def xacts(): return P.q("select xact_commit + xact_rollback from pg_stat_database where datname = 'postgres'")[0][0]

class PollRelay(threading.Thread):
    def __init__(self, tp, interval, batch=200, skip_locked=False, name=''):
        super().__init__(daemon=True); self.tp = tp; self.interval = interval; self.batch = batch; self.skip = skip_locked; self.stop_ = threading.Event(); self.pr = mk_producer(KN.port); self.sent = 0; self.go = threading.Event(); self.go.set()
    def run(self):
        self.pr.produce(self.tp, key='warm', value=json.dumps({'i': -1, 't': time.time()})); self.pr.flush(10)   # 先热身:第一条消息要建立到 broker 的连接
        self.go.wait(); c = P.conn(autocommit=False)
        while not self.stop_.is_set():
            lock = ' for update skip locked' if self.skip else ''
            cur = c.execute(f'select id, aggregate_id, payload from outbox where not sent order by id limit {self.batch}{lock}'); rows = cur.fetchall()
            for id_, agg, pl in rows: self.pr.produce(self.tp, key=agg, value=pl)
            if rows:
                self.pr.flush(10); c.execute('update outbox set sent = true where id = any(%s)', ([r[0] for r in rows],)); self.sent += len(rows)
            c.commit()
            time.sleep(self.interval)
        c.close()

print('== 一:轮询发布:轮询间隔越短,事件到达越快,但数据库被问得越频繁(每种间隔发 150 个事件,平均每 15 ms 一个;“空闲负载”是没有任何新事件时 5 秒里数据库完成的事务数)')
rows = []
for interval in (0.01, 0.1, 1.0):
    P.q('delete from outbox'); tp = topic(f'poll-{int(interval * 1000)}'); sk = Sink(tp); sk.start(); sk.ready.wait(20)
    rl = PollRelay(tp, interval); rl.start(); sk.warm.wait(20); load(150, 0.015); t0 = time.time()
    while len(sk.lat) < 150 and time.time() - t0 < 20: time.sleep(0.05)
    idle0 = xacts(); time.sleep(5.0); idle = xacts() - idle0
    rl.stop_.set(); sk.stop_.set(); rl.join(); sk.join(2)
    rows.append((f'每 {int(interval * 1000)} ms 轮询一次', len(sk.lat), f'{statistics.median(sk.lat) * 1000:.1f} ms', f'{pct(sk.lat, 0.99) * 1000:.1f} ms', f'{idle / 5:.0f}'))
table(rows, ['发布方式', '收到的事件', '延迟中位数', '延迟 p99', '空闲时数据库每秒事务数(≈轮询次数)'])
print('  延迟 ≈ 事件等到下一次轮询的时间(均匀分布时约为间隔的一半)再加发布耗时;间隔越短,空闲时对数据库的查询越多')
poll_rows = rows

print('== 二:自增 id 的顺序不是提交顺序:T1 先拿到 id、后提交,T2 后拿 id、先提交。“记住上次读到的最大 id”的轮询会永远错过 T1 的事件')
def conc_trial(rng, relay_kind, state):
    """T1 开事务插入(拿到较小的 id),T2 随后插入并先提交;随机的时间点之后 T1 才提交。返回两条事件各自有没有被读到。"""
    c1, c2 = P.conn(autocommit=False), P.conn(autocommit=False)
    c1.execute('insert into outbox(aggregate_id, payload) values (%s, %s) returning id', (f'T1-{state["n"]}', '{}')); c2.execute('insert into outbox(aggregate_id, payload) values (%s, %s)', (f'T2-{state["n"]}', '{}'))
    c2.commit(); time.sleep(rng.random() * 0.01)         # T2 先提交
    seen = poll(relay_kind, state) if rng.random() < 0.5 else []   # 轮询恰好落在两次提交之间的概率设成 50%
    c1.commit(); c1.close(); c2.close()                       # T1 后提交
    seen += poll(relay_kind, state); state['n'] += 1; return seen
def poll(kind, state):
    c = P.conn()
    if kind == 'cursor':                                      # 记住上次读到的最大 id
        rows = c.execute('select id, aggregate_id from outbox where id > %s order by id', (state['last'],)).fetchall()
        if rows: state['last'] = rows[-1][0]
    else:                                                     # 标志位:所有还没发的
        rows = c.execute('select id, aggregate_id from outbox where not sent order by id').fetchall()
        c.execute('update outbox set sent = true where id = any(%s)', ([r[0] for r in rows],))
    c.close(); return [r[1] for r in rows]
res = {}
for kind, name in (('cursor', '游标:id > 上次读到的最大 id'), ('flag', '标志位:where not sent')):
    P.q('delete from outbox'); state = {'last': 0, 'n': 0}; got = []; rng = random.Random(4)
    for _ in range(300): got += conc_trial(rng, kind, state)
    exp = 600; res[kind] = (len(set(got)), exp - len(set(got)))
table([(name, 600, res[k][0], res[k][1]) for k, name in (('cursor', '游标:id > 上次读到的最大 id'), ('flag', '标志位:where not sent'))], ['轮询方式', '应发出的事件', '实际读到', '丢失'])
print('  游标轮询只要恰好在“T2 提交了、T1 还没提交”的间隙里跑了一次(这里设成 50% 的概率),就会把游标推过 T1 的 id,T1 提交后永远读不到;标志位轮询不依赖 id 的顺序,没有丢失')

print('== 三:多个 relay 同时轮询:不加锁时同一批行会被几个 relay 都读到,重复发送;加 FOR UPDATE SKIP LOCKED 后各取各的(预先放 20000 个事件,批大小 200)')
rows = []
for k, skip in ((1, False), (2, False), (4, False), (2, True), (4, True)):
    dts = []; dup = tot = None
    for rep_ in range(3):
        P.q('delete from outbox'); c = P.conn(autocommit=False)
        for b in range(20): c.cursor().executemany("insert into outbox(aggregate_id, payload) values (%s, %s)", [(f'M{b}-{i}', json.dumps({'i': b * 1000 + i, 't': 0})) for i in range(1000)]); c.commit()
        c.close(); tp = topic(f'multi-{k}-{int(skip)}-{rep_}'); rls = [PollRelay(tp, 0.0, batch=200, skip_locked=skip) for _ in range(k)]
        [r.go.clear() for r in rls]; [r.start() for r in rls]; time.sleep(0.5)       # 各个 relay 先热身(各发一条热身消息),再同时放行
        t0 = time.time(); [r.go.set() for r in rls]
        while P.q('select count(*) from outbox where not sent')[0][0] > 0 and time.time() - t0 < 120: time.sleep(0.002)
        dts.append(time.time() - t0); [r.stop_.set() for r in rls]; [r.join() for r in rls]
        if rep_ == 0:
            keys = [e[0] for e in read_all(KN.port, tp, idle=1.5) if e[0] != 'warm']; tot = len(keys); dup = len(keys) - len(set(keys))
    dt = statistics.median(dts)
    rows.append((f'{k} 个 relay,{"FOR UPDATE SKIP LOCKED" if skip else "不加锁"}', f'{dt:.2f} s', f'{20000 / dt:.0f}', tot, dup))
table(rows, ['配置', '发完 20000 个用时(3 轮中位数)', '事件/秒', 'Kafka 里收到的条数(第 1 轮)', '重复的条数(第 1 轮)'])
print('  不加锁时,多开 relay 不但没有变快,还带来大量重复;SKIP LOCKED 让每个 relay 只取没被别人锁住的行,没有重复')

print('== 四:CDC(逻辑解码):不查表,直接读 WAL 里已提交事务的变更;和第二节同样的交错、第一节同样的负载,看延迟、顺序和丢失')
def start_cdc(tp, slot, rel='outbox'):
    subprocess.run([f'{PG_BIN}/pg_recvlogical', '-h', '127.0.0.1', '-p', str(P.port), '-U', 'postgres', '-d', 'postgres', '--slot', slot, '--create-slot', '--plugin', 'test_decoding'], capture_output=True, text=True, check=True)
    return CDCRelay(tp, slot)
class CDCRelay(threading.Thread):
    LINE = re.compile(r"^table public\.outbox: INSERT: id\[bigint\]:(\d+) aggregate_id\[text\]:'(.*?)' payload\[text\]:'(.*)' sent\[boolean\]")
    def __init__(self, tp, slot):
        super().__init__(daemon=True); self.tp = tp; self.slot = slot; self.pr = mk_producer(KN.port); self.n = 0; self.order = []
        self.pr.produce(tp, key='warm', value=json.dumps({'i': -1, 't': time.time()})); self.pr.flush(10)
        self.p = subprocess.Popen([f'{PG_BIN}/pg_recvlogical', '-h', '127.0.0.1', '-p', str(P.port), '-U', 'postgres', '-d', 'postgres', '--slot', slot, '--start', '-f', '-', '--no-loop'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    def run(self):
        for line in self.p.stdout:
            m = self.LINE.match(line.strip())
            if m:
                self.order.append(m.group(2)); self.pr.produce(self.tp, key=m.group(2), value=m.group(3)); self.pr.poll(0); self.n += 1
                if self.n % 50 == 0: self.pr.flush(5)
            else: self.pr.flush(5) if line.startswith('COMMIT') else None
        self.pr.flush(10)
    def stop(self):
        self.p.terminate(); self.p.wait(10)
P.q('delete from outbox'); tp = topic('cdc-lat'); sk = Sink(tp); sk.start(); sk.ready.wait(20)
cdc = start_cdc(tp, 'slot_lat'); cdc.start(); sk.warm.wait(20); time.sleep(0.5); load(150, 0.015); t0 = time.time()
while len(sk.lat) < 150 and time.time() - t0 < 20: time.sleep(0.05)
idle0 = xacts(); time.sleep(5.0); idle = xacts() - idle0
sk.stop_.set(); sk.join(2); cdc.stop(); cdc.join(5)
rows = poll_rows + [('CDC(逻辑解码)', len(sk.lat), f'{statistics.median(sk.lat) * 1000:.1f} ms', f'{pct(sk.lat, 0.99) * 1000:.1f} ms', f'{idle / 5:.0f}')]
table(rows, ['发布方式', '收到的事件', '延迟中位数', '延迟 p99', '空闲时数据库每秒事务数'])
subprocess.run([f'{PG_BIN}/pg_recvlogical', '-h', '127.0.0.1', '-p', str(P.port), '-U', 'postgres', '-d', 'postgres', '--slot', 'slot_lat', '--drop-slot'], capture_output=True)
# 第二节同样的交错,用 CDC 收
P.q('delete from outbox'); tp = topic('cdc-order'); cdc = start_cdc(tp, 'slot_ord'); cdc.start(); time.sleep(0.5); rng = random.Random(4); st = {'n': 0, 'last': 0}
for _ in range(300):
    c1, c2 = P.conn(autocommit=False), P.conn(autocommit=False)
    c1.execute('insert into outbox(aggregate_id, payload) values (%s, %s)', (f'T1-{st["n"]}', '{}')); c2.execute('insert into outbox(aggregate_id, payload) values (%s, %s)', (f'T2-{st["n"]}', '{}'))
    c2.commit(); time.sleep(rng.random() * 0.01); c1.commit(); c1.close(); c2.close(); st['n'] += 1
time.sleep(1.5); cdc.stop(); cdc.join(5); evs = read_all(KN.port, tp, idle=1.5); keys = [e[0] for e in evs if e[0] != 'warm']
inv = sum(1 for i in range(300) if keys.index(f'T2-{i}') < keys.index(f'T1-{i}')) if len(set(keys)) == 600 else -1
print(f'  同样的 300 组“T1 先拿 id、T2 先提交”:应发 600 个事件,CDC 收到 {len(set(keys))} 个不同的(丢失 {600 - len(set(keys))}),重复 {len(keys) - len(set(keys))};其中 {inv} 组里 Kafka 里的顺序是 T2 在 T1 前面 —— 事件按提交顺序出现,和 id 的大小无关')
subprocess.run([f'{PG_BIN}/pg_recvlogical', '-h', '127.0.0.1', '-p', str(P.port), '-U', 'postgres', '-d', 'postgres', '--slot', 'slot_ord', '--drop-slot'], capture_output=True)

print('== 五:CDC 的代价:复制槽会为还没读走的消费者保留 WAL。消费者停了,业务继续写,槽后面的 WAL 一直堆着')
P.q('delete from outbox'); tp = topic('cdc-lag')
subprocess.run([f'{PG_BIN}/pg_recvlogical', '-h', '127.0.0.1', '-p', str(P.port), '-U', 'postgres', '-d', 'postgres', '--slot', 'slot_lag', '--create-slot', '--plugin', 'test_decoding'], capture_output=True, check=True)
def lag(): 
    r = P.q("select active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) from pg_replication_slots where slot_name = 'slot_lag'")[0]; return r[0], int(r[1])
a, b0 = lag(); print(f'  刚建好的槽:active={a},落后当前 WAL {b0 / 1024:.0f} KiB')
c = P.conn(autocommit=False)
for rnd in range(1, 4):
    for b in range(30): c.cursor().executemany("insert into outbox(aggregate_id, payload) values (%s, %s)", [(f'L{rnd}-{b}-{i}', 'x' * 200) for i in range(1000)]); c.commit()
    P.q('checkpoint'); a, bl = lag(); print(f'  消费者没在读,又写了 3 万个事件(共 {rnd * 30000} 个,每个 payload 200 字节),做一次 checkpoint 后:active={a},槽落后 {bl / 1024 / 1024:.1f} MiB,pg_wal 目录里 {len(os.listdir(P.d / "data" / "pg_wal"))} 个文件')
c.close()
cdc = CDCRelay(tp, 'slot_lag'); t0 = time.time(); cdc.start()
while cdc.n < 90000 and time.time() - t0 < 120: time.sleep(0.05)
dt = time.time() - t0; time.sleep(1.0); P.q('checkpoint'); a, bl = lag()
print(f'  消费者回来之后一口气追上 {cdc.n} 个事件,用时 {dt:.1f} s({cdc.n / dt:.0f} 事件/秒);刚追上就 checkpoint,槽还是落后 {bl / 1024:.0f} KiB,pg_wal 里 {len(os.listdir(P.d / "data" / "pg_wal"))} 个文件(槽的位置要等消费者向服务器汇报进度才会前进)')
time.sleep(11.0); P.q('checkpoint'); a, bl2 = lag()
print(f'  消费者继续连着、过了 11 秒(pg_recvlogical 默认每 10 秒汇报一次进度)再 checkpoint:槽落后 {bl2 / 1024:.0f} KiB,pg_wal 里 {len(os.listdir(P.d / "data" / "pg_wal"))} 个文件')
cdc.stop(); cdc.join(5)
print('  消费者长时间不回来,WAL 会一直堆到磁盘写满(PostgreSQL 13+ 可以用 max_slot_wal_keep_size 给槽设上限,超出后槽失效,这一项没有实验)')
KN.stop(); reset(); ql.reset(); shutil.rmtree(TT / 'pg_t12', ignore_errors=True); shutil.rmtree(HERE / 'qtmp' / 't12k', ignore_errors=True)
