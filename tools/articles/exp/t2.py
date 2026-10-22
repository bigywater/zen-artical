import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from tpc import Coord, pgconn
tee('t2'); reset()
A = PG('t2_a', conf={'wal_sync_method': 'fsync'}); B = PG('t2_b', conf={'wal_sync_method': 'fsync'})
ths = [threading.Thread(target=n.start) for n in (A, B)]; [t.start() for t in ths]; [t.join() for t in ths]
A.q('create table orders(id int primary key, status text)'); B.q('create table stock(sku text primary key, qty int)'); B.q("insert into stock values('sku-1', 100), ('sku-2', 100)")
B.q('create table orders(id int primary key, status text)')   # 对照用:订单和库存放在同一个实例里
print(f'两个独立的 PostgreSQL 实例:订单库(端口 {A.port})有 orders 表,库存库(端口 {B.port})有 stock 表;{A.q("show max_prepared_transactions")[0][0]} 个允许同时存在的 prepared 事务;{A.q("select version()")[0][0].split(",")[0]}')
W = {'订单库': ["insert into orders values(%d, 'CREATED')"], '库存库': ["update stock set qty = qty - 1 where sku='sku-1'"]}
def st():
    return (A.q('select count(*) from orders')[0][0], B.q("select qty from stock where sku='sku-1'")[0][0])

print('== 一:手动走一遍两阶段:阶段一两边各 PREPARE TRANSACTION(此时数据还不可见);阶段二两边各 COMMIT PREPARED')
ca, cb = pgconn(A.port), pgconn(B.port)
print('  初始:订单库 %d 条订单,库存库 sku-1=%d' % st())
ca.execute('begin'); ca.execute("insert into orders values(1, 'CREATED')"); print("  订单库  BEGIN; INSERT INTO orders ...")
cb.execute('begin'); cb.execute("update stock set qty = qty - 1 where sku='sku-1'"); print("  库存库  BEGIN; UPDATE stock SET qty = qty - 1 ...")
print("  订单库  PREPARE TRANSACTION 'tx-1' ->", ca.execute("prepare transaction 'tx-1'").statusmessage)
print("  库存库  PREPARE TRANSACTION 'tx-1' ->", cb.execute("prepare transaction 'tx-1'").statusmessage)
for name, n in (('订单库', A), ('库存库', B)):
    print(f"  {name} pg_prepared_xacts:", [(g, o, d) for g, o, d in n.q('select gid, owner, database from pg_prepared_xacts')])
print('  prepare 之后别的会话看到:订单库 %d 条订单,库存库 sku-1=%d  (两个修改都还不可见)' % st())
print("  订单库  COMMIT PREPARED 'tx-1' ->", ca.execute("commit prepared 'tx-1'").statusmessage)
print("  库存库  COMMIT PREPARED 'tx-1' ->", cb.execute("commit prepared 'tx-1'").statusmessage)
print('  提交后:订单库 %d 条订单,库存库 sku-1=%d;pg_prepared_xacts 里剩 %s / %s' % (st() + (A.q('select count(*) from pg_prepared_xacts')[0][0], B.q('select count(*) from pg_prepared_xacts')[0][0])))
ca.close(); cb.close()

