import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m35'); reset()
n = Node('m35', cache=0.5); n.start(); c = n.client(); db = c.test
N = 8000000; r = random.Random(35)
fill(db.t, N, lambda i: {'_id': i, 'k': r.randrange(10 ** 9), 'u': i, 'z': r.randrange(10 ** 9), 'pad': 'x' * 40}, batch=40000)
print(f'== 一:{N:,} 个文档,在 k(随机整数)上建索引,同时有一个线程不停地读和写同一个集合')
def lat_stats(x):
    x = sorted(x); return f'{len(x):>6,} 次,中位数 {median(x):.2f} ms,p99 {x[int(len(x) * .99)]:.2f} ms,最大 {x[-1]:.1f} ms'
class Load:
    def __init__(self, nm): self.nm = nm; self.r_ = []; self.w_ = []; self.err = []; self.stop = threading.Event(); self.mark = []
    def run(self):
        cc = n.client(); d = cc.test.get(self.nm) if False else cc.test[self.nm]; i = 10_000_000; rg = random.Random(1)
        while not self.stop.is_set():
            t1 = time.perf_counter()
            try: d.find_one({'_id': rg.randrange(N)})
            except Exception as e: self.err.append(str(e)[:60])
            t2 = time.perf_counter(); self.r_.append((t1, (t2 - t1) * 1000))
            try: d.insert_one({'_id': i, 'k': rg.randrange(10 ** 9), 'u': i, 'z': rg.randrange(10 ** 9), 'pad': 'w'}); i += 1
            except Exception as e: self.err.append(str(e)[:60])
            t3 = time.perf_counter(); self.w_.append((t2, (t3 - t2) * 1000))
ld = Load('t'); th = threading.Thread(target=ld.run); th.start(); time.sleep(2)
t_start = time.perf_counter()
prog = []; stopp = threading.Event()
def poll():
    cc = n.client()
    while not stopp.is_set():
        try:
            ops = cc.admin.command('currentOp', {'$all': True, 'command.createIndexes': {'$exists': True}})['inprog']
            for o in ops:
                if o.get('msg'): prog.append((round(time.perf_counter() - t_start, 2), o.get('msg'), o.get('progress')))
        except Exception: pass
        time.sleep(0.5)
pt = threading.Thread(target=poll); pt.start()
db.t.create_index('k'); t_end = time.perf_counter(); stopp.set(); pt.join()
time.sleep(2); ld.stop.set(); th.join()
build = t_end - t_start
print(f'  建索引耗时 {build:.1f} s')
before = [x for t, x in ld.r_ if t < t_start]; during = [x for t, x in ld.r_ if t_start <= t < t_end]; after = [x for t, x in ld.r_ if t >= t_end]
wb = [x for t, x in ld.w_ if t < t_start]; wd = [x for t, x in ld.w_ if t_start <= t < t_end]; wa = [x for t, x in ld.w_ if t >= t_end]
print('== 二:建索引之前 / 期间 / 之后,并发线程的读(find_one by _id)与写(insert_one)延迟')
print(f'  读  建之前 {lat_stats(before)}'); print(f'  读  建期间 {lat_stats(during)}'); print(f'  读  建之后 {lat_stats(after)}')
print(f'  写  建之前 {lat_stats(wb)}'); print(f'  写  建期间 {lat_stats(wd)}'); print(f'  写  建之后 {lat_stats(wa)}')
print(f'  并发线程遇到的错误数: {len(ld.err)} {ld.err[:2]}')
print('== 三:currentOp 看到的建索引进度(每 0.5 秒取样)')
seen = []
for t, msg, pr in prog:
    key = (msg, json.dumps(pr, default=str)[:80])
    if not seen or seen[-1][1] != key: seen.append((t, key))
for t, (msg, pr) in seen[:8]: print(f'  {t:>5.1f}s  {msg}  {pr}')
print('== 四:建索引期间插入的文档也在索引里:索引条目数 = 文档数')
ks = db.command('validate', 't', full=True)['keysPerIndex']; cnt = db.t.count_documents({})
print(f'  文档数 {cnt:,};索引条目 {ks}')
msh(n, EXJS + 'ex(db.t.find({k: {$gte: 0, $lt: 100000}}).explain("executionStats"))', label='db.t.find({k: {$gte: 0, $lt: 100000}})', n=12)
print('== 五:唯一索引在建的过程中,另一个线程插入了和已有文档重复的值:看构建和插入各自的结果')
res = {}
def build_u():
    t0 = time.perf_counter()
    try: db.t.create_index('u', unique=True); res['build'] = 'ok'
    except Exception as e: res['build'] = str(e).replace('\n', ' ')[:230]
    res['build_s'] = time.perf_counter() - t0
tb = threading.Thread(target=build_u); tb.start(); time.sleep(0.3)
ins = []
for j in range(50):
    try: db.t.insert_one({'_id': 50_000_000 + j, 'k': 1, 'u': 123, 'z': 1, 'pad': 'dup'}); ins.append(j)
    except Exception as e: res['insert_err'] = str(e)[:120]; break
    time.sleep(0.02)
tb.join()
print(f'  建唯一索引耗时 {res["build_s"]:.1f} s;并发线程插入 u=123 的重复文档(原来已有一个 u=123)成功了 {len(ins)} 次' + (f',然后被拒绝: {res["insert_err"]}' if 'insert_err' in res else ''))
print(f'  建唯一索引的结果: {res["build"]}')
print(f'  索引列表: {[i["name"] for i in db.t.list_indexes()]};u=123 的文档数 {db.t.count_documents({"u": 123})}')
print('== 六:建索引期间对集合做 drop:会怎样?')
res2 = {}
def build_d():
    t0 = time.perf_counter()
    try: db.t.create_index('z'); res2['build'] = 'ok'
    except Exception as e: res2['build'] = str(e).replace('\n', ' ')[:160]
    res2['build_s'] = time.perf_counter() - t0
tb = threading.Thread(target=build_d); tb.start(); time.sleep(1.5)
t0 = time.perf_counter()
try: db.t.drop(); res2['drop'] = 'ok'
except Exception as e: res2['drop'] = str(e)[:100]
res2['drop_s'] = time.perf_counter() - t0
tb.join()
print(f'  建 z 索引 1.5 s 后在另一个连接上 drop 整个集合:drop {res2["drop"]},耗时 {res2["drop_s"]:.2f} s;建索引的线程: {res2["build"]},{res2["build_s"]:.2f} s')
n.stop()
