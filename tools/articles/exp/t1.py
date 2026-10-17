import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t1'); reset()

# 三个独立的 MySQL 实例:订单库、库存库、钱包库
nodes = {'订单库': MySQL('t1_ord'), '库存库': MySQL('t1_stk'), '钱包库': MySQL('t1_wal')}
ths = [threading.Thread(target=n.start) for n in nodes.values()]
[t.start() for t in ths]; [t.join() for t in ths]
ORD, STK, WAL = nodes['订单库'], nodes['库存库'], nodes['钱包库']
DDL_ORD = 'create table orders(id bigint primary key, user_id int, sku varchar(20), qty int, amount int, status varchar(10))'
DDL_STK = 'create table stock(sku varchar(20) primary key, qty int, constraint stock_ok check (qty >= 0))'
DDL_WAL = 'create table wallet(user_id int primary key, balance int, constraint wallet_ok check (balance >= 0))'
for n, ddl in ((ORD, DDL_ORD), (STK, DDL_STK), (WAL, DDL_WAL)):
    n.q('create database shop'); n.q(ddl, db='shop')
# 再起一个实例,三张表都放在里面,用来做“单库”对照
SG = MySQL('t1_single').start(); SG.q('create database shop')
for ddl in (DDL_ORD, DDL_STK, DDL_WAL): SG.q(ddl, db='shop')
print(f'三个独立的 mysqld(订单库 {ORD.port}、库存库 {STK.port}、钱包库 {WAL.port})加一个放着全部三张表的 mysqld(单库对照 {SG.port});版本 {SG.q("select version()")[0][0]},隔离级别 {SG.q("select @@transaction_isolation")[0][0]}')


def seed(user_balance=1000, stock=10):
    for n, tbls in ((ORD, ['orders']), (STK, ['stock']), (WAL, ['wallet']), (SG, ['orders', 'stock', 'wallet'])):
        for t in tbls: n.q(f'delete from {t}', db='shop')
    for n in (STK, SG): n.q("insert into stock values('sku-1', %s)", (stock,), db='shop')
    for n in (WAL, SG): n.q("insert into wallet values(1, %s)", (user_balance,), db='shop')


def state(label_n=None):
    o = ORD.q('select count(*) from orders', db='shop')[0][0]
    s = STK.q("select qty from stock where sku='sku-1'", db='shop')[0][0]
    w = WAL.q('select balance from wallet where user_id=1', db='shop')[0][0]
    return o, s, w


def state_single():
    o = SG.q('select count(*) from orders', db='shop')[0][0]
    s = SG.q("select qty from stock where sku='sku-1'", db='shop')[0][0]
    w = SG.q('select balance from wallet where user_id=1', db='shop')[0][0]
    return o, s, w


# ---------------------------------------------------------------- 一
print('== 一:三张表在同一个实例里:下单 = 建订单 + 扣库存 + 扣余额,放进一个本地事务;余额不够时第三步失败,前两步跟着回滚')
seed(user_balance=50, stock=10)
print('  初始(单库):订单 %d 条,sku-1 库存 %d,用户 1 余额 %d' % state_single())
c = SG.conn('shop', autocommit=False)
cur = c.cursor()
print('  BEGIN')
cur.execute("insert into orders values(1001, 1, 'sku-1', 1, 80, 'CREATED')"); print('  insert into orders ...                      -> OK(事务内可见,还没提交)')
cur.execute("update stock set qty = qty - 1 where sku='sku-1'"); print('  update stock set qty = qty - 1 ...          -> OK')
try:
    cur.execute("update wallet set balance = balance - 80 where user_id=1")
except Exception as e:
    print('  update wallet set balance = balance - 80 ... -> 失败:%s' % (e.args,))
    c.rollback(); print('  ROLLBACK')
c.close()
print('  回滚后(单库):订单 %d 条,sku-1 库存 %d,用户 1 余额 %d  —— 三张表都回到了初始值' % state_single())

# ---------------------------------------------------------------- 二
print('== 二:同样的三步,表分别在三个实例里:每个实例只能提交自己的事务,第三步失败时前两步已经提交,没法回滚')
seed(user_balance=50, stock=10)
print('  初始(拆开后):订单库 %d 条,库存库 sku-1=%d,钱包库 用户 1 余额=%d' % state())
co, cs, cw = ORD.conn('shop', autocommit=False), STK.conn('shop', autocommit=False), WAL.conn('shop', autocommit=False)
co.cursor().execute("insert into orders values(1001, 1, 'sku-1', 1, 80, 'CREATED')"); co.commit(); print('  订单库:insert + COMMIT      -> OK')
cs.cursor().execute("update stock set qty = qty - 1 where sku='sku-1'"); cs.commit(); print('  库存库:update + COMMIT      -> OK')
try:
    cw.cursor().execute("update wallet set balance = balance - 80 where user_id=1"); cw.commit()