print("== 二:PREPARE 之后连接断开,事务还在,行锁还在;别的会话读不被挡(读到旧值),写同一行被挡")
B.q("update stock set qty = 100 where sku='sku-1'")
c = pgconn(B.port); c.execute('begin'); c.execute("update stock set qty = qty - 1 where sku='sku-1'"); c.execute("prepare transaction 'tx-2'"); c.close()
print("  协调者的连接已关闭。pg_prepared_xacts:", B.q('select gid, owner from pg_prepared_xacts'))
print('  pg_locks 里属于它的锁(pid 为空 = 没有会话持有):')
for r in B.q("select locktype, mode, granted, pid is null as 无会话, coalesce(relation::regclass::text, '-') from pg_locks where pid is null order by locktype, mode, 5"): print('   ', r)
t0 = time.perf_counter(); v = B.q("select qty from stock where sku='sku-1'")[0][0]; print(f'  别的会话 SELECT:读到 qty={v}(旧值),用时 {ms(time.perf_counter() - t0)},没有被挡')
c2 = pgconn(B.port); c2.execute("set lock_timeout = '1500ms'")
t0 = time.perf_counter()
try: c2.execute("update stock set qty = qty - 5 where sku='sku-1'")
except Exception as e: print(f'  别的会话 UPDATE 同一行(lock_timeout=1500ms):{type(e).__name__} {str(e).splitlines()[0]},等了 {ms(time.perf_counter() - t0)}')
c2.close()
res = {}
def blocked_update():
    cc = pgconn(B.port); t0 = time.perf_counter(); cc.execute("update stock set qty = qty - 5 where sku='sku-1'"); res['wait'] = time.perf_counter() - t0; cc.close()
th = threading.Thread(target=blocked_update); th.start(); time.sleep(1.2)
B.q("commit prepared 'tx-2'"); th.join()
qty2 = B.q("select qty from stock where sku='sku-1'")[0][0]
print(f"  另一个会话的 UPDATE 阻塞着,1.2 秒后协调者 COMMIT PREPARED 'tx-2':它等了 {ms(res['wait'])} 后返回;最终 qty={qty2}(100 - 1 - 5)")

print('== 三:PREPARE 之后整个 PostgreSQL 被 kill -9,重启后事务还在(prepare 时就写进了 WAL),锁也被恢复')
B.q("update stock set qty = 100 where sku='sku-1'")
c = pgconn(B.port); c.execute('begin'); c.execute("update stock set qty = qty - 1 where sku='sku-1'"); c.execute("prepare transaction 'tx-3'")
B.kill(); print('  kill -9 postmaster 和全部子进程')
try: c.close()
except Exception: pass
t0 = time.perf_counter(); B.start(); print(f'  重启用时 {ms(time.perf_counter() - t0)}')
print('  重启后 pg_prepared_xacts:', B.q('select gid from pg_prepared_xacts'))
c2 = pgconn(B.port); c2.execute("set lock_timeout = '800ms'")
try: c2.execute("update stock set qty = qty - 5 where sku='sku-1'")
except Exception as e: print(f'  重启后别的会话 UPDATE 同一行:{type(e).__name__} {str(e).splitlines()[0]}(行锁被恢复了)')
c2.close()
cc = pgconn(B.port); print("  COMMIT PREPARED 'tx-3' ->", cc.execute("commit prepared 'tx-3'").statusmessage); cc.close()
print('  提交后 qty=%d' % B.q("select qty from stock where sku='sku-1'")[0][0])
log_lines = [l for l in B.log().splitlines() if 'prepared transaction' in l.lower() or 'recovery' in l.lower()]
print('  PostgreSQL 日志里和恢复有关的行:'); [print('   ', l.split('] ', 1)[-1][:140]) for l in log_lines[-5:]]

print('== 四:代价:同样“建订单 + 扣库存”两个修改,放在一个实例里提交 vs 跨两个实例做 2PC;每个事务 fsync 几次、慢多少(各 300 次)')
N = 300
def walsync(n): return n.q('select wal_sync from pg_stat_wal')[0][0]
B.q("update stock set qty = 1000000 where sku='sku-1'")
lc = pgconn(B.port); lat1 = []
a0, b0 = walsync(A), walsync(B)
for i in range(N):
    t0 = time.perf_counter(); lc.execute('begin'); lc.execute("insert into orders values(%d, 'X')" % (10000 + i)); lc.execute("update stock set qty = qty - 1 where sku='sku-1'"); lc.execute('commit'); lat1.append(time.perf_counter() - t0)
