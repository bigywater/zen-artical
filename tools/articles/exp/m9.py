import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m9'); reset()
n = Node('m9', cache=0.25); n.start(); c = n.client(); db = c.test
r = random.Random(9)
def docs(a, b): return [{'_id': i, 'k': r.randrange(1_000_000), 'pad': ''.join(r.choice('abcdefghijklmnop') for _ in range(300))} for i in range(a, b)]
def stat(coll='t'):
    c.admin.command('fsync'); time.sleep(1.5); c.admin.command('fsync')
    st = db.command('collStats', coll); w = st['wiredTiger']
    uri = w['uri'].split(':')[-1]; f = n.db / f'{uri}.wt'
    free = w['block-manager'].get('file bytes available for reuse', 0)
    ix = sum(v for v in st['indexSizes'].values())
    return dict(count=st['count'], size=st['size'], storage=st['storageSize'], file=f.stat().st_size if f.exists() else 0, free=free, idx=ix, freeIdx=sum(db.command('collStats', coll)['indexDetails'][k]['block-manager'].get('file bytes available for reuse', 0) for k in st['indexDetails']))
def row(lbl, s): print(f'  {lbl:<22}{s["count"]:>9,}{s["size"]:>13,}{s["storage"]:>13,}{s["file"]:>13,}{s["free"]:>13,}{s["idx"]:>12,}')
HDR = f'  {"":<22}{"文档数":>9}{"dataSize":>13}{"storageSize":>13}{"磁盘文件":>13}{"可复用空闲":>13}{"索引总大小":>12}'
N = 120000
print(f'== 一:插入 {N:,} 个文档(每个约 340 字节,带 k 上的二级索引)')
db.t.create_index('k')
for i in range(0, N, 5000): db.t.insert_many(docs(i, i + 5000), ordered=False)
print(HDR); s0 = stat(); row('插入后', s0)
print('== 二:deleteMany 删掉 90% 的文档(_id 不是 10 的倍数的)之后,磁盘文件没有变小,只是多了“可复用空闲”')
t0 = time.perf_counter(); res = db.t.delete_many({'$expr': {'$ne': [{'$mod': ['$_id', 10]}, 0]}}); dt = time.perf_counter() - t0
print(f'  delete_many 删除 {res.deleted_count:,} 个,耗时 {dt:.1f} s')
print(HDR); s1 = stat(); row('删除后', s1)
print(f'  磁盘文件 {s0["file"]:,} → {s1["file"]:,}(变化 {s1["file"] - s0["file"]:+,} 字节);可复用空闲 {s0["free"]:,} → {s1["free"]:,}')
print('== 三:再插入同样数量的新文档:先用文件里的空闲空间,文件不再长大')
for i in range(N, N + 100000, 5000): db.t.insert_many(docs(i, i + 5000), ordered=False)
print(HDR); s2 = stat(); row('再插入 10 万个后', s2)
print(f'  磁盘文件 {s1["file"]:,} → {s2["file"]:,}({s2["file"] - s1["file"]:+,} 字节);可复用空闲 {s1["free"]:,} → {s2["free"]:,}')
print('== 四:再删掉 90%,然后 compact:文件缩小,空闲空间还给操作系统')
res = db.t.delete_many({'$expr': {'$ne': [{'$mod': ['$_id', 10]}, 0]}}); print(f'  又删除了 {res.deleted_count:,} 个')
print(HDR); s3 = stat(); row('删除后', s3)
t0 = time.perf_counter(); out = db.command('compact', 't'); dt = time.perf_counter() - t0
print(f'  compact 返回 {out}(耗时 {dt:.1f} s)')
s4 = stat(); row('compact 后', s4)
print(f'  磁盘文件 {s3["file"]:,} → {s4["file"]:,}(减少 {s3["file"] - s4["file"]:,} 字节,{1 - s4["file"] / s3["file"]:.0%});索引总大小 {s3["idx"]:,} → {s4["idx"]:,}')
print('== 五:compact 期间同一个集合上的读写:另一个线程不停地 find_one 和 insert_one,记录每次延迟')
db.t2.create_index('k')
for i in range(0, N, 5000): db.t2.insert_many(docs(i, i + 5000), ordered=False)
db.t2.delete_many({'$expr': {'$ne': [{'$mod': ['$_id', 10]}, 0]}})
c.admin.command('fsync'); time.sleep(1)
stop = threading.Event(); lat = {'read': [], 'write': []}; errs = []; started = threading.Event()
def worker():
    cc = n.client(); d = cc.test; i = 10_000_000; started.set()
    while not stop.is_set():
        t0 = time.perf_counter()
        try: d.t2.find_one({'_id': 10})
        except Exception as e: errs.append(str(e)[:80])
        lat['read'].append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        try: d.t2.insert_one({'_id': i, 'k': i, 'pad': 'x'}); i += 1
        except Exception as e: errs.append(str(e)[:80])
        lat['write'].append((time.perf_counter() - t0) * 1000)
th = threading.Thread(target=worker); th.start(); started.wait(); time.sleep(0.5)
t0 = time.perf_counter(); out = db.command('compact', 't2'); dt = time.perf_counter() - t0
time.sleep(0.5); stop.set(); th.join()
for k in ('read', 'write'):
    x = sorted(lat[k]); print(f'  compact 期间(含前后各 0.5 s)的 {k}: {len(x)} 次,中位数 {median(x):.2f} ms,最大 {x[-1]:.0f} ms')
print(f'  compact 本身耗时 {dt:.1f} s;期间工作线程的错误数: {len(errs)} {errs[:2]}')
print('== 六:想马上还磁盘:整个集合不要了就 drop(文件立刻删掉),比 deleteMany({}) 彻底')
db.t3.insert_many(docs(0, 50000)); s5 = stat('t3'); print(f'  t3 插入 50,000 个: 磁盘文件 {s5["file"]:,}')
db.t3.delete_many({}); s6 = stat('t3'); print(f'  deleteMany({{}}) 之后: 文档数 {s6["count"]},磁盘文件 {s6["file"]:,},可复用空闲 {s6["free"]:,}')
uri = db.command('collStats', 't3')['wiredTiger']['uri'].split(':')[-1]
db.t3.drop(); time.sleep(2); c.admin.command('fsync'); time.sleep(1)
print(f'  drop 之后文件还在吗: {(n.db / (uri + ".wt")).exists()}')
n.stop()
