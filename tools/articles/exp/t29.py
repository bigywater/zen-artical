import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import pymysql
tee('t29'); reset()
M = MySQL('t29', opts=['--innodb-purge-threads=4', '--innodb-lock-wait-timeout=50']).start(); M.q('create database shop')
M.q('create table hot(id int primary key, v int)', db='shop'); M.q('insert into hot values (1, 0), (2, 0)', db='shop')
M.q('create table t(id int primary key, a int)', db='shop'); M.q('insert into t values (1, 1), (2, 2)', db='shop')
print(f'MySQL {M.q("select version()")[0][0]}(InnoDB,默认 REPEATABLE-READ,innodb_lock_wait_timeout 默认 50 秒,实验里按需在会话里调小);PostgreSQL 16.15 用在第四节')
def hist_len():
    r = M.q('show engine innodb status')[0][2]; m = re.search(r'History list length (\d+)', r); return int(m.group(1)) if m else -1
def conn(**kw): return M.conn('shop', autocommit=False, **kw)

print('== 一:长事务让 undo 越积越多,也让它自己的快照读越来越慢:A 开一个一致性快照事务(读一次就闲着),别的会话给同一行更新 6 万次')
A = conn(); ca = A.cursor(); ca.execute('start transaction with consistent snapshot'); ca.execute('select v from hot where id = 1'); a0 = ca.fetchone()[0]
print(f'  A:START TRANSACTION WITH CONSISTENT SNAPSHOT,读到 v = {a0};此刻 History list length = {hist_len()}')
B = conn(); cb = B.cursor(); marks = []
for k in range(600):
    for _ in range(100): cb.execute('update hot set v = v + 1 where id = 1')
    B.commit()
    if (k + 1) % 150 == 0: marks.append(((k + 1) * 100, hist_len()))
print('  更新次数 → History list length:' + ',  '.join(f'{n} → {h}' for n, h in marks))
print('  (History list length 数的是还没清理的 undo 日志单位——每个提交的事务一个——不是行版本的个数;这里每 100 次更新提交一次,所以每 15000 次更新涨 150 左右。真正按着不放的是 6 万个行版本)')
def timeit(c, n=20):
    cur = c.cursor(); lat = []
    for _ in range(n): t0 = time.perf_counter(); cur.execute('select v from hot where id = 1'); r = cur.fetchone()[0]; lat.append(time.perf_counter() - t0)
    return statistics.median(lat) * 1000, r
la, ra = timeit(A); C = conn(); lc, rc = timeit(C)
print(f'  A 的快照读同一行:读到 {ra}(快照里的旧值),单次耗时中位数 {la:.2f} ms;新会话读同一行:读到 {rc},单次耗时中位数 {lc:.2f} ms —— A 要顺着 6 万个版本的 undo 链往回找到它快照里的那一版')
A.commit(); t0 = time.time()
while hist_len() > 100 and time.time() - t0 < 60: time.sleep(0.2)
print(f'  A 提交之后,purge 线程把 undo 清掉:History list length 回到 {hist_len()},用了 {time.time() - t0:.1f} s')
la2, _ = timeit(A); print(f'  A 提交后再读同一行(新快照):单次耗时中位数 {la2:.2f} ms')
A.close(); B.close(); C.close()

