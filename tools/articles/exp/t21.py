import sys, os, json, pymysql; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from at import *
tee('t21'); reset()
M = MySQL('t21').start()
for db in ('acct_db', 'stock_db'): M.q(f'create database {db}')
M.q('create table account(id int primary key, balance int)', db='acct_db'); M.q('create table stock(id int primary key, qty int)', db='stock_db')
TC_ = TC(M); RA = RM(M, 'acct_db', TC_, 'acct'); RS = RM(M, 'stock_db', TC_, 'stock')
print(f'MySQL {M.q("select version()")[0][0]}:acct_db(account、undo_log)、stock_db(stock、undo_log)、tc_db(global_lock、global_tx);AT 的实现是我自己写的 Python(tools/articles/at.py),分支执行 = 本地事务里“前镜像 → 改 → 后镜像 → 写 undo_log → 申请全局锁 → 本地提交”,全局提交只删 undo_log 与全局锁,全局回滚按后镜像校验、按前镜像恢复;它不是 Seata,只是同样的思路')
def reset_data():
    for db, t in (('acct_db', 'account'), ('stock_db', 'stock'), ('acct_db', 'undo_log'), ('stock_db', 'undo_log'), ('tc_db', 'global_lock'), ('tc_db', 'global_tx')): M.q(f'delete from {t}', db=db)
    M.q('insert into account values (1, 1000), (2, 1000)', db='acct_db'); M.q('insert into stock values (1, 50), (2, 50)', db='stock_db')
def acct(i=1): return M.q('select balance from account where id = %s', (i,), db='acct_db')[0][0]
def stk(i=1): return M.q('select qty from stock where id = %s', (i,), db='stock_db')[0][0]
def gtx_begin(xid): TC_.begin(xid)
def gtx_commit(xid):
    TC_.set_status(xid, 'COMMITTED')
    for rm in (RA, RS): rm.commit_global(xid)
    TC_.release(xid)
def gtx_rollback(xid):
    TC_.set_status(xid, 'ROLLBACK'); out = []
    for rm in (RS, RA): out += rm.rollback_global(xid)
    TC_.release(xid); return out

print('== 一:一次全局事务的两个分支(账户扣 100、库存扣 3),全局提交之前与之后:undo_log、全局锁、别人能看到什么')
reset_data(); xid = 'xid-1'; gtx_begin(xid)
RA.branch_update(xid, 'account', 1, 'balance = balance - %s', [100]); RS.branch_update(xid, 'stock', 1, 'qty = qty - %s', [3])
print('  两个分支都已经本地提交,全局事务还没决定:')
print('   账户 RM 的 undo_log:', [(r[0], r[1], r[2], json.loads(r[3]) if isinstance(r[3], str) else r[3], json.loads(r[4]) if isinstance(r[4], str) else r[4]) for r in M.q('select xid, tbl, pk, before_image, after_image from undo_log', db='acct_db')])
print('   库存 RM 的 undo_log:', [(r[0], r[1], r[2], json.loads(r[3]) if isinstance(r[3], str) else r[3], json.loads(r[4]) if isinstance(r[4], str) else r[4]) for r in M.q('select xid, tbl, pk, before_image, after_image from undo_log', db='stock_db')])
print('   tc_db.global_lock:', [tuple(r) for r in M.q('select rid, pk, xid from global_lock', db='tc_db')])
print(f'   别的会话此刻读到:账户 {acct()}、库存 {stk()} —— 分支已经本地提交,新值对所有人可见(全局事务还没提交)')
gtx_commit(xid)
print(f'  全局提交之后:undo_log 行数 {M.q("select count(*) from undo_log", db="acct_db")[0][0]} + {M.q("select count(*) from undo_log", db="stock_db")[0][0]},global_lock 行数 {M.q("select count(*) from global_lock", db="tc_db")[0][0]};账户 {acct()}、库存 {stk()}')

