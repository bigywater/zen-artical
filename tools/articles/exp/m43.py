import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.errors import DuplicateKeyError
tee('m43'); reset()
n = Node('m43'); n.start(); c = n.client(); db = c.test
T, ROUNDS = 16, 300
def race(coll, mk_filter, mk_update, label, upsert=True, keys=ROUNDS):
    errs = []; lock = threading.Lock(); barrier = threading.Barrier(T)
    def worker(w):
        cc = n.client().test[coll]; local = []
        for k in range(keys):
            barrier.wait()
            try: cc.update_one(mk_filter(k), mk_update(w, k), upsert=upsert)
            except Exception as e: local.append(type(e).__name__ + ': ' + str(e)[:70])
        with lock: errs.extend(local)
    ths = [threading.Thread(target=worker, args=(w,)) for w in range(T)]; [t.start() for t in ths]; [t.join() for t in ths]
    return errs
print(f'== 一:没有唯一索引:{T} 个线程同时对同一个条件 {{k: i}} 做 upsert,共 {ROUNDS} 轮(每轮所有线程用同一个 k)——会不会重复插入?')
errs = race('nou', lambda k: {'k': k}, lambda w, k: {'$set': {'by': w}}, 'no-unique')
dup = list(db.nou.aggregate([{'$group': {'_id': '$k', 'n': {'$sum': 1}}}, {'$match': {'n': {'$gt': 1}}}]))
print(f'  文档总数 {db.nou.count_documents({})}(应为 {ROUNDS} 个不同的 k);有重复的 k 有 {len(dup)} 个,最多重复 {max([d["n"] for d in dup], default=1)} 份;错误数 {len(errs)}')
print(f'== 二:在 k 上建唯一索引再来一遍:重复被索引挡住——客户端看到多少次 E11000?')
db.uniq.create_index('k', unique=True)
errs = race('uniq', lambda k: {'k': k}, lambda w, k: {'$set': {'by': w}}, 'unique')
print(f'  文档总数 {db.uniq.count_documents({})}(应为 {ROUNDS});客户端收到的错误数 {len(errs)}' + (f',例如 {errs[0]}' if errs else ''))
print('  (服务端对“条件里是唯一键的等值”的 upsert 在遇到 E11000 时会自动重试一次,所以一般看不到)')
print('== 三:自动重试不管用的情形:upsert 的条件字段不是唯一索引的键。条件是 {a: ?},唯一索引在 b 上,$setOnInsert 给 b 一个固定值')
db.trick.create_index('b', unique=True)
errs = race('trick', lambda k: {'a': k + 10 * 0}, lambda w, k: {'$setOnInsert': {'b': 'same'}, '$set': {'by': w}}, 'trick', keys=3)
print(f'  3 轮,每轮 {T} 个线程;文档数 {db.trick.count_documents({})}(唯一的 b="same");错误数 {len(errs)},例如 {errs[:2]}')
print('== 四:应用层的做法:捕获 DuplicateKeyError,重试一次(这时文档已存在,变成普通更新)')
db.fix.create_index('k', unique=True)
cnt = {'dupkey': 0, 'retried_ok': 0}; lock = threading.Lock()
def safe_upsert(coll, k, w):
    try: coll.update_one({'k': k, 'tag': 'x'}, {'$set': {'by': w}}, upsert=True)
    except DuplicateKeyError:
        with lock: cnt['dupkey'] += 1
        coll.update_one({'k': k, 'tag': 'x'}, {'$set': {'by': w}}, upsert=False)   # 文档已被别人插入,再更新
        with lock: cnt['retried_ok'] += 1
barrier = threading.Barrier(T)
def worker4(w):
    cc = n.client().test.fix
    for k in range(60):
        barrier.wait(); safe_upsert(cc, k, w)
ths = [threading.Thread(target=worker4, args=(w,)) for w in range(T)]; [t.start() for t in ths]; [t.join() for t in ths]
print(f'  条件 {{k, tag: "x"}}(多了一个非唯一字段 tag,服务端不再自动重试):捕获到 DuplicateKeyError {cnt["dupkey"]} 次,重试更新成功 {cnt["retried_ok"]} 次;最终文档数 {db.fix.count_documents({})}(60 个 k)')
print('== 五:findOneAndUpdate upsert 做“取号器”:每个线程都要拿到不同的编号')
db.ctr.insert_one({'_id': 'seq', 'n': 0})
got = []; lock2 = threading.Lock()
def grab():
    cc = n.client().test.ctr
    for _ in range(100):
        d = cc.find_one_and_update({'_id': 'seq'}, {'$inc': {'n': 1}}, return_document=True)
        with lock2: got.append(d['n'])
ths = [threading.Thread(target=grab) for _ in range(T)]; [t.start() for t in ths]; [t.join() for t in ths]
print(f'  {T} 个线程各取 100 次:共 {len(got)} 个编号,不同的 {len(set(got))} 个,最小 {min(got)},最大 {max(got)}(无重复无缺口)')
print('== 六:$setOnInsert 只在插入时生效;upsert 的 matchedCount / upsertedId 告诉你发生了什么')
msh(n, 'db.s.updateOne({k: 1}, {$set: {v: 1}, $setOnInsert: {created: "first"}}, {upsert: true})')
msh(n, 'db.s.updateOne({k: 1}, {$set: {v: 2}, $setOnInsert: {created: "second"}}, {upsert: true}); db.s.findOne({k: 1}, {_id: 0})', label='第二次 upsert(文档已存在,$setOnInsert 不生效)')
n.stop()