print('== 二:长事务持有的行锁让别人等:A 更新 id=1 之后迟迟不提交;B 把 innodb_lock_wait_timeout 调成 1 秒,再去更新同一行。以及超时之后事务本身是什么状态')
M.q('update hot set v = 0', db='shop')
A = conn(); ca = A.cursor(); ca.execute('update hot set v = 100 where id = 1')
B = conn(); cb = B.cursor(); cb.execute('set session innodb_lock_wait_timeout = 1'); cb.execute('begin'); cb.execute('update hot set v = 200 where id = 2'); t0 = time.perf_counter()
try: cb.execute('update hot set v = 300 where id = 1'); print('  B 更新 id=1:成功(不该发生)')
except Exception as e: print(f'  B 先改了 id=2(成功),再改被 A 锁住的 id=1:等了 {(time.perf_counter() - t0) * 1000:.0f} ms 后报错 {e.args[0]} {e.args[1][:50]}')
cb.execute('select v from hot where id = 2'); v2 = cb.fetchone()[0]; cb.execute("select count(*) from information_schema.innodb_trx where trx_mysql_thread_id = connection_id()"); open_ = cb.fetchone()[0]
print(f'  超时之后 B 这个事务还开着吗:innodb_trx 里有 {open_} 条属于它的记录;它自己读 id=2 = {v2}(第一条 UPDATE 还在事务里,没有被回滚)—— 默认只回滚超时的那一条语句,不回滚整个事务')
B.commit(); print('  如果应用只是捕获了异常、没有 ROLLBACK 就继续往下走并最终 COMMIT:这一半的修改就被提交了,库里 id=2 =', M.q('select v from hot where id = 2', db='shop')[0][0], '(本该和 id=1 的修改一起成功或一起失败)')
A.rollback(); A.close(); B.close()

print('== 三:长事务和 DDL:A 开着事务读了一下表 t(拿着元数据锁),B 执行 ALTER TABLE 要等 A;而 B 在等的时候,后面来的普通 SELECT 也被排在 B 后面一起卡住')
A = conn(); ca = A.cursor(); ca.execute('begin'); ca.execute('select * from t')
res = {}
def ddl():
    c = conn(); t0 = time.perf_counter(); c.cursor().execute('alter table t add column c int'); res['ddl'] = time.perf_counter() - t0; c.close()
def sel():
    c = conn(); t0 = time.perf_counter(); c.cursor().execute('select * from t limit 1'); res['sel'] = time.perf_counter() - t0; c.close()
td = threading.Thread(target=ddl); td.start(); time.sleep(0.3); ts = threading.Thread(target=sel); ts.start(); time.sleep(1.2)
pl = [(r[0], r[4], r[6]) for r in M.q('show full processlist', db='shop') if r[6] and 'metadata' in str(r[6])]
print(f'  1.5 秒时 processlist 里在等元数据锁的会话:{[(f"线程 {a}", st) for a, _, st in pl]}')
time.sleep(0.5); A.commit(); td.join(); ts.join()
print(f'  A 提交(事务结束)之后:ALTER 用了 {res["ddl"]:.2f} s 才完成(其中 2 秒是在等 A),后来的普通 SELECT 用了 {res["sel"]:.2f} s(它本身是 0.1 ms 的查询,却在 ALTER 后面排了队)')
A.close()

print('== 四:PostgreSQL 的长事务:idle in transaction 的会话按住快照,VACUUM 清不掉死元组;设置 idle_in_transaction_session_timeout 之后会话被服务器断开,VACUUM 才能清')
P = PG('t29', conf={'autovacuum': 'off'}).start(); P.q('create table churn(id int primary key, v int)'); P.q('insert into churn select g, 0 from generate_series(1, 5000) g')
def vac():
    notes = []; c = P.conn(); c.add_notice_handler(lambda d: notes.append(d.message_primary)); c.execute('vacuum (verbose) churn'); c.close()
    return [l for m in notes for l in m.splitlines() if l.startswith('tuples:') or l.startswith('removable cutoff')]
