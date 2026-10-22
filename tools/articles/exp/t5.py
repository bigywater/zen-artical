import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t5'); reset()
M = MySQL('t5_a'); M2 = MySQL('t5_b')
ths = [threading.Thread(target=n.start) for n in (M, M2)]; [t.start() for t in ths]; [t.join() for t in ths]
for n in (M, M2): n.q('create database shop')
M.q('create table orders(id int primary key, status varchar(10))', db='shop'); M.q('create table stock(sku varchar(10) primary key, qty int)', db='shop'); M.q("insert into stock values('sku-1', 100)", db='shop')
M2.q('create table stock(sku varchar(10) primary key, qty int)', db='shop'); M2.q("insert into stock values('sku-1', 100)", db='shop')
print(f'MySQL {M.q("select version()")[0][0]},binlog_format={M.q("select @@binlog_format")[0][0]},sync_binlog={M.q("select @@sync_binlog")[0][0]},innodb_flush_log_at_trx_commit={M.q("select @@innodb_flush_log_at_trx_commit")[0][0]},innodb_lock_wait_timeout={M.q("select @@innodb_lock_wait_timeout")[0][0]};两个独立实例:A(端口 {M.port})、B(端口 {M2.port})')
def err(e): return f'{type(e).__name__} {e.args[0]} {e.args[1][:110]}'
def run(c, sql, show=True):
    cur = c.cursor()
    try:
        cur.execute(sql); r = cur.fetchall() if cur.description else None
        if show: print(f'  mysql> {sql}' + (f'   -> {r}' if r else '   -> OK'))
        return r
    except Exception as e:
        if show: print(f'  mysql> {sql}   -> 错误:{err(e)}')
        return e

print('== 一:XA 的语句流程:XA START → 业务语句 → XA END → XA PREPARE → XA COMMIT;每一步之后能执行什么,实际试一遍')
c = M.conn('shop'); o = M.conn('shop')
run(c, "XA START 'x1'"); run(c, "INSERT INTO orders VALUES (1, 'CREATED')")
run(c, "COMMIT")                                   # ACTIVE 状态下直接 COMMIT
run(c, "XA PREPARE 'x1'")                          # 没有 XA END 就 PREPARE
run(c, "XA END 'x1'"); run(c, "INSERT INTO orders VALUES (2, 'CREATED')")   # IDLE 状态下再写
run(c, "XA PREPARE 'x1'"); run(c, "SELECT 1")      # PREPARED 状态下再执行语句
print('  另一个会话此时看到的订单数:', run(o, 'SELECT COUNT(*) FROM orders', show=False)[0][0], '(prepare 了但还没 commit,不可见)')
print('  XA RECOVER:', run(o, 'XA RECOVER', show=False))
run(o, "XA COMMIT 'x1'")                           # 用另一个会话提交
print('  提交后订单数:', run(o, 'SELECT COUNT(*) FROM orders', show=False)[0][0], ',XA RECOVER:', run(o, 'XA RECOVER', show=False))
c.close(); o.close()

print('== 二:连接断开会怎样:XA END 之后(还没 PREPARE)断开 → 回滚;XA PREPARE 之后断开 → 事务留在服务端,换个连接还能提交')
M.q('delete from orders', db='shop')
c = M.conn('shop'); run(c, "XA START 'y1'", show=False); run(c, "INSERT INTO orders VALUES (11, 'A')", show=False); run(c, "XA END 'y1'", show=False); c.close()
print('  XA START;INSERT;XA END 之后断开连接:XA RECOVER =', M.q('XA RECOVER'), ',订单数 =', M.q('select count(*) from orders', db='shop')[0][0], '(没 prepare 的 XA 事务随连接一起回滚)')
c = M.conn('shop'); run(c, "XA START 'y2'", show=False); run(c, "INSERT INTO orders VALUES (12, 'B')", show=False); run(c, "XA END 'y2'", show=False); run(c, "XA PREPARE 'y2'", show=False); c.close()
print("  XA PREPARE 之后断开连接:XA RECOVER =", M.q('XA RECOVER'), ',订单数 =', M.q('select count(*) from orders', db='shop')[0][0])
o = M.conn('shop'); run(o, "XA COMMIT 'y2'"); print('  换一个连接 XA COMMIT 之后订单数 =', M.q('select count(*) from orders', db='shop')[0][0]); o.close()

