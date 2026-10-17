import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.errors import OperationFailure
tee('m48'); reset()
rs = ReplSet('m48', 1).start(); rs.wait_primary()
c = rs.client(); db = c.test; adm = c.admin
db.t.insert_many([{'_id': i, 'v': 0} for i in range(5)])
print('== 一:事务的生命周期上限由参数 transactionLifetimeLimitSeconds 决定')
msh(rs.primary(), 'var r = db.adminCommand({getParameter: 1, transactionLifetimeLimitSeconds: 1, maxTransactionLockRequestTimeoutMillis: 1}); ({transactionLifetimeLimitSeconds: r.transactionLifetimeLimitSeconds, maxTransactionLockRequestTimeoutMillis: r.maxTransactionLockRequestTimeoutMillis})', note='默认值')
print('== 二:currentOp 里正在运行的事务:timeOpenMicros、expiryTime')
s = c.start_session(); s.start_transaction(); db.t.update_one({'_id': 0}, {'$inc': {'v': 1}}, session=s)
ops = list(adm.aggregate([{'$currentOp': {'allUsers': True, 'idleSessions': True}}, {'$match': {'transaction': {'$exists': True}}}]))
tx = ops[0]['transaction'] if ops else {}
print(f'  currentOp 里事务的字段: {sorted(tx.keys())}')
print(f'  timeOpenMicros = {tx.get("timeOpenMicros")};timeActiveMicros = {tx.get("timeActiveMicros")};expiryTime - startWallClockTime = {(__import__("datetime").datetime.fromisoformat(tx["expiryTime"].replace("Z", "+00:00")) - __import__("datetime").datetime.fromisoformat(tx["startWallClockTime"].replace("Z", "+00:00"))).total_seconds()} 秒;parameters = {tx.get("parameters")}')
s.abort_transaction()
print('== 三:把上限调成 5 秒来观察:事务里改了文档 A 之后不再操作,过多久会被服务端中止?另一个线程对 A 的普通写入被阻塞多久?')
msh(rs.primary(), 'var r = db.adminCommand({setParameter: 1, transactionLifetimeLimitSeconds: 5}); ({was: r.was, ok: r.ok})')
s = c.start_session(); s.start_transaction(); db.t.update_one({'_id': 1}, {'$inc': {'v': 1}}, session=s); t_open = time.perf_counter()
res = {}
def outside():
    t0 = time.perf_counter(); db.t.update_one({'_id': 1}, {'$set': {'w': 1}}); res['wait'] = (time.perf_counter() - t0) * 1000
th = threading.Thread(target=outside); th.start()
th.join()
print(f'  事务外对 A 的 update 等了 {res["wait"]:.0f} ms 才完成(上限 5 s;期间事务里一直没有再操作)')
t_before = time.perf_counter() - t_open
try: db.t.update_one({'_id': 2}, {'$inc': {'v': 1}}, session=s); print('  事务里继续操作?')
except OperationFailure as e: print(f'  事务开始 {t_before:.1f} s 后在事务里继续操作:code={e.code}({e.details.get("codeName")}),errorLabels={sorted(e.details.get("errorLabels", []))};message: {str(e)[:120]}')
try: s.commit_transaction(); print('  commit 成功?')
except OperationFailure as e: print(f'  commit:code={e.code}({e.details.get("codeName")}),errorLabels={sorted(e.details.get("errorLabels", []))}')
print(f'  文档 A(_id 1)的 v = {db.t.find_one({"_id": 1})["v"]}(事务里的 $inc 被回滚了),w = {db.t.find_one({"_id": 1}).get("w")}(事务外的写入生效)')
print('== 四:没有被服务端中止的长事务:5 秒内持续在事务里操作,事务的“生命周期”仍然从开始时算起,到点就中止')
s = c.start_session(); s.start_transaction(); t0 = time.perf_counter(); n_ok = 0
try:
    while True:
        db.t.update_one({'_id': 3}, {'$inc': {'v': 1}}, session=s); n_ok += 1; time.sleep(0.5)
except OperationFailure as e: print(f'  每 0.5 秒操作一次:成功了 {n_ok} 次后在 {time.perf_counter() - t0:.1f} s 时失败 code={e.code}({e.details.get("codeName")})——即使一直在用,到上限也会中止')
print('== 五:服务端日志里关于事务过期的记录')
lg = rs.primary().logs(r'(?i)transaction.*(expired|abort)|abort.*transaction')
msgs = []
for j in lg:
    m = j.get('msg', '')
    if m not in msgs: msgs.append(m)
print(f'  含 transaction + expired/abort 的日志行 {len(lg)} 条;不同的 msg: {msgs[:5]}')
msh(rs.primary(), 'var r = db.adminCommand({setParameter: 1, transactionLifetimeLimitSeconds: 60}); ({was: r.was, ok: r.ok})')
print('== 六:默认的 60 秒:两个事务同时开始并各改一个文档然后什么也不做——一个在 70 秒时提交,另一个等到被服务端中止为止')
sa = c.start_session(); sa.start_transaction(); db.t.update_one({'_id': 4}, {'$inc': {'v': 1}}, session=sa)
sb = c.start_session(); sb.start_transaction(); db.t.update_one({'_id': 3}, {'$inc': {'v': 100}}, session=sb); t0 = time.perf_counter()
def txn_alive(): return any(True for _ in adm.aggregate([{'$currentOp': {'allUsers': True, 'idleSessions': True}}, {'$match': {'transaction': {'$exists': True}}}]))
gone = None; committed_a = None
while time.perf_counter() - t0 < 220:
    el = time.perf_counter() - t0
    if committed_a is None and el >= 70:
        try: sa.commit_transaction(); committed_a = f'{el:.0f} s 时 commit 成功'
        except OperationFailure as e: committed_a = f'{el:.0f} s 时 commit 失败 code={e.code}({e.details.get("codeName")})'
    if committed_a is not None and not txn_alive(): gone = time.perf_counter() - t0; break
    time.sleep(1)
print(f'  事务 A:{committed_a};文档 _id 4 的 v = {db.t.find_one({"_id": 4})["v"]}')
print(f'  事务 B(一直没动):在 {gone:.0f} s 时从 currentOp 里消失(被服务端中止),上限是 60 s')
try: sb.commit_transaction(); print('  B commit 成功?')
except OperationFailure as e: print(f'  B 的 commit:code={e.code}({e.details.get("codeName")}),errorLabels={sorted(e.details.get("errorLabels", []))};文档 _id 3 的 v = {db.t.find_one({"_id": 3})["v"]}(没有被修改)')
lg = rs.primary().logs(r'transactionLifetimeLimitSeconds')
print(f'  日志里 "Aborting transaction because it has been running for longer than transactionLifetimeLimitSeconds" 的记录数 {len(lg)}')
rs.stop()
