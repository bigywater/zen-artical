import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t10'); reset()
M = MySQL('t10').start(); M.q('create database bank')
M.q('create table acct(user_id int primary key, balance int, pending int default 0)', db='bank'); M.q('create table inv(sku varchar(10) primary key, qty int, pending int default 0)', db='bank')
print(f'一个 MySQL {M.q("select version()")[0][0]} 里的 bank 库:acct(user_id, balance, pending)、inv(sku, qty, pending);Saga 的每个步骤各自一个本地事务(autocommit),步骤之间别的事务随时可以读写;时间窗口用真实 sleep')
def conn(): return M.conn('bank')
def q1(c, sql, a=None):
    cur = c.cursor(); cur.execute(sql, a); return cur.fetchone()

print('== 一:脏读:Saga 第一步扣掉 800(已提交),第二步失败、100 ms 后补偿加回 800;同时一个“额度审批”服务每 5 ms 读一次余额(规则:余额 >= 500 才批准贷款)')
M.q('delete from acct', db='bank'); M.q('insert into acct values(1, 1000, 0)', db='bank')
stop = threading.Event(); reads = []
def reader():
    c = conn()
    while not stop.is_set():
        b = q1(c, 'select balance from acct where user_id = 1')[0]; reads.append(('批准' if b >= 500 else '拒绝', b)); time.sleep(0.005)
rt = threading.Thread(target=reader); rt.start()
cw = conn(); N = 30; wall = time.perf_counter()
for i in range(N):
    cw.cursor().execute('update acct set balance = balance - 800 where user_id = 1')   # 第一步:扣款,立即提交
    time.sleep(0.1)                                   # 第二步失败之前的时间窗口
    cw.cursor().execute('update acct set balance = balance + 800 where user_id = 1')              # 补偿
    time.sleep(0.1)
stop.set(); rt.join(); wall = time.perf_counter() - wall
rej = [r for r in reads if r[0] == '拒绝']; dirty_rej = len(rej); seen = sorted({b for _, b in reads})
print(f'  {N} 个 saga 依次跑完,每个 saga 里“已扣款、还没补偿”的窗口 100 ms,共 {wall:.1f} 秒;审批服务一共读了 {len(reads)} 次,读到过的余额值 {seen}')
print(f'  其中读到中间状态 200 并因此“拒绝”贷款的有 {len(rej)} 次({len(rej) / len(reads) * 100:.0f}%)—— 这些拒绝都是错的:每个 saga 最后都被补偿了,账户余额从来没有真的低过 1000')
print('  最终余额:', q1(cw, 'select balance from acct where user_id = 1')[0])

print('== 二:补偿覆盖别人的更新:Saga 扣款 100 后需要补偿,同时另一个事务给账户加了 5 元利息。补偿写法 A:“把余额恢复成扣款之前读到的值”;写法 B:“把扣掉的 100 加回去”')
def trial(variant, rng):
    M.q('update acct set balance = 1000, pending = 0 where user_id = 1', db='bank')
    c1, c2 = conn(), conn(); done = threading.Event()
    def interest():
        time.sleep(rng.random() * 0.04); c2.cursor().execute('update acct set balance = balance + 5 where user_id = 1'); done.set()
    th = threading.Thread(target=interest)
    old = q1(c1, 'select balance from acct where user_id = 1')[0]; c1.cursor().execute('update acct set balance = balance - 100 where user_id = 1')
    th.start(); time.sleep(0.02)                                                      # 第二步在 20 ms 后失败
    if variant == 'A': c1.cursor().execute('update acct set balance = %s where user_id = 1', (old,))
    else: c1.cursor().execute('update acct set balance = balance + 100 where user_id = 1')
    th.join(); r = q1(c1, 'select balance from acct where user_id = 1')[0]; c1.close(); c2.close(); return r
rows = []
for variant, name in (('A', '写法 A:恢复成扣款前读到的值'), ('B', '写法 B:加回扣掉的 100')):
    rng = random.Random(5); res = [trial(variant, rng) for _ in range(200)]
    lost = sum(1 for r in res if r != 1005)
    rows.append((name, 200, lost, f'{lost / 2:.0f}%'))
table(rows, ['补偿写法', '试验次数', '终态不是 1005 的次数(丢了利息)', '比例'])
print('  利息更新落在“扣款之后、补偿之前”的窗口里时,A 把它覆盖掉了(丢失更新);B 是相对增量,先后顺序不影响结果')

