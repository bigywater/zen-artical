import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from percolator import *
tee('t23'); reset()
M = MySQL('t23').start(); ST = Store(M)
print(f'Percolator 风格的事务,自己写的最小实现(tools/articles/percolator.py,Python + MySQL {M.q("select version()")[0][0]}):data(k, ts, v) 多版本值、lk(k, ts, pk, expire) 锁(每个 key 一把,记着主锁是哪个 key)、wr(k, commit_ts, start_ts) 提交记录、tso 单调递增时间戳;锁的 TTL 设成 1.5 秒;不是 Google 的 Percolator,也不是 TiKV')
def dump(label):
    d = [tuple(r) for r in M.q('select k, ts, v from data order by k, ts', db='perc')]; l = [tuple(r) for r in M.q('select k, ts, pk from lk order by k', db='perc')]; w = [tuple(r) for r in M.q('select k, commit_ts, start_ts from wr order by k, commit_ts', db='perc')]
    print(f'  {label}')
    print(f'    data(k, ts, v):{d}'); print(f'    lock(k, ts, 主锁):{l}'); print(f'    write(k, commit_ts, start_ts):{w}')
def seed(vals):
    ST.reset(); t = Txn(ST)
    for k, v in vals.items(): t.set(k, v)
    t.commit()

print('== 一:一次转账(A 的 100 转 50 给 B)的提交过程:预写 → 提交主锁 → 提交次锁,每一步之后三张表里是什么')
seed({'A': 100, 'B': 0}); dump('初始(已提交):')
t = Txn(ST); a, b = t.get('A'), t.get('B'); t.set('A', a - 50); t.set('B', b + 50)
t.prewrite(); dump(f'预写之后(start_ts={t.start_ts},主锁 = {t.primary},B 上的锁指向 A):')
t.commit_ts = ST.tso(); ST._commit_key(t.primary, t.start_ts, t.commit_ts); dump(f'提交主锁 A 之后(commit_ts={t.commit_ts}):A 有了提交记录、锁没了;B 还有锁 —— 此刻这个事务已经算提交了:')
ST._commit_key('B', t.start_ts, t.commit_ts); dump('提交次锁 B 之后(锁全部清掉):')
tr = Txn(ST); print(f'  新事务(start_ts={tr.start_ts})读到 A = {tr.get("A")},B = {tr.get("B")}')

print('== 二:快照读与写写冲突(先提交者赢):T1 先开始,T2 之后开始并提交了对 x 的修改;T1 再读 x 仍是旧值,T1 想写 x 提交时发现更新的提交记录,中止')
seed({'x': 1}); t1 = Txn(ST); t2 = Txn(ST); t2.set('x', 2); t2.commit()
print(f'  T1(start_ts={t1.start_ts})读 x = {t1.get("x")}(T2 在 commit_ts={t2.commit_ts} 提交了 x = 2,T1 的快照看不到);新事务读 x = {Txn(ST).get("x")}')
t1.set('x', 10)
try: t1.commit()
except Conflict as e: print(f'  T1 提交:预写失败 —— {e};锁 / 数据都已清理:lock 行数 {M.q("select count(*) from lk", db="perc")[0][0]}')

print('== 三:客户端在预写之后、提交主锁之前被 kill -9:两个锁留在库里,谁碰到谁处理;读到的人要等主锁过期再回滚整个事务')
CHILD = r'''
import sys, time, pymysql
sys.path.insert(0, sys.argv[1])
from percolator import *
class FM:
    def __init__(self, sock): self.sock = sock
    def conn(self, db, autocommit=True, **kw): return pymysql.connect(unix_socket=self.sock, user='root', password='', database=db, autocommit=autocommit)
    def q(self, sql, args=None, db=None):
        c = self.conn(db); cur = c.cursor(); cur.execute(sql, args); r = cur.fetchall(); c.close(); return r
st = Store(FM(sys.argv[2])); t = Txn(st, ttl_ms=1500)
a, b = t.get('A'), t.get('B'); t.set('A', a - 50); t.set('B', b + 50)
r = t.commit(crash=sys.argv[3]); print('WAIT', flush=True); time.sleep(60)
'''
(TT / 't23_child.py').write_text(CHILD)
def crash_child(point):
    p = subprocess.Popen([sys.executable, str(TT / 't23_child.py'), str(HERE), M.sock, point], stdout=subprocess.PIPE, text=True)
    while not p.stdout.readline().startswith('WAIT'): pass
    os.kill(p.pid, signal.SIGKILL); p.wait()