except Exception as e:
    print('  钱包库:update              -> 失败:%s' % (e.args,))
    cw.rollback(); print('  钱包库:ROLLBACK(只回滚了自己这一步)')
for c in (co, cs, cw): c.close()
print('  结果:订单库 %d 条,库存库 sku-1=%d,钱包库 用户 1 余额=%d  —— 订单存在、库存少了 1、钱没扣:三个库对这单的看法不一致' % state())

# ---------------------------------------------------------------- 三
print('== 三:不是业务失败,而是调用方进程在两次提交之间被 kill -9:订单库 → 库存库 → 钱包库 的顺序,在每个间隙杀一次')
CHILD = r'''
import sys, time, pymysql
def conn(sock): return pymysql.connect(unix_socket=sock, user='root', password='', database='shop', autocommit=False)
socks = sys.argv[1:4]; crash_after = int(sys.argv[4])
steps = [(0, "insert into orders values(1001, 1, 'sku-1', 1, 80, 'CREATED')"), (1, "update stock set qty = qty - 1 where sku='sku-1'"), (2, "update wallet set balance = balance - 80 where user_id=1")]
if crash_after == 0: print('WAIT', 0, flush=True); time.sleep(60)
for k, sql in steps:
    c = conn(socks[k]); c.cursor().execute(sql); c.commit(); c.close(); print('COMMITTED', k + 1, flush=True)
    if crash_after == k + 1: print('WAIT', k + 1, flush=True); time.sleep(60)
print('DONE', flush=True)
'''
(TT / 't1_child.py').write_text(CHILD)
rows = []
labels = {0: '第 1 次提交之前', 1: '订单库提交之后', 2: '库存库提交之后', 3: '钱包库提交之后(全部完成)'}
for k in range(4):
    seed(user_balance=1000, stock=10)
    p = subprocess.Popen([sys.executable, str(TT / 't1_child.py'), ORD.sock, STK.sock, WAL.sock, str(k)], stdout=subprocess.PIPE, text=True)
    while True:
        l = p.stdout.readline()
        if l.startswith('WAIT'): break
    os.kill(p.pid, signal.SIGKILL); p.wait()
    o, s, w = state()
    verdict = '一致' if (o, s, w) in ((0, 10, 1000), (1, 9, 920)) else '不一致'
    rows.append((f'kill -9 于:{labels[k]}', o, 10 - s, 1000 - w, verdict))
table(rows, ['进程在哪个位置被杀', '订单数', '库存扣了', '余额扣了', '结论'])
print('  只有“一次都没提交”和“三次都提交”两种状态是一致的;中间的两个间隙里,进程一死,数据就永远停在半截')

# ---------------------------------------------------------------- 四
print('== 四:把“每一步有 5% 的概率失败(超时、对端报错、连接断)”加进去,下 2000 单,看多少单落在半截状态')
N, P = 2000, 0.05
def run(split, seed_=7):
    rng = random.Random(seed_)
    seed(user_balance=10 ** 9, stock=10 ** 6)
    tally = {'成功': 0, '第 1 步就失败(什么都没留下)': 0, '第 2 步失败(订单已存在)': 0, '第 3 步失败(订单存在且库存已扣)': 0}
    if split:
        cs_ = [ORD.conn('shop'), STK.conn('shop'), WAL.conn('shop')]
        sqls = ["insert into orders values(%s, 1, 'sku-1', 1, 80, 'CREATED')", "update stock set qty = qty - 1 where sku='sku-1'", "update wallet set balance = balance - 80 where user_id=1"]
        for i in range(N):
            for k in range(3):
                if rng.random() < P:
                    tally[['第 1 步就失败(什么都没留下)', '第 2 步失败(订单已存在)', '第 3 步失败(订单存在且库存已扣)'][k]] += 1; break
                cs_[k].cursor().execute(sqls[k], (i,) if k == 0 else None)
            else: tally['成功'] += 1
        [c.close() for c in cs_]
        o, s, w = ORD.q('select count(*) from orders', db='shop')[0][0], 10 ** 6 - STK.q("select qty from stock", db='shop')[0][0], (10 ** 9 - WAL.q('select balance from wallet', db='shop')[0][0]) // 80
    else:
        c = SG.conn('shop', autocommit=False); cur = c.cursor()
        sqls = ["insert into orders values(%s, 1, 'sku-1', 1, 80, 'CREATED')", "update stock set qty = qty - 1 where sku='sku-1'", "update wallet set balance = balance - 80 where user_id=1"]
        for i in range(N):
            failed = None
            for k in range(3):
                if rng.random() < P: failed = k; break
                cur.execute(sqls[k], (i,) if k == 0 else None)
            if failed is None: c.commit(); tally['成功'] += 1
            else:
                c.rollback(); tally[['第 1 步就失败(什么都没留下)', '第 2 步失败(订单已存在)', '第 3 步失败(订单存在且库存已扣)'][failed]] += 1
        c.close()
        o, s, w = SG.q('select count(*) from orders', db='shop')[0][0], 10 ** 6 - SG.q("select qty from stock", db='shop')[0][0], (10 ** 9 - SG.q('select balance from wallet', db='shop')[0][0]) // 80
    return tally, (o, s, w)