print('== 三:中间状态让别人买不到:库存只剩 1 件,saga 先预留这 1 件,支付失败后释放;买家在随机时刻到达')
def stock_trial(rng):
    M.q("delete from inv", db='bank'); M.q("insert into inv values('s', 1, 0)", db='bank')
    c1, c2 = conn(), conn(); res = {}
    arrive = rng.random() * 0.4
    def buyer():
        time.sleep(arrive); res['ok'] = c2.cursor().execute("update inv set qty = qty - 1 where sku = 's' and qty >= 1") == 1
    th = threading.Thread(target=buyer); th.start()
    time.sleep(0.1)                                                                      # saga 在 0.1 s 时预留
    c1.cursor().execute("update inv set qty = qty - 1 where sku = 's' and qty >= 1"); t_res = time.perf_counter()
    time.sleep(0.2)                                                                      # 预留了 0.2 秒,然后支付失败
    c1.cursor().execute("update inv set qty = qty + 1 where sku = 's'")
    th.join(); c1.close(); c2.close(); return arrive, res['ok']
rng = random.Random(8); out = [stock_trial(rng) for _ in range(60)]
in_win = [a for a, ok in out if 0.1 <= a < 0.3]; rej = [a for a, ok in out if not ok]
print(f'  60 次试验,买家到达时刻在 0 到 0.4 秒之间均匀随机;预留窗口是 0.1 到 0.3 秒')
print(f'  买家被拒绝(库存不足)的有 {len(rej)} 次;其中到达时刻落在预留窗口里的 {sum(1 for a in rej if 0.1 <= a < 0.3)} 次;到达时落在窗口里的买家共 {len(in_win)} 个')
outside = [round(a, 4) for a in rej if not (0.1 <= a < 0.3)]
print(f'  被拒绝但到达时刻不在窗口里的:{outside}(都紧贴窗口边界 0.1 / 0.3 秒:sleep 和线程调度的误差让实际窗口比名义上宽几毫秒)' if outside else '  被拒绝的买家全部落在预留窗口里')
print('  窗口里到达的买家被拒了,可是 0.2 秒后 saga 补偿把这 1 件放回去了:这些订单本来是卖得出去的(丢单)。晚于 0.3 秒到的买家买到了')

print('== 四:对策:语义锁(把“正在被 saga 处理”的金额写进 pending 列)。saga 扣款时 balance -= 800、pending += 800;补偿时 balance += 800、pending -= 800;读者要判断总资产时用 balance + pending')
M.q('delete from acct', db='bank'); M.q('insert into acct values(1, 1000, 0)', db='bank')
stop = threading.Event(); reads2 = []; waits = []
def reader2():
    c = conn()
    while not stop.is_set():
        b, p = q1(c, 'select balance, pending from acct where user_id = 1')
        reads2.append(('批准' if b + p >= 500 else '拒绝', b, p)); time.sleep(0.005)
def reader3():                                       # “等待型”读者:看到 pending > 0 就等一会儿再读,直到 saga 收尾
    c = conn(); t0 = None
    while not stop.is_set():
        b, p = q1(c, 'select balance, pending from acct where user_id = 1')
        if p > 0:
            t0 = t0 or time.perf_counter(); time.sleep(0.002); continue
        if t0: waits.append(time.perf_counter() - t0); t0 = None
        time.sleep(0.005)
r2 = threading.Thread(target=reader2); r3 = threading.Thread(target=reader3); r2.start(); r3.start()
cw = conn()
for i in range(N):
    cw.cursor().execute('update acct set balance = balance - 800, pending = pending + 800 where user_id = 1'); time.sleep(0.1)
    cw.cursor().execute('update acct set balance = balance + 800, pending = pending - 800 where user_id = 1'); time.sleep(0.1)
stop.set(); r2.join(); r3.join()
rej2 = [r for r in reads2 if r[0] == '拒绝']; mid = [r for r in reads2 if r[2] > 0]
print(f'  同样的 {N} 个 saga:读 balance + pending 的审批服务读了 {len(reads2)} 次,其中 {len(mid)} 次读到了 saga 进行中的状态(pending > 0),错误拒绝 {len(rej2)} 次')
print(f'  “等待型”读者(看到 pending > 0 就等到 saga 收尾再决定):等待了 {len(waits)} 次,每次平均等 {statistics.mean(waits) * 1000:.0f} ms,最长 {max(waits) * 1000:.0f} ms;等待换来的是它永远只看到已收尾的状态')

print('== 五:三种做法放在一起(同样的场景,数字来自上面的实验)')
table([('无防护:读 balance + 绝对值补偿', f'{dirty_rej}', f'{rows[0][2]}'), ('只改补偿:相对增量', f'{dirty_rej}', f'{rows[1][2]}'), ('相对增量 + 语义锁(pending 列)', f'{len(rej2)}', f'{rows[1][2]}')],
      ['做法', '审批被错误拒绝(第一节的 saga 窗口,次)', '丢失的更新(第二节,200 次里)'])
print('  (第一列的数字是第一节“只读 balance”的错误拒绝次数,第三行是第四节读 balance + pending 的结果;丢失更新数第一行来自写法 A,后两行来自写法 B)')
reset(); shutil.rmtree(TT / 'my_t10', ignore_errors=True)