print('== 三:prepare 之后行锁一直握着:别的会话读到旧值,写同一行等到 innodb_lock_wait_timeout')
M.q("update stock set qty = 100 where sku='sku-1'", db='shop')
c = M.conn('shop'); run(c, "XA START 'z1'", show=False); run(c, "UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'", show=False); run(c, "XA END 'z1'", show=False); run(c, "XA PREPARE 'z1'", show=False); c.close()
o = M.conn('shop'); run(o, 'SET SESSION innodb_lock_wait_timeout = 2', show=False)
print('  别的会话 SELECT qty:', run(o, "SELECT qty FROM stock WHERE sku='sku-1'", show=False)[0][0], '(旧值)')
t0 = time.perf_counter(); e = run(o, "UPDATE stock SET qty = qty - 5 WHERE sku='sku-1'", show=False)
print(f'  别的会话 UPDATE 同一行:{err(e)},等了 {ms(time.perf_counter() - t0)}')
print('  information_schema.innodb_trx(trx_state, trx_mysql_thread_id, trx_rows_locked, trx_started 距现在多少秒):', [(a, b, c_, d) for a, b, c_, d in M.q('select trx_state, trx_mysql_thread_id, trx_rows_locked, timestampdiff(second, trx_started, now()) from information_schema.innodb_trx')], '—— 这个 prepared 的事务在里面显示成 RUNNING,线程号 0(已经没有连接了)')
o.close(); M.q("XA ROLLBACK 'z1'")

print('== 四:prepare 之后 kill -9 整个 mysqld:重启后 XA RECOVER 还能看到,行锁被恢复;没 prepare 的 XA 事务重启后消失;binlog 里记着 XA PREPARE')
M.q("update stock set qty = 100 where sku='sku-1'", db='shop'); M.q('delete from orders', db='shop')
c = M.conn('shop'); run(c, "XA START 'k1'", show=False); run(c, "UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'", show=False); run(c, "XA END 'k1'", show=False); run(c, "XA PREPARE 'k1'", show=False)
c2 = M.conn('shop'); run(c2, "XA START 'k2'", show=False); run(c2, "INSERT INTO orders VALUES (21, 'K')", show=False)    # 还在 ACTIVE
M.kill(); print('  kill -9 mysqld(此时 k1 已 PREPARE,k2 还在 ACTIVE)')
for x in (c, c2):
    try: x.close()
    except Exception: pass
t0 = time.perf_counter(); M.start(); print(f'  重启用时 {ms(time.perf_counter() - t0)}')
print('  重启后 XA RECOVER:', M.q('XA RECOVER'), ',订单数(k2 的插入):', M.q('select count(*) from orders', db='shop')[0][0])
o = M.conn('shop'); run(o, 'SET SESSION innodb_lock_wait_timeout = 2', show=False)
e = run(o, "UPDATE stock SET qty = qty - 5 WHERE sku='sku-1'", show=False); print('  重启后别的会话 UPDATE 同一行:', err(e), '(行锁在恢复时被重新持有)')
run(o, "XA COMMIT 'k1'"); print('  XA COMMIT 之后 qty =', M.q("select qty from stock where sku='sku-1'", db='shop')[0][0]); o.close()
logs = M.q('show binary logs'); evs = []
for name, *_ in logs:
    for r in M.q(f"show binlog events in '{name}'"):
        if r[5].upper().startswith('XA'): evs.append((name, r[2], r[5][:70]))
print('  binlog 里的 XA 相关事件:'); [print('   ', e) for e in evs]
err_lines = [l.split('] ', 2)[-1][:150] for l in M.errlog().splitlines() if 'XA' in l or 'prepared' in l.lower()]
print('  mysqld 错误日志里和 XA / prepared 有关的行:'); [print('   ', l) for l in err_lines[-6:]]

print('== 五:代价(每种写法 3 轮交替、每轮 200 次,共 600 次;每次 = 往订单表 INSERT 一行 + 往库存表 UPDATE 一行):普通事务 vs 同一个实例里的 XA vs 跨两个实例的 XA')
N = 200
def fsyncs(n): return int(n.q("show global status like 'Innodb_os_log_fsyncs'")[0][1])
M.q("update stock set qty = 1000000 where sku='sku-1'", db='shop'); M2.q("update stock set qty = 1000000 where sku='sku-1'", db='shop'); M.q('delete from orders', db='shop')
ctr = [0]
def bench(fn):
    lat = []; f0 = fsyncs(M) + fsyncs(M2)
    for i in range(N): ctr[0] += 1; t0 = time.perf_counter(); fn(ctr[0]); lat.append(time.perf_counter() - t0)
    return lat, fsyncs(M) + fsyncs(M2) - f0
