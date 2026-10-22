import sys, os, json, urllib.request, urllib.error; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from tcsvc import post
tee('t22'); reset()
M = MySQL('t22').start()
for db in ('acct_db', 'stock_db'): M.q(f'create database {db}')
M.q('create table account(id int primary key, balance int)', db='acct_db'); M.q('create table stock(id int primary key, qty int)', db='stock_db')
EV = TT / 't22_events.log'; EV.write_text('')
TP, AP, SP = free_port(), free_port(), free_port()
PY = sys.executable; SVC = str(HERE / 'tcsvc.py')
procs = {}
def start(name):
    if name == 'tc': cmd = [PY, SVC, 'tc', M.sock, str(TP), str(EV)]
    else: cmd = [PY, SVC, 'rm', M.sock, str(AP if name == 'acct' else SP), 'acct_db' if name == 'acct' else 'stock_db', str(TP), str(EV)]
    procs[name] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); wait_port(TP if name == 'tc' else (AP if name == 'acct' else SP), 30)
for n in ('tc', 'acct', 'stock'): start(n)
TC_URL, A_URL, S_URL = f'http://127.0.0.1:{TP}', f'http://127.0.0.1:{AP}', f'http://127.0.0.1:{SP}'
print(f'三种角色各是一个独立进程(HTTP/JSON):TC(端口 {TP},状态存在自己的 tc_db 里)、账户 RM(端口 {AP},库 acct_db)、库存 RM(端口 {SP},库 stock_db);TM 就是实验脚本;MySQL {M.q("select version()")[0][0]};实现是我自己写的(tools/articles/tcsvc.py + at.py),不是 Seata')
def reset_data():
    M.q('delete from account', db='acct_db'); M.q('delete from stock', db='stock_db'); M.q('insert into account values (1, 1000), (2, 1000)', db='acct_db'); M.q('insert into stock values (1, 50), (2, 50)', db='stock_db')
    for t in ('global_lock', 'global_tx', 'branch'): M.q(f'delete from {t}', db='tc_db')
    for db in ('acct_db', 'stock_db'): M.q('delete from undo_log', db=db)
