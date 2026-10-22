import sys, os, itertools; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from tcc import *
tee('t7'); reset()
M = MySQL('t7_acct').start(); M.q('create database shop')
M.q('create table account(user_id int primary key, balance int, frozen int, spent int, constraint c1 check (balance >= 0 and frozen >= 0))', db='shop')
M.q("create table tcc_log(xid varchar(40) primary key, status varchar(10), amt int, created datetime default current_timestamp)", db='shop')
NAI = AccountSvc(M); GRD = GuardedAccountSvc(M)
BAL, AMT = 1000, 80
def reset_acct(): M.q('delete from account', db='shop'); M.q('delete from tcc_log', db='shop'); M.q('insert into account values(1, %s, 0, 0)', (BAL,), db='shop')
def st(): return tuple(NAI.row(1))
def log_rows(): return [tuple(r) for r in M.q('select xid, status from tcc_log order by xid', db='shop')]
def drop_check(): M.q('alter table account drop check c1', db='shop')
def add_check(): M.q('delete from account', db='shop'); M.q('alter table account add constraint c1 check (balance >= 0 and frozen >= 0)', db='shop')
def tolerant_cancel(user, amt):
    NAI.run('update account set balance = balance + %s, frozen = frozen - %s where user_id = %s and frozen >= %s', (amt, amt, user, amt))
print(f'一个账户服务(MySQL {M.q("select version()")[0][0]}),初始 (balance, frozen, spent) = ({BAL}, 0, 0),每次冻结 / 确认 / 取消金额 {AMT};三种实现:朴素版(第 6 篇的写法)、“宽容 Cancel”版(Cancel 里加一个 frozen >= amt 的条件)、带 tcc_log 防护版')

print('== 一:空回滚:Try 请求超时或丢了,管理器发了 Cancel,Cancel 先到了服务端,而 Try 从来没有执行过')
reset_acct()
print('  朴素版,表上有 CHECK(balance >= 0 and frozen >= 0):')
for k in range(3):
    try: NAI.cancel(1, AMT); print('    Cancel 成功')
    except Exception as e: print(f'    第 {k + 1} 次 Cancel:{type(e).__name__} {e.args[0]} {e.args[1][:50]}')
print('    状态:', st(), '—— CHECK 拦住了,但 Cancel 永远失败,管理器只能一直重试')
drop_check(); reset_acct()
NAI.cancel(1, AMT); print(f'  朴素版,没有 CHECK:Cancel 执行成功,状态 (balance, frozen, spent) = {st()} —— 凭空多出 {AMT} 块钱,frozen 变成负数')
add_check(); reset_acct()
r = GRD.cancel('x1', 1, AMT); print(f'  防护版:Cancel 返回 {r},状态 {st()},tcc_log = {log_rows()} —— 不改业务列,只记一条 CANCELLED')

print('== 二:悬挂:Cancel 先到(空回滚)、Try 后到:Try 是网络里慢了一步的请求,它到的时候管理器已经收尾了')
reset_acct()
tolerant_cancel(1, AMT); print(f'  “宽容 Cancel”版:Cancel(frozen >= {AMT} 才执行)先到,什么都没改,状态 {st()}')
NAI.try_(1, AMT); print(f'  随后迟到的 Try 到达并执行成功,状态 {st()} —— {AMT} 块钱被冻结了,管理器已经走完流程,再也不会有人 Confirm 或 Cancel')
reset_acct()
GRD.cancel('x2', 1, AMT)
try: GRD.try_('x2', 1, AMT)
except Rejected as e: print(f'  防护版:Cancel 先到(记 CANCELLED),迟到的 Try 被拒绝:{e};状态 {st()},tcc_log = {log_rows()}')

