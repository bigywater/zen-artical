import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.errors import OperationFailure, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
tee('m47'); reset()
rs = ReplSet('m47', 1).start(); rs.wait_primary()
c = rs.client(); db = c.test
db.acct.insert_many([{'_id': 'A', 'bal': 100}, {'_id': 'B', 'bal': 100}])
def bal(x, s=None): return x.acct.find_one({'_id': 'A'}, session=s)['bal']
print('== 一:快照隔离:事务开始后读到的数据是“事务开始那一刻”的快照——别人之后提交的修改看不到,直到事务结束')
s1 = c.start_session(); s1.start_transaction(read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))
print(f'  事务 T1 开始后读 A.bal = {bal(db, s1)}')
db.acct.update_one({'_id': 'A'}, {'$set': {'bal': 150}})
print(f'  事务外把 A.bal 改成 150 并提交;事务外读 = {bal(db)};T1 里再读 = {bal(db, s1)}(仍是快照里的值)')
s1.commit_transaction(); print(f'  T1 提交后,在新的读里 A.bal = {bal(db)}')
print('== 二:写冲突:T1 修改了 A 还没提交,另一个事务 T2 也要改 A,会立刻报 WriteConflict(code 112),带 TransientTransactionError 标签')
db.acct.update_one({'_id': 'A'}, {'$set': {'bal': 100}})
s1 = c.start_session(); s1.start_transaction(); db.acct.update_one({'_id': 'A'}, {'$inc': {'bal': 1}}, session=s1)
s2 = c.start_session(); s2.start_transaction(); t0 = time.perf_counter()
try: db.acct.update_one({'_id': 'A'}, {'$inc': {'bal': 10}}, session=s2)
except OperationFailure as e: print(f'  T2 的更新:{(time.perf_counter() - t0) * 1000:.0f} ms 后报错 code={e.code}({e.details.get("codeName")}),errorLabels={sorted(e.details.get("errorLabels", []))}')
s2.abort_transaction() if s2.in_transaction else None
print('== 三:事务外的写入遇到事务里未提交的修改:不报错,而是等待,直到事务结束')
res = {}
def outside():
    t0 = time.perf_counter(); db.acct.update_one({'_id': 'A'}, {'$inc': {'bal': 100}}); res['ms'] = (time.perf_counter() - t0) * 1000
th = threading.Thread(target=outside); th.start(); time.sleep(1.5)
print(f'  T1 仍未提交 1.5 秒后,事务外的 update 完成了吗: {not th.is_alive()}')
s1.commit_transaction(); th.join()
print(f'  T1 提交后事务外的 update 才完成:总共等了 {res["ms"]:.0f} ms;最终 A.bal = {bal(db)}(100 + 1 + 100)')
print('== 四:with_transaction 回调写法:冲突时自动重试整个回调。16 个线程各给同一个账户加 1,共 100 轮')
db.acct.update_one({'_id': 'A'}, {'$set': {'bal': 0}}); retries = []; lock = threading.Lock()
def work(w):
    cc = rs.client(); d = cc.test; cnt = [0]
    for _ in range(100):
        def cb(session):
            cnt[0] += 1; d.acct.update_one({'_id': 'A'}, {'$inc': {'bal': 1}}, session=session)
        with cc.start_session() as s: s.with_transaction(cb)
    with lock: retries.append(cnt[0] - 100)
t0 = time.perf_counter(); ths = [threading.Thread(target=work, args=(w,)) for w in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
print(f'  最终 A.bal = {bal(db)}(应为 1600);耗时 {dt:.2f} s;因 WriteConflict 额外重试了 {sum(retries)} 次(平均每次提交 {sum(retries) / 1600:.2f} 次)')
print('== 五:快照隔离的“写偏斜”:两个医生值班规则“至少要有一人在岗”,两个事务各自检查后让不同的医生下班,都提交成功')
db.doc.drop(); db.doc.insert_many([{'_id': 'alice', 'on': True}, {'_id': 'bob', 'on': True}])
ready = threading.Barrier(2); out = []
def leave(name):
    cc = rs.client(); d = cc.test
    def cb(session):
        n_on = d.doc.count_documents({'on': True}, session=session)
        ready.wait()
        if n_on >= 2: d.doc.update_one({'_id': name}, {'$set': {'on': False}}, session=session); out.append((name, '下班', n_on))
    with cc.start_session() as s: s.with_transaction(cb)
ths = [threading.Thread(target=leave, args=(nm,)) for nm in ('alice', 'bob')]; [t.start() for t in ths]; [t.join() for t in ths]
print(f'  两个事务各自看到的在岗人数 {[o[2] for o in out]},都让自己下班了;事务结束后在岗人数 = {db.doc.count_documents({"on": True})}(规则被破坏)')
print('== 六:事务里能做和不能做的:count 命令不行(要用 countDocuments),读写文档可以')
s = c.start_session(); s.start_transaction()
try: db.command('count', 'acct', session=s); print('  count 命令:成功?')
except OperationFailure as e: print(f'  count 命令:code={e.code} {str(e)[:100]}')
try: s.abort_transaction()
except Exception: pass
s = c.start_session(); s.start_transaction()
print(f'  新开一个事务:countDocuments = {db.acct.count_documents({}, session=s)},find_one 的结果 {db.acct.find_one({"_id": "B"}, session=s)}')
s.abort_transaction()
rs.stop()