lc.close(); time.sleep(1.5)
a1, b1 = walsync(A), walsync(B)
sync1 = (a1 - a0) + (b1 - b0)
co = Coord({'订单库': A.port, '库存库': B.port}, str(TT / 't2_decision.sqlite3'), say=lambda *x: None)
conns = {'订单库': pgconn(A.port), '库存库': pgconn(B.port)}; lat2 = []
W2 = {'订单库': ["insert into orders values(%d, 'X')"], '库存库': ["update stock set qty = qty - 1 where sku='sku-1'"]}
a0, b0 = walsync(A), walsync(B)
for i in range(N):
    w = {'订单库': [W2['订单库'][0] % (20000 + i)], '库存库': W2['库存库']}
    t0 = time.perf_counter(); r = co.run(f'bench-{i}', w, conns=conns); lat2.append(time.perf_counter() - t0); assert r == 'COMMIT'
for c in conns.values(): c.close()
time.sleep(1.5)
a1, b1 = walsync(A), walsync(B)
sync2 = (a1 - a0) + (b1 - b0)
def pct(l, p): return sorted(l)[int(len(l) * p) - 1]
print(f'  一个实例里一个事务:中位数 {ms(statistics.median(lat1))},p99 {ms(pct(lat1, 0.99))};两个实例合计 WAL fsync {sync1} 次 = 每个事务 {sync1 / N:.2f} 次')
print(f'  两个实例做 2PC:  中位数 {ms(statistics.median(lat2))},p99 {ms(pct(lat2, 0.99))};两个实例合计 WAL fsync {sync2} 次 = 每个事务 {sync2 / N:.2f} 次')
print(f'  2PC / 单实例:中位数 {statistics.median(lat2) / statistics.median(lat1):.1f} 倍;fsync {sync2 / max(sync1, 1):.1f} 倍(协调者自己写决定日志的 fsync 不在这里面,它写在 SQLite 里)')

print('== 五:阶段一和阶段二之间的这段时间,行锁一直被持有:协调者在 PREPARE 之后多等 hold 毫秒再提交,两个线程连续对同一行做 2PC,吞吐被这段时间卡死')
def hot(rows, hold, per=20):
    def worker(tid):
        co = Coord({'订单库': A.port, '库存库': B.port}, str(TT / f't2_dec_{tid}.sqlite3'), say=lambda *x: None)
        conns = {'订单库': pgconn(A.port), '库存库': pgconn(B.port)}
        for i in range(per):
            sku = rows[tid]
            co.run(f'h-{hold}-{tid}-{i}-{random.random()}', {'订单库': ["insert into orders values(%d, 'H')" % (random.randrange(10 ** 9))], '库存库': [f"update stock set qty = qty - 1 where sku='{sku}'"]}, hold=hold / 1000, conns=conns)
        for c in conns.values(): c.close()
    t0 = time.perf_counter(); ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
    return 2 * per / (time.perf_counter() - t0)
rows_out = []; base = None
for hold in (0, 50, 200):
    same = hot(['sku-1', 'sku-1'], hold); diff = hot(['sku-1', 'sku-2'], hold)
    if base is None: base = 1000 / same   # hold=0 时同一行上一次 2PC 本身占多少毫秒
    rows_out.append((f'{hold} ms', f'{same:.0f}', f'{1000 / (hold + base):.0f}', f'{diff:.0f}', f'{diff / same:.1f}'))
table(rows_out, ['prepare 之后多等', '两线程抢同一行 (事务/秒)', '估算 1000/(hold+%.1f ms)' % base, '两线程各用各的行 (事务/秒)', '各自的行 / 同一行'])
print('  同一行上的事务是一个接一个排队的:每个事务占着行锁的时间 = 2PC 自己的耗时 + hold;不同行的事务互不影响,仍然能并行')
reset()
for n in ('pg_t2_a', 'pg_t2_b'): shutil.rmtree(TT / n, ignore_errors=True)
for f in TT.glob('t2_*'): f.unlink()