print('== 三:重复:Confirm / Cancel 的确认包丢了,管理器按“至少一次”重发,同一个动作被执行了两次')
drop_check(); reset_acct()
NAI.try_(1, AMT); NAI.confirm(1, AMT); print(f'  朴素版:Try → Confirm 一次,状态 {st()}'); NAI.confirm(1, AMT); print(f'  同一个 Confirm 再来一次:状态 {st()} —— spent 记了 {2 * AMT},frozen 变成 {-AMT}')
reset_acct(); NAI.try_(1, AMT); NAI.cancel(1, AMT); print(f'  朴素版:Try → Cancel 一次,状态 {st()}'); NAI.cancel(1, AMT); print(f'  同一个 Cancel 再来一次:状态 {st()} —— balance 比初始多了 {AMT}')
add_check(); reset_acct()
GRD.try_('x3', 1, AMT); GRD.confirm('x3', 1, AMT); a = st(); GRD.confirm('x3', 1, AMT); GRD.confirm('x3', 1, AMT)
print(f'  防护版:Try → Confirm,再重复 Confirm 两次:状态 {a} → {st()},tcc_log = {log_rows()} —— 重复的 Confirm 看到状态已经是 CONFIRMED,什么都不做')
reset_acct(); GRD.try_('x4', 1, AMT); GRD.cancel('x4', 1, AMT); GRD.cancel('x4', 1, AMT); print(f'  防护版:Try → Cancel,再重复 Cancel:状态 {st()},tcc_log = {log_rows()}')

print('== 四:穷举:把一个 xid 的所有“消息到达顺序”都跑一遍(Try 可能丢、可能重复,Cancel / Confirm 可能重复,Cancel 可以抢在 Try 前面,Confirm 总在第一个 Try 之后),看最终账户状态对不对')
def sequences():
    seqs = []
    for nT in (0, 1, 2):
        for nC in (1, 2):
            seqs += [('cancel', s) for s in sorted(set(itertools.permutations('T' * nT + 'C' * nC)))]
    for nT in (1, 2):
        for nK in (1, 2):
            seqs += [('confirm', s) for s in sorted(set(itertools.permutations('T' * nT + 'K' * nK))) if s.index('T') < s.index('K')]
    return seqs
SEQS = sequences()
print(f'  共 {len(SEQS)} 条序列(取消路径 {sum(1 for p, _ in SEQS if p == "cancel")} 条、确认路径 {sum(1 for p, _ in SEQS if p == "confirm")} 条);正确的终态:取消路径 = 初始 ({BAL}, 0, 0),确认路径 = ({BAL - AMT}, 0, {AMT});为了让错误能显现,朴素版和宽容版跑在没有 CHECK 的表上')
drop_check()
def run_seq(impl, path, seq, k):
    reset_acct(); xid = f's{k}'
    for m in seq:
        try:
            if impl == 'guarded': {'T': GRD.try_, 'K': GRD.confirm, 'C': GRD.cancel}[m](xid, 1, AMT)
            else:
                if m == 'T': NAI.try_(1, AMT)
                elif m == 'K': NAI.confirm(1, AMT)
                else: (NAI.cancel if impl == 'naive' else tolerant_cancel)(1, AMT)
        except (Rejected, Insufficient): pass
    want = (BAL, 0, 0) if path == 'cancel' else (BAL - AMT, 0, AMT)
    return st(), want
kinds = {}
for impl, name in (('naive', '朴素版'), ('tolerant', '宽容 Cancel 版'), ('guarded', '防护版')):
    bad = []; cls = {'frozen 变成负数(多退或多确认了)': 0, '预留永久卡住(frozen > 0)': 0, '其它': 0}
    for k, (path, seq) in enumerate(SEQS):
        got, want = run_seq(impl, path, seq, k)
        if got != want:
            bad.append((path, ''.join(seq), got))
            if got[1] < 0: cls['frozen 变成负数(多退或多确认了)'] += 1
            elif got[1] > 0: cls['预留永久卡住(frozen > 0)'] += 1
            else: cls['其它'] += 1
    print(f'  {name}:{len(SEQS)} 条序列里 {len(bad)} 条终态不对  {cls}')
    for path, s, got in bad[:4]: print(f'     例:{"取消路径" if path == "cancel" else "确认路径"} 到达顺序 {" → ".join(s)} => (balance, frozen, spent) = {got}')
    kinds[impl] = len(bad)
print('  (T=Try,K=Confirm,C=Cancel)')
add_check()