print('== 二:全局回滚:第二个分支失败,按 undo_log 的前镜像把第一个分支恢复回去')
reset_data(); xid = 'xid-2'; gtx_begin(xid)
RA.branch_update(xid, 'account', 1, 'balance = balance - %s', [100]); print(f'  分支 1(账户扣 100)已本地提交:账户 {acct()}')
print('  分支 2(库存)失败 → 全局回滚')
out = gtx_rollback(xid)
print(f'  回滚动作:{[(t, p, b) for t, p, b in out]};回滚之后:账户 {acct()}、库存 {stk()},undo_log 行数 {M.q("select count(*) from undo_log", db="acct_db")[0][0]},global_lock 行数 {M.q("select count(*) from global_lock", db="tc_db")[0][0]}')

print('== 三:全局锁防止脏写:T1 改了账户 1 之后停 1 秒才决定;本地行锁在分支提交时就释放了,T2 想改同一行。有全局锁 / 没有全局锁两种')
def two_tx(use_gl, t1_decision, lock_timeout):
    reset_data(); res = {}
    def t1():
        gtx_begin('T1'); RA.branch_update('T1', 'account', 1, 'balance = balance - %s', [100], use_global_lock=use_gl); res['t1_branch'] = time.perf_counter(); time.sleep(1.0)
        try:
            (gtx_commit if t1_decision == 'commit' else gtx_rollback)('T1'); res['t1'] = 'ok'
        except DirtyWrite as e: res['t1'] = f'回滚失败:{str(e)[:90]}...'
    th = threading.Thread(target=t1); th.start(); time.sleep(0.2); t0 = time.perf_counter()
    try:
        gtx_begin('T2'); _, _, waited = RA.branch_update('T2', 'account', 1, 'balance = balance - %s', [10], lock_timeout=lock_timeout, use_global_lock=use_gl); res['t2'] = f'分支成功,等全局锁 {waited * 1000:.0f} ms'; res['t2_done'] = time.perf_counter() - t0
        gtx_commit('T2')
    except LockConflict as e: res['t2'] = f'分支失败:{e}'
    th.join(); return res
r = two_tx(True, 'commit', 3.0); print(f'  有全局锁,T1 提交:T2 {r["t2"]}(T2 在 T1 的全局提交之后才拿到锁);T1 {r["t1"]};最终账户 {acct()}(1000 - 100 - 10)')
r = two_tx(True, 'commit', 0.3); print(f'  有全局锁、T2 只愿意等 0.3 s:T2 {r["t2"]};T1 {r["t1"]};最终账户 {acct()}')
r = two_tx(False, 'rollback', 0.3); print(f'  没有全局锁、T1 决定回滚:T2 立刻成功({r["t2"]});T1 {r["t1"]};账户现在是 {acct()}(T1 想把它恢复成 1000,但 T2 已经又扣了 10:不能直接恢复)')

print('== 四:全局事务之外的写入(没有全局事务、不知道全局锁的普通 UPDATE)也会造成脏写;让普通写入先检查全局锁(类似 Seata 的 @GlobalLock)可以补上')
def outsider(check_lock):
    reset_data(); gtx_begin('T1'); RA.branch_update('T1', 'account', 1, 'balance = balance - %s', [100]); res = {}
    def plain():
        t0 = time.perf_counter()
        if check_lock:
            while TC_.holder('acct.account', 1): time.sleep(0.005)                      # 先等全局锁释放
        c = M.conn('acct_db'); c.cursor().execute('update account set balance = balance + 5 where id = 1'); c.close(); res['wait'] = time.perf_counter() - t0
    th = threading.Thread(target=plain); th.start(); time.sleep(0.5)
    try: out = gtx_rollback('T1'); r = '回滚成功'
    except DirtyWrite as e: r = f'回滚失败(脏写):{str(e)[str(e).index("当前值"):][:60]}...'
    th.join(); return r, res['wait']
r, w = outsider(False); print(f'  普通写入不看全局锁:它立刻写入(等了 {w * 1000:.0f} ms);T1 全局回滚:{r};账户 {acct()}')
r, w = outsider(True); print(f'  普通写入先看全局锁:它等了 {w * 1000:.0f} ms(T1 回滚完成之后才写);T1 全局回滚:{r};账户 {acct()}(1000 恢复后再 +5)')

print('== 五:读:分支已经本地提交,全局事务回滚之前,别人读到的就是“还没确定”的值(默认相当于全局读未提交)。100 个全局事务各“扣 100、停 20 ms、回滚”,另一个线程不停读余额')
reset_data(); stop = threading.Event(); seen = {}
def reader():
    c = M.conn('acct_db'); cur = c.cursor()
    while not stop.is_set():
        cur.execute('select balance from account where id = 1'); v = cur.fetchone()[0]; seen[v] = seen.get(v, 0) + 1