x = P.conn(autocommit=False); x.execute('set idle_in_transaction_session_timeout = 0'); x.execute('begin isolation level repeatable read'); x.execute('select count(*) from churn').fetchone()
for _ in range(5): P.q('update churn set v = v + 1')
print('  会话 X:BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT ...(之后闲着);别的会话把 churn 表(5000 行)整体 UPDATE 了 5 次,然后 VACUUM:')
for l in vac(): print('    ' + l)
print('  pg_stat_activity 里 X 的状态:', [tuple(r) for r in P.q("select state, now() - xact_start > interval '0' as long_tx from pg_stat_activity where state like 'idle in transaction%'")])
P.q("select pg_terminate_backend(pid) from pg_stat_activity where state = 'idle in transaction'")       # 等价于服务器按 idle_in_transaction_session_timeout 把它断开
try: x.execute('select 1'); print('  X 还能用(不该发生)')
except Exception as e: print(f'  会话 X 被服务器断开之后再用它:{type(e).__name__}')
print('  X 断开之后再 VACUUM:')
for l in vac(): print('    ' + l)
y = P.conn(autocommit=False); y.execute("set idle_in_transaction_session_timeout = '700ms'"); y.execute('begin'); y.execute('select 1').fetchone(); time.sleep(1.2)
try: y.execute('select 1'); print('  设置了 idle_in_transaction_session_timeout = 700ms 的会话:1.2 秒后还能用(不该发生)')
except Exception as e: print(f'  设置了 idle_in_transaction_session_timeout = 700ms 的会话:事务里闲了 1.2 秒后再用它,得到 {type(e).__name__}: {str(e).splitlines()[0]}')
P.stop()

print('== 五:找出并处理长事务:监控查询 innodb_trx(事务开始超过 N 秒的),watchdog 对超过 1.5 秒的事务 KILL;20 个事务里有 5 个故意拖 3 秒才提交')
M.q('update hot set v = 0', db='shop'); M.q('delete from t', db='shop'); M.q('alter table t drop column c', db='shop') if False else None
M.q('create table if not exists w(id int primary key, who varchar(10))', db='shop'); M.q('delete from w', db='shop')
stop = threading.Event(); killed = []
def watchdog():
    c = M.conn('shop')
    while not stop.is_set():
        cur = c.cursor(); cur.execute("select trx_mysql_thread_id, timestampdiff(microsecond, trx_started, now(6)) / 1e6, trx_rows_modified from information_schema.innodb_trx where timestampdiff(microsecond, trx_started, now(6)) > 1500000")
        for tid, age, rows in cur.fetchall():
            try: cur.execute(f'kill {int(tid)}'); killed.append((tid, round(float(age), 2), rows))
            except Exception: pass
        time.sleep(0.2)
    c.close()
wt = threading.Thread(target=watchdog); wt.start(); out = {}
def worker(i, slow):
    try:
        c = conn(); cur = c.cursor(); cur.execute('insert into w values (%s, %s)', (i, 'slow' if slow else 'fast'))
        if slow: time.sleep(3.0)
        c.commit(); out[i] = '提交成功'; c.close()
    except Exception as e: out[i] = f'被中断:{type(e).__name__} {e.args[0] if e.args else ""}'
ths = [threading.Thread(target=worker, args=(i, i % 4 == 0)) for i in range(20)]; [t.start() for t in ths]; [t.join() for t in ths]; time.sleep(0.5); stop.set(); wt.join()
ok = sum(1 for v in out.values() if v == '提交成功'); cut = sum(1 for v in out.values() if v.startswith('被中断'))
print(f'  20 个事务:{ok} 个提交成功,{cut} 个被 watchdog 中断;watchdog 的记录(线程号、事务年龄 s、已修改行数):{killed}')
print(f'  库里 w 表有 {M.q("select count(*) from w", db="shop")[0][0]} 行(都是提交成功的 {ok} 个;被杀的事务,修改随连接断开一起回滚),全部是 fast 的:{M.q("select count(*) from w where who = %s", ("fast",), db="shop")[0][0]} 行')
print('  只按“开了多久”杀事务会误伤合法的慢事务(比如批处理),所以 watchdog 的阈值、白名单和告警都要按业务定;杀之前最好先告警')
reset(); shutil.rmtree(TT / 'my_t29', ignore_errors=True); shutil.rmtree(TT / 'pg_t29', ignore_errors=True)