def tc_status(xid): return post(f'{TC_URL}/status', {'xid': xid})['status']
def wait_status(xid, want, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if tc_status(xid) in want: return time.time() - t0
        except Exception: pass
        time.sleep(0.02)
    return None
def acct(): return M.q('select balance from account where id = 1', db='acct_db')[0][0]
def stk(): return M.q('select qty from stock where id = 1', db='stock_db')[0][0]
def show_events(since, pat=None, limit=60):
    out = []
    for l in EV.read_text().splitlines():
        t, rest = l.split(' ', 1)
        if float(t) >= since and (pat is None or re.search(pat, rest)): out.append((float(t), rest))
    for t, r in out[:limit]: print(f'    {(t - since) * 1000:7.0f} ms  {r}')
    return out
def tm_tx(decision='commit', timeout_ms=60000, xid=None, sets_a=('balance = balance - %s', [100]), sets_s=('qty = qty - %s', [3])):
    xid = post(f'{TC_URL}/begin', {'timeout_ms': timeout_ms, **({'xid': xid} if xid else {})})['xid']
    post(f'{A_URL}/do', {'xid': xid, 'table': 'account', 'pk': 1, 'sets': sets_a[0], 'params': sets_a[1]}); post(f'{S_URL}/do', {'xid': xid, 'table': 'stock', 'pk': 1, 'sets': sets_s[0], 'params': sets_s[1]})
    if decision: post(f'{TC_URL}/{decision}', {'xid': xid})
    return xid

print('== 一:一次全局事务里三种角色之间的消息(TM begin → 两个 RM 做分支 → TM commit → TC 驱动二阶段),时间戳来自各进程自己写的事件日志')
reset_data(); EV.write_text(''); t0 = time.time(); xid = tm_tx('commit'); dt = wait_status(xid, ('COMMITTED',))
show_events(t0 - 0.0)
print(f'  TM 的 commit 调用返回后 {dt * 1000:.0f} ms 全局事务才真正 COMMITTED(二阶段是 TC 在后台做的);账户 {acct()}、库存 {stk()};undo_log 行数 {M.q("select count(*) from undo_log", db="acct_db")[0][0]} + {M.q("select count(*) from undo_log", db="stock_db")[0][0]};tc_db:global_tx {M.q("select count(*) from global_tx", db="tc_db")[0][0]} 行、branch {M.q("select count(*) from branch", db="tc_db")[0][0]} 行、global_lock {M.q("select count(*) from global_lock", db="tc_db")[0][0]} 行')

print('== 二:TM 崩溃(开了全局事务、做完两个分支就再也不来了,没有 commit 也没有 rollback):TC 的超时扫描器接管,超时(这里设 1.5 秒)后把它回滚')
reset_data(); EV.write_text(''); t0 = time.time(); xid = tm_tx(None, timeout_ms=1500)
print(f'  两个分支做完后:账户 {acct()}、库存 {stk()},全局事务状态 {tc_status(xid)}')
dt = wait_status(xid, ('ROLLED_BACK',)); show_events(t0, r'超时|rollback|ROLL|分支')
print(f'  开始后 {(time.time() - t0) * 1000:.0f} ms 左右 TC 把它回滚完(等待了 {dt * 1000:.0f} ms 才变成 ROLLED_BACK);账户 {acct()}、库存 {stk()},global_lock 行数 {M.q("select count(*) from global_lock", db="tc_db")[0][0]}')

print('== 三:TC 在二阶段中途崩溃(kill -9),重启后从 tc_db 里恢复继续做。为了让崩溃发生在二阶段做完之前,先让两个 RM 的 branch_commit / branch_rollback 暂时失败')
def tc_crash(decision):
    reset_data(); EV.write_text(''); path = 'branch_commit' if decision == 'commit' else 'branch_rollback'
    for u in (A_URL, S_URL): post(f'{u}/fault', {'path': path, 'n': 10 ** 6})
    t0 = time.time(); xid = tm_tx(decision); wait_status(xid, ('COMMITTING', 'ROLLING_BACK')); time.sleep(0.3)
    st = tc_status(xid); os.killpg(procs['tc'].pid, signal.SIGKILL); procs['tc'].wait(); tk = time.time()
    print(f'  [{decision}] TC 被 kill -9 时全局事务状态是 {st}(二阶段没做完);此刻 undo_log 行数 {M.q("select count(*) from undo_log", db="acct_db")[0][0]} + {M.q("select count(*) from undo_log", db="stock_db")[0][0]},global_lock 行数 {M.q("select count(*) from global_lock", db="tc_db")[0][0]},账户 {acct()}、库存 {stk()}')
    for u in (A_URL, S_URL): post(f'{u}/fault', {'path': path, 'n': 0})
    start('tc'); dt = wait_status(xid, ('COMMITTED', 'ROLLED_BACK')); 
    out = show_events(tk, r'启动恢复|成功|全局事务')
    print(f'  [{decision}] TC 重启后 {dt * 1000:.0f} ms 把二阶段做完:状态 {tc_status(xid)},账户 {acct()}、库存 {stk()},undo_log 行数 {M.q("select count(*) from undo_log", db="acct_db")[0][0]} + {M.q("select count(*) from undo_log", db="stock_db")[0][0]},global_lock 行数 {M.q("select count(*) from global_lock", db="tc_db")[0][0]}')
tc_crash('commit'); tc_crash('rollback')

print('== 四:RM 在二阶段暂时不可用:TC 带退避地重试(100 ms 起,每次翻倍,上限 1.6 s)。先让账户 RM 的 branch_rollback 失败 3 次;再看一直失败时,全局锁一直被占着,别的全局事务会被挡住')
reset_data(); EV.write_text(''); post(f'{A_URL}/fault', {'path': 'branch_rollback', 'n': 3}); t0 = time.time(); xid = tm_tx('rollback'); wait_status(xid, ('ROLLED_BACK',)); show_events(t0, r'branch_rollback|全局事务')
print(f'  账户 {acct()}、库存 {stk()};最终状态 {tc_status(xid)}')
reset_data(); EV.write_text(''); post(f'{A_URL}/fault', {'path': 'branch_rollback', 'n': 10 ** 6}); t0 = time.time(); xid = tm_tx('rollback'); time.sleep(4.0)
n_try = len([l for l in EV.read_text().splitlines() if '失败(第' in l])
print(f'  账户 RM 一直失败 4 秒:全局事务状态 {tc_status(xid)},TC 重试了 {n_try} 次(间隔 100 → 200 → 400 → 800 → 1600 ms 封顶),账户 {acct()}(分支已经提交的 -100 还没恢复),global_lock 仍有 {M.q("select count(*) from global_lock", db="tc_db")[0][0]} 行')
t1 = time.time()
try: post(f'{A_URL}/do', {'xid': 'other', 'table': 'account', 'pk': 1, 'sets': 'balance = balance - %s', 'params': [1], 'lock_timeout': 1.0}, timeout=10); print('  另一个全局事务想改同一个账户:成功(不该发生)')
except urllib.error.HTTPError as e: print(f'  另一个全局事务想改同一个账户:等了 {(time.time() - t1) * 1000:.0f} ms 后失败({json.loads(e.read()).get("error", "")[:60]})—— 没做完二阶段的事务一直占着全局锁')
post(f'{A_URL}/fault', {'path': 'branch_rollback', 'n': 0}); wait_status(xid, ('ROLLED_BACK',), 10); print(f'  把故障去掉后,TC 的下一次重试成功:最终状态 {tc_status(xid)},账户 {acct()}')

print('== 五:每个全局事务产生多少次跨角色调用,各角色库里留下什么;以及这个原型在 1、4、8 个 TM 线程下的耗时(原型是 Python 的 http.server + urllib,每次调用新建连接,绝对数字只说明这个原型,不代表任何成熟的 TC)')
reset_data(); EV.write_text('')
def bench(threads, per):
    lat = []; done = []; lk = threading.Lock(); M.q('delete from account', db='acct_db'); M.q('delete from stock', db='stock_db')
    M.q('insert into account values %s' % ','.join(f'({i}, 1000000)' for i in range(1, 17)), db='acct_db'); M.q('insert into stock values %s' % ','.join(f'({i}, 1000000)' for i in range(1, 17)), db='stock_db')
    def w(k):
        loc = []; ids = []
        for i in range(per):
            t0 = time.perf_counter(); xid = post(f'{TC_URL}/begin', {})['xid']
            post(f'{A_URL}/do', {'xid': xid, 'table': 'account', 'pk': k + 1, 'sets': 'balance = balance - %s', 'params': [1]}); post(f'{S_URL}/do', {'xid': xid, 'table': 'stock', 'pk': k + 1, 'sets': 'qty = qty - %s', 'params': [1]})
            post(f'{TC_URL}/commit', {'xid': xid}); loc.append(time.perf_counter() - t0); ids.append(xid)
        with lk: lat.extend(loc); done.extend(ids)
    t0 = time.perf_counter(); ts = [threading.Thread(target=w, args=(k,)) for k in range(threads)]; [t.start() for t in ts]; [t.join() for t in ts]; dt = time.perf_counter() - t0
    t1 = time.perf_counter()
    while M.q("select count(*) from global_tx where status not in ('COMMITTED')", db='tc_db')[0][0] > 0 and time.perf_counter() - t1 < 60: time.sleep(0.02)
    return statistics.median(lat), threads * per / dt, time.perf_counter() - t0
rows = []
for th, per in ((1, 100), (4, 50), (8, 25)):
    reset_data(); med, tps, tot = bench(th, per); rows.append((th, th * per, f'{med * 1000:.1f} ms', f'{tps:.0f}', f'{tot:.2f} s'))
table(rows, ['TM 线程数', '全局事务数', 'TM 看到的单个事务耗时(中位数,begin 到 commit 返回)', '每秒完成的全局事务(到 commit 返回)', '全部二阶段做完的总用时'])
reset_data()
for u in (TC_URL, A_URL, S_URL): post(f'{u}/stats', {'reset': 1})
med, tps, tot = bench(1, 50)
cnt = {}
for name, u in (('TC', TC_URL), ('账户 RM', A_URL), ('库存 RM', S_URL)):
    for path, n in post(f'{u}/stats', {}).items(): cnt[(name, path)] = n
tot_calls = sum(cnt.values())
print('  单线程跑 50 个全局事务(每个 2 个分支)时,各进程收到的 HTTP 调用次数(平均每个全局事务):' + ',  '.join(f'{name}{path} {n / 50:.1f}' for (name, path), n in sorted(cnt.items())))
print(f'  合计每个全局事务 {tot_calls / 50:.1f} 次 HTTP 调用(本地事务是 0 次);其中 TM 直接发起的是 begin、两次业务调用、commit 共 4 次,其余是 RM 与 TC 之间互相调用')
print(f'  做完之后各角色库里留下的行数:TC 的 global_tx {M.q("select count(*) from global_tx", db="tc_db")[0][0]} 行(状态 COMMITTED 的历史记录)、branch {M.q("select count(*) from branch", db="tc_db")[0][0]} 行,global_lock {M.q("select count(*) from global_lock", db="tc_db")[0][0]} 行(锁已释放);RM 的 undo_log {M.q("select count(*) from undo_log", db="acct_db")[0][0]} + {M.q("select count(*) from undo_log", db="stock_db")[0][0]} 行(二阶段清理掉了);TM 不存任何状态')
for p in procs.values():
    try: os.killpg(p.pid, signal.SIGKILL)
    except Exception: pass
reset(); EV.unlink(missing_ok=True); shutil.rmtree(TT / 'my_t22', ignore_errors=True)