rt = threading.Thread(target=reader); rt.start()
for i in range(100):
    xid = f'r{i}'; gtx_begin(xid); RA.branch_update(xid, 'account', 1, 'balance = balance - %s', [100]); time.sleep(0.02); gtx_rollback(xid)
stop.set(); rt.join()
total = sum(seen.values()); print(f'  读线程共读了 {total} 次,读到的余额值分布 {dict(sorted(seen.items()))};其中读到 900(一个最终被回滚、从未真正生效的值)的有 {seen.get(900, 0)} 次({seen.get(900, 0) / total * 100:.0f}%)')
print('  需要读到“已经确定”的值时,读之前要先看全局锁(或用 SELECT FOR UPDATE 并让它等全局锁),相当于把读也串到全局事务后面')

print('== 六:代价:一次分支更新 vs 普通的本地更新(每个单独一次提交);8 个线程各改自己的行,各 300 次')
M.q('delete from account', db='acct_db'); [M.q('insert into account values (%s, 1000000)', (i,), db='acct_db') for i in range(1, 9)]
def plain_op(i, k):
    c = plain_conns[k]; c.cursor().execute('update account set balance = balance - 1 where id = %s', (k + 1,)); c.commit()
plain_conns = [M.conn('acct_db', autocommit=False) for _ in range(8)]
DL = [0]
def bench(fn, per=300):
    lat = []; lk = threading.Lock()
    def w(k):
        loc = []
        for i in range(per):
            t0 = time.perf_counter()
            while True:
                try: fn(i, k); break
                except pymysql.err.OperationalError as e:
                    if e.args[0] != 1213: raise
                    with lk: DL[0] += 1                      # 死锁:回滚后重试这一次操作
                    for rm in (RA,):
                        try: rm.c().rollback()
                        except Exception: pass
            loc.append(time.perf_counter() - t0)
        with lk: lat.extend(loc)
    t0 = time.perf_counter(); ts = [threading.Thread(target=w, args=(k,)) for k in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]; dt = time.perf_counter() - t0
    return statistics.median(lat), 8 * per / dt
def at_op(i, k):
    xid = f'p{k}-{i}-{time.time_ns()}'; TC_.begin(xid); RA.branch_update(xid, 'account', k + 1, 'balance = balance - %s', [1]); RA.commit_global(xid); TC_.release(xid)
def at_branch_only(i, k):
    xid = f'q{k}-{i}-{time.time_ns()}'; RA.branch_update(xid, 'account', k + 1, 'balance = balance - %s', [1]); RA.commit_global(xid); TC_.release(xid)
rows = []
res = {n: [] for n in ('plain', 'at-branch', 'at-full')}
for rnd in range(3):
    res['plain'].append(bench(plain_op)); res['at-branch'].append(bench(at_branch_only)); res['at-full'].append(bench(at_op))
for n, name in (('plain', '普通本地更新(1 条 UPDATE + 提交)'), ('at-branch', 'AT 分支(前镜像、改、后镜像、undo、全局锁、提交)+ 全局提交清理'), ('at-full', '上一项 + TC 里记录全局事务的开始与状态')):
    r = res[n]; rows.append((name, f'{statistics.median(x[0] for x in r) * 1e6:.0f} µs', f'{statistics.median(x[1] for x in r):.0f}'))
table(rows, ['写法', '单次延迟中位数', '8 线程吞吐(次/秒,3 轮中位数)'])
print(f'  AT 路径上 8 个线程各改自己的行(互不冲突),3 轮共遇到 {DL[0]} 次 InnoDB 死锁(提示 1213;具体死在哪两条语句上我没有追查),重试后成功;普通本地更新没有出现')
print('  一次 AT 分支更新比普通更新多 4 条语句(前镜像、后镜像、undo_log、全局锁)和一次全局提交时的清理;换来的是业务代码里只有普通的 SQL')
for c in plain_conns: c.close()
reset(); shutil.rmtree(TT / 'my_t21', ignore_errors=True)