for name, split in (('三个实例(每步各自提交)', True), ('一个实例(一个事务)', False)):
    t, (o, s, w) = run(split)
    inc = t['第 2 步失败(订单已存在)'] + t['第 3 步失败(订单存在且库存已扣)'] if split else 0
    print(f'  {name}:{N} 单,按程序里的记录 ' + ',  '.join(f'{k}={v}' for k, v in t.items()))
    print(f'    从数据库里数出来:订单 {o} 条,库存扣了 {s},余额折合 {w} 单   —— ' + ('三个数字不相等,按单对账会有差' if not (o == s == w) else '三个数字完全相等'))
    print(f'    不一致的单数 = {inc}({inc / N * 100:.1f}%)')
    if split: inc_split = inc
th = (1 - P) * P + (1 - P) ** 2 * P
sd = (N * th * (1 - th)) ** 0.5
print(f'  理论值:第 2、3 步失败的概率 = (1-p)p + (1-p)^2 p = {th * 100:.2f}%,{N} 单期望 {th * N:.0f} 单,标准差约 {sd:.0f} 单;实测 {inc_split} 单,差 {abs(inc_split - th * N):.0f} 单(随机数固定种子 7)')

# ---------------------------------------------------------------- 五
print('== 五:一个实例的本地事务到底保证了什么:事务没提交时 kill -9 mysqld,重启后已提交的在、没提交的没有(崩溃恢复靠自己的 redo/undo,别的实例管不了)')
seed(user_balance=1000, stock=10)
SG.q('delete from orders', db='shop')
SG.q("insert into orders values(1, 1, 'sku-1', 1, 80, 'CREATED')", db='shop')
c = SG.conn('shop', autocommit=False); cur = c.cursor()
cur.execute("insert into orders values(2, 1, 'sku-1', 1, 80, 'CREATED')"); cur.execute("update stock set qty = qty - 5 where sku='sku-1'")
print('  事务内可见:订单 %s,库存 %s(订单 2 与库存 -5 都还没 COMMIT)' % (cur.execute('select count(*) from orders') and cur.fetchone()[0], (cur.execute("select qty from stock where sku='sku-1'"), cur.fetchone()[0])[1]))
SG.kill(); print('  kill -9 mysqld')
try: c.close()
except Exception: pass
SG.start()
print('  重启后:订单 %s 条(%s),库存 %s' % (SG.q('select count(*) from orders', db='shop')[0][0], [r[0] for r in SG.q('select id from orders order by id', db='shop')], SG.q("select qty from stock where sku='sku-1'", db='shop')[0][0]))
rec = [l.split('] ', 2)[-1][:150] for l in SG.errlog().splitlines() if any(w in l.lower() for w in ('recovery', 'rolling back', 'rollback', 'crash', 'redo', 'undo', 'transactions'))]
print('  错误日志里和恢复有关的行:' + (('\n    ' + '\n    '.join(rec[:6])) if rec else '(没有匹配到)'))
print('  本地事务的原子性来自这一个实例自己的日志;订单库的日志管不了库存库里发生了什么')
reset()
(TT / 't1_child.py').unlink()
for n in ('t1_ord', 't1_stk', 't1_wal', 't1_single'): shutil.rmtree(TT / ('my_' + n), ignore_errors=True)
