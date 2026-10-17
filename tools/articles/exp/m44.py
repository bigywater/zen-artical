import sys, os, threading, datetime as dt; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import ReturnDocument
tee('m44'); reset()
n = Node('m44'); n.start(); c = n.client(); db = c.test
W, JOBS = 8, 2000
def load(coll, jobs=JOBS, prio=False):
    db[coll].drop(); db[coll].insert_many([{'_id': i, 'status': 'pending', 'prio': (i * 7) % 5 if prio else 0, 'tries': 0} for i in range(jobs)])
def workers(fn, coll):
    res = [[] for _ in range(W)]; ths = [threading.Thread(target=fn, args=(w, res[w], coll)) for w in range(W)]
    t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; return res, time.perf_counter() - t0
def claim_atomic(w, out, coll):
    cc = n.client().test[coll]
    while True:
        d = cc.find_one_and_update({'status': 'pending'}, {'$set': {'status': 'running', 'worker': w}, '$inc': {'tries': 1}}, sort=[('prio', -1), ('_id', 1)], return_document=ReturnDocument.AFTER)
        if not d: return
        out.append(d['_id'])
print(f'== 一:原子领取:{W} 个 worker 各自循环 findOneAndUpdate({{status: "pending"}} → running),直到队列空;{JOBS:,} 个任务')
load('q1'); db.q1.create_index([('status', 1), ('prio', -1), ('_id', 1)])
res, dt1 = workers(claim_atomic, 'q1')
allj = [j for r in res for j in r]
print(f'  耗时 {dt1:.2f} s({JOBS / dt1:,.0f} 个/秒);领取总数 {len(allj):,},不同的任务 {len(set(allj)):,}(应为 {JOBS:,},没有重复领取);各 worker 领到: {[len(r) for r in res]}')
print(f'  数据库里 tries>1 的任务数 {db.q1.count_documents({"tries": {"$gt": 1}})};status 分布 {list(db.q1.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]))}')
print('== 二:有缺陷的做法:先 find 一个 pending,再 update 它为 running(两步,中间没有保护)')
def claim_naive(w, out, coll):
    cc = n.client().test[coll]
    while True:
        d = cc.find_one({'status': 'pending'}, sort=[('_id', 1)])
        if not d: return
        cc.update_one({'_id': d['_id']}, {'$set': {'status': 'running', 'worker': w}, '$inc': {'tries': 1}})
        out.append(d['_id'])
load('q2'); db.q2.create_index([('status', 1), ('_id', 1)])
res, dt2 = workers(claim_naive, 'q2')
allj = [j for r in res for j in r]
print(f'  耗时 {dt2:.2f} s;领取总数 {len(allj):,},不同的任务 {len(set(allj)):,}(应为 {JOBS:,});被多个 worker 同时领到(重复处理)的任务有 {len(allj) - len(set(allj)):,} 个')
print('== 三:折中:update 时带条件 status: "pending",检查 modified_count,没抢到就重来')
def claim_cond(w, out, coll):
    cc = n.client().test[coll]; fails = 0
    while True:
        d = cc.find_one({'status': 'pending'}, sort=[('_id', 1)])
        if not d: out.append(('fails', fails)); return
        r = cc.update_one({'_id': d['_id'], 'status': 'pending'}, {'$set': {'status': 'running', 'worker': w}, '$inc': {'tries': 1}})
        if r.modified_count: out.append(d['_id'])
        else: fails += 1
load('q3'); db.q3.create_index([('status', 1), ('_id', 1)])
res, dt3 = workers(claim_cond, 'q3')
ids = [j for r in res for j in r if not isinstance(j, tuple)]; fails = sum(j[1] for r in res for j in r if isinstance(j, tuple))
print(f'  耗时 {dt3:.2f} s;领取 {len(ids):,},不同 {len(set(ids)):,}(没有重复);抢占失败(白做的 find + update)共 {fails:,} 次')
print('== 四:按优先级领取:sort 指定 prio 降序;验证领取顺序确实是 prio 从高到低(单 worker)')
load('q4', 300, prio=True); db.q4.create_index([('status', 1), ('prio', -1), ('_id', 1)])
seq = []
cc = db.q4
while True:
    d = cc.find_one_and_update({'status': 'pending'}, {'$set': {'status': 'running'}}, sort=[('prio', -1), ('_id', 1)])
    if not d: break
    seq.append(d['prio'])
print(f'  300 个任务的领取顺序里 prio 序列是否单调不增: {all(a >= b for a, b in zip(seq, seq[1:]))};前 10 个 prio {seq[:10]},第 100 / 200 / 300 个 {seq[99]}, {seq[199]}, {seq[299]}')
print('== 五:队列索引:没有 (status, prio, _id) 索引时,每次领取都要扫描——队列越大越慢。pending 任务 5 万个,每次 findOneAndUpdate 的耗时(有索引 100 次、无索引 20 次的中位数)')
for name, idx in [('有索引', True), ('无索引', False)]:
    load('q5' + name, 50000, prio=True)
    if idx: db['q5' + name].create_index([('status', 1), ('prio', -1), ('_id', 1)])
    ts = []
    for _ in range(100 if idx else 20):
        t0 = time.perf_counter(); db['q5' + name].find_one_and_update({'status': 'pending'}, {'$set': {'status': 'running'}}, sort=[('prio', -1), ('_id', 1)]); ts.append((time.perf_counter() - t0) * 1000)
    print(f'  {name}:{fm(median(ts))}(中位数)')
print('== 六:worker 领到任务后崩溃:任务永远停在 running。给任务加一个租约时间 lease_until,清扫线程把过期的 running 重新放回 pending')
db.q6.drop(); db.q6.create_index([('status', 1), ('lease', 1)])
now = lambda: dt.datetime.now(dt.timezone.utc)
db.q6.insert_many([{'_id': i, 'status': 'pending', 'tries': 0} for i in range(10)])
for i in range(4):
    db.q6.find_one_and_update({'status': 'pending'}, {'$set': {'status': 'running', 'lease': now() + dt.timedelta(seconds=1)}, '$inc': {'tries': 1}})   # 4 个 worker 领了任务;假设它们崩溃了,没人完成
print(f'  4 个任务被领走(租约 1 秒)后 worker 崩溃: {list(db.q6.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]))}')
time.sleep(1.2)
r = db.q6.update_many({'status': 'running', 'lease': {'$lt': now()}}, {'$set': {'status': 'pending'}, '$unset': {'lease': ''}})
print(f'  1.2 秒后清扫:把 {r.modified_count} 个过期租约的任务放回 pending;{list(db.q6.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]))};这 4 个任务的 tries = {[d["tries"] for d in db.q6.find({"tries": {"$gt": 0}})]}(领取过 1 次)')
n.stop()