ca = M.conn('shop'); cb = M2.conn('shop')
def local(i):
    cur = ca.cursor(); cur.execute('BEGIN'); cur.execute('INSERT INTO orders VALUES (%s, %s)', (100000 + i, 'L')); cur.execute("UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'"); cur.execute('COMMIT')
def xa_one(i):
    cur = ca.cursor(); x = f"'o{i}'"
    cur.execute(f'XA START {x}'); cur.execute('INSERT INTO orders VALUES (%s, %s)', (200000 + i, 'X')); cur.execute("UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'"); cur.execute(f'XA END {x}'); cur.execute(f'XA PREPARE {x}'); cur.execute(f'XA COMMIT {x}')
def xa_two(i):
    x = f"'t{i}'"; a = ca.cursor(); b = cb.cursor()
    a.execute(f'XA START {x}'); a.execute('INSERT INTO orders VALUES (%s, %s)', (300000 + i, 'T')); a.execute(f'XA END {x}')
    b.execute(f'XA START {x}'); b.execute("UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'"); b.execute(f'XA END {x}')
    a.execute(f'XA PREPARE {x}'); b.execute(f'XA PREPARE {x}'); a.execute(f'XA COMMIT {x}'); b.execute(f'XA COMMIT {x}')
def pct(l, p): return sorted(l)[int(len(l) * p) - 1]
rows = []
base = None
cases = (('普通事务(一个实例)', local), ('XA(同一个实例,走完 prepare + commit)', xa_one), ('XA(跨两个实例)', xa_two))
acc = {n: ([], 0) for n, _ in cases}
for rnd in range(3):
    for name, fn in cases:
        lat, fs = bench(fn); acc[name] = (acc[name][0] + lat, acc[name][1] + fs)
for name, fn in cases:
    lat, fs = acc[name]; med = statistics.median(lat)
    if base is None: base = med
    rows.append((name, ms(med), ms(pct(lat, 0.99)), f'{fs / len(lat):.2f}', f'{med / base:.1f}x'))
table(rows, ['写法', '中位数', 'p99', '每个事务的 redo fsync(两个实例合计)', '相对普通事务'])
print('  redo fsync 来自 Innodb_os_log_fsyncs;binlog 的 fsync(sync_binlog=1)没有计在内,因为没有对应的状态变量')
print('  一个事务里每条语句平均引起几次 redo fsync(Innodb_os_log_fsyncs 的增量,单个实例,各重复 200 个事务取平均;单次测量会被后台刷盘线程干扰,BEGIN 这类不写日志的语句也会量到约 0.1 的本底):')
cur = ca.cursor()
def avg_steps(stmts, reps=200):
    tot = [0] * len(stmts)
    for r in range(reps):
        ctr[0] += 1
        for k, (q, a) in enumerate(stmts):
            f0 = fsyncs(M); cur.execute(q.replace('@ID', str(ctr[0])), (500000 + ctr[0], 'S') if a else None); tot[k] += fsyncs(M) - f0
    return [t / reps for t in tot]
stm = [('BEGIN', 0), ('INSERT INTO orders VALUES (%s, %s)', 1), ("UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'", 0), ('COMMIT', 0)]
r = avg_steps(stm); print('   普通事务:' + ',  '.join(f'{q.split()[0]} {v:.2f}' for (q, _), v in zip(stm, r)) + f'  合计 {sum(r):.2f}')
stx = [("XA START 'p@ID'", 0), ('INSERT INTO orders VALUES (%s, %s)', 1), ("UPDATE stock SET qty = qty - 1 WHERE sku='sku-1'", 0), ("XA END 'p@ID'", 0), ("XA PREPARE 'p@ID'", 0), ("XA COMMIT 'p@ID'", 0)]
r = avg_steps(stx); print('   XA 事务:  ' + ',  '.join(f"{' '.join(q.split()[:2])} {v:.2f}" for (q, _), v in zip(stx, r)) + f'  合计 {sum(r):.2f}')
ca.close(); cb.close()
reset()
for n in ('my_t5_a', 'my_t5_b'): shutil.rmtree(TT / n, ignore_errors=True)