seed({'A': 100, 'B': 0}); crash_child('after_prewrite'); dump('kill -9 之后:')
ST.stats.update(resolved_forward=0, resolved_back=0, waits=0); r = Txn(ST); t0 = time.perf_counter(); vb = r.get('B'); dt = time.perf_counter() - t0
print(f'  新事务读 B:等了 {dt * 1000:.0f} ms(锁的 TTL 是 1500 ms,过期之前主锁还可能属于一个正在进行的事务,只能等)才读到 B = {vb};等待轮询 {ST.stats["waits"]} 次,回滚了 {ST.stats["resolved_back"]} 把锁')
print(f'  再读 A = {r.get("A")}(A 的锁在回滚 B 时已经一并清掉);lock 行数 {M.q("select count(*) from lk", db="perc")[0][0]},data 行 {[tuple(x) for x in M.q("select k, ts, v from data order by k, ts", db="perc")]}')

print('== 四:客户端在提交主锁之后、提交次锁之前被 kill -9:事务已经提交(主锁一提交就算),B 上的锁是个遗留物,读到它的人看一眼主锁就前滚,不用等')
seed({'A': 100, 'B': 0}); crash_child('after_primary'); dump('kill -9 之后(A 已提交、B 的锁还在):')
r = Txn(ST); naive_b = ST.get_ignoring_locks('B', r.start_ts); naive_a = ST.get_ignoring_locks('A', r.start_ts)
print(f'  只看提交记录、不管锁的读:A = {naive_a},B = {naive_b},合计 {naive_a + naive_b}(应该是 100)—— 看到了转账的一半')
ST.stats.update(resolved_forward=0, resolved_back=0, waits=0); t0 = time.perf_counter(); vb = r.get('B'); dt = time.perf_counter() - t0; va = r.get('A')
print(f'  会处理锁的读:B = {vb}(用时 {dt * 1000:.1f} ms,没有等待:前滚了 {ST.stats["resolved_forward"]} 把锁),A = {va},合计 {va + vb}')
dump('读之后:B 的锁被换成了提交记录:')

print('== 五:压力下的一致性:10 个账户各 100(总额 1000),6 个线程各做 100 次随机转账;每次转账有 5% 概率在预写之后“崩溃”(留下锁)、5% 概率在主锁提交之后“崩溃”;另外 2 个读线程不断对全部 10 个账户做快照读并检查总额')
seed({f'acc{i}': 100 for i in range(10)}); stop = threading.Event(); chk = {'aware': [0, 0], 'blind': [0, 0]}; ck = threading.Lock(); outc = {'committed': 0, 'conflict': 0, 'crash_pre': 0, 'crash_primary': 0}; ol = threading.Lock()
def reader(aware):
    key = 'aware' if aware else 'blind'
    while not stop.is_set():
        ts = ST.tso()
        try: tot = sum((ST.get(f'acc{i}', ts) if aware else ST.get_ignoring_locks(f'acc{i}', ts)) or 0 for i in range(10))
        except Conflict: continue
        with ck: chk[key][0] += 1; chk[key][1] += (tot != 1000)
def writer(seed_):
    rng = random.Random(seed_)
    for _ in range(100):
        a, b = rng.sample(range(10), 2); amt = rng.randrange(1, 20); r = rng.random()
        try:
            t = Txn(ST, ttl_ms=300); va = t.get(f'acc{a}'); vb = t.get(f'acc{b}'); t.set(f'acc{a}', va - amt); t.set(f'acc{b}', vb + amt)
            res = t.commit(crash='after_prewrite' if r < 0.05 else ('after_primary' if r < 0.10 else None))
            with ol: outc['committed' if res != 'CRASH' else ('crash_pre' if r < 0.05 else 'crash_primary')] += 1
        except (Conflict, Aborted):
            with ol: outc['conflict'] += 1
rs = [threading.Thread(target=reader, args=(True,)), threading.Thread(target=reader, args=(True,)), threading.Thread(target=reader, args=(False,))]; ws = [threading.Thread(target=writer, args=(s,)) for s in range(6)]
t0 = time.perf_counter(); [t.start() for t in rs + ws]; [t.join() for t in ws]; dt = time.perf_counter() - t0; time.sleep(0.5); stop.set(); [t.join() for t in rs]
ts = ST.tso(); final = [ST.get(f'acc{i}', ts) for i in range(10)]
print(f'  600 次转账用时 {dt:.1f} s:{outc};读线程处理锁的次数:前滚 {ST.stats["resolved_forward"]}、回滚 {ST.stats["resolved_back"]}、等待轮询 {ST.stats["waits"]}')
print(f'  会处理锁的快照读:{chk["aware"][0]} 次检查,总额 ≠ 1000 的 {chk["aware"][1]} 次;不管锁的读:{chk["blind"][0]} 次检查,总额 ≠ 1000 的 {chk["blind"][1]} 次')
print(f'  全部处理完之后的最终快照:{final},合计 {sum(final)};lock 行数 {M.q("select count(*) from lk", db="perc")[0][0]}')
reset(); (TT / 't23_child.py').unlink(missing_ok=True); shutil.rmtree(TT / 'my_t23', ignore_errors=True)