print('== 五:并发到达:Try 和 Cancel 同时到服务端(两个线程,用屏障同时放行),重复 300 次,看终态')
def race(impl, n=300):
    bad = 0; neg = [0]; stop = threading.Event()
    def sampler():
        while not stop.is_set():
            r = NAI.row(1)
            if r and r[1] < 0: neg[0] += 1
    sp = threading.Thread(target=sampler); sp.start()
    for i in range(n):
        reset_acct(); xid = f'r{i}'; bar = threading.Barrier(2); order = []
        def do_try():
            bar.wait()
            try:
                (GRD.try_(xid, 1, AMT) if impl == 'guarded' else NAI.try_(1, AMT)); order.append('T')
            except (Rejected, Insufficient): order.append('t-rejected')
        def do_cancel():
            bar.wait()
            if impl == 'guarded': GRD.cancel(xid, 1, AMT)
            elif impl == 'naive': NAI.cancel(1, AMT)
            else: tolerant_cancel(1, AMT)
            order.append('C')
        ts = [threading.Thread(target=do_try), threading.Thread(target=do_cancel)]; [t.start() for t in ts]; [t.join() for t in ts]
        if st() != (BAL, 0, 0): bad += 1
    stop.set(); sp.join()
    return bad, neg[0]
drop_check()
rows = []; NEG = {}
for impl, name in (('naive', '朴素版'), ('tolerant', '宽容 Cancel 版'), ('guarded', '防护版')):
    bad, neg = race(impl); rows.append((name, f'{bad} / 300', neg)); NEG[impl] = neg
add_check()
table(rows, ['实现', '终态不是初始状态的次数', '另一个线程不停读,读到 frozen 为负的次数'])
print('  线程调度决定谁先到。朴素版的 Try 和 Cancel 只是加减,先后顺序不同终态一样,所以终态是对的;' + (f'但 Cancel 先到时中间状态的 frozen 是负数,另一个线程读到了 {NEG["naive"]} 次' if NEG['naive'] else '另一个线程这次没有读到中间状态的负数(只读了一个线程的采样,不代表读不到)') + ';宽容版在 Cancel 先到时卡住预留;防护版两种顺序都回到初始状态')

print('== 六:防护的代价:每个动作多一次 tcc_log 读写;tcc_log 能保留多久、什么时候能删')
N = 400
def bench(f): 
    lat = []
    for i in range(N): t0 = time.perf_counter(); f(i); lat.append(time.perf_counter() - t0)
    return statistics.median(lat)
reset_acct(); M.q('update account set balance = 100000000 where user_id = 1', db='shop')
ctr = [0]
def n_try(i): NAI.try_(1, 1)
def n_conf(i): NAI.confirm(1, 1)
def g_try(i): ctr[0] += 1; GRD.try_(f'b{ctr[0]}', 1, 1)
def g_conf(i): GRD.confirm(f'b{ctr[0] - N + i + 1}', 1, 1)
nt, nc = bench(n_try), bench(n_conf); gt, gc = bench(g_try), bench(g_conf)
us = lambda t: f'{t * 1e6:.0f} µs'
table([('Try', us(nt), us(gt), f'{gt / nt:.1f}x'), ('Confirm', us(nc), us(gc), f'{gc / nc:.1f}x')], ['动作(中位数,各 400 次)', '朴素版', '防护版', '防护版 / 朴素版'])
M.q('truncate table tcc_log', db='shop')
rows = [(f'b{i}', 'CONFIRMED', 80) for i in range(100000)]
c = M.conn('shop', autocommit=False); cur = c.cursor()
for k in range(0, len(rows), 10000): cur.executemany('insert into tcc_log(xid, status, amt) values (%s, %s, %s)', rows[k:k + 10000]); c.commit()
c.close(); M.q('analyze table tcc_log', db='shop')
sz = M.q("select data_length + index_length, table_rows from information_schema.tables where table_schema = 'shop' and table_name = 'tcc_log'")[0]
print(f'  tcc_log 里 10 万行(xid 约 7 个字符)占 {int(sz[0]) / 1024 / 1024:.1f} MiB,平均每行约 {int(sz[0]) / 100000:.0f} 字节(含主键索引);每笔 TCC 事务每个参与的服务一行')
reset_acct()
GRD.cancel('late-1', 1, AMT)
M.q("delete from tcc_log where xid = 'late-1'", db='shop'); print(f'  过早清理:Cancel 记下的 CANCELLED 行被删除后,迟到的 Try 到达 —— ', end='')
try: GRD.try_('late-1', 1, AMT); print(f'Try 执行成功,状态 {st()}(又悬挂了)')
except Rejected as e: print('被拒绝')
print('  所以 tcc_log 的保留期必须比“一条消息在网络里最长能晃多久”还长;删之前要确认不会再有这个 xid 的迟到消息')
reset()
shutil.rmtree(TT / 'my_t7_acct', ignore_errors=True)
