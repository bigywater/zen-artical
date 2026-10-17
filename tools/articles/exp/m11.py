import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m11'); reset()
n = Node('m11', cache=0.25); n.start(); c = n.client(); db = c.test
KEYS = ['maximum bytes configured', 'bytes currently in the cache', 'tracked dirty bytes in the cache', 'pages read into cache', 'pages written from cache',
        'application threads page read from disk to cache count', 'application thread time evicting (usecs)', 'pages evicted by application threads', 'unmodified pages evicted', 'modified pages evicted', 'pages queued for eviction']
def cache(cl=None):
    w = (cl or c).admin.command('serverStatus')['wiredTiger']['cache']; return {k: w.get(k, 0) for k in KEYS}
def mb(x): return f'{x / 1024 / 1024:,.1f} MB'
def delta(a, b): return {k: b[k] - a[k] for k in KEYS}
def lat_stats(x):
    x = sorted(x); return f'中位数 {median(x):.2f} ms,p99 {x[int(len(x) * .99)]:.2f} ms,最大 {x[-1]:.1f} ms'
w0 = c.admin.command('serverStatus')['wiredTiger']['cache']
print('== 一:缓存大小与淘汰阈值:--wiredTigerCacheSizeGB 0.25(最小值),serverStatus 里直接给出各个阈值')
print(f'  maximum bytes configured = {w0["maximum bytes configured"]:,}({mb(w0["maximum bytes configured"])})')
for k in ('eviction threshold cache full target multiplied by 100 for precision', 'eviction threshold cache full trigger multiplied by 100 for precision', 'eviction threshold dirty target multiplied by 100 for precision', 'eviction threshold dirty trigger multiplied by 100 for precision', 'eviction threshold updates target multiplied by 100 for precision', 'eviction threshold updates trigger multiplied by 100 for precision'):
    print(f'  {k.replace(" multiplied by 100 for precision", ""):<52}{w0[k] / 100:>6.1f}%')
N = 500000; r = random.Random(11)
print(f'== 二:装入 {N:,} 个文档(每个约 1.2 KB 的随机字节,不可压缩,总计约 600 MB,是缓存的 2 倍多),看缓存怎么被占满')
c0 = cache(); lats = []; t0 = time.perf_counter(); peak = [0]; stop = threading.Event()
def sampler():
    cc = n.client()
    while not stop.is_set():
        try: peak[0] = max(peak[0], cc.admin.command('serverStatus')['wiredTiger']['cache']['bytes currently in the cache'])
        except Exception: pass
        time.sleep(0.2)
th = threading.Thread(target=sampler); th.start()
for i in range(0, N, 1000):
    b = [{'_id': j, 'k': j % 1000, 'p': Binary(r.randbytes(1200))} for j in range(i, i + 1000)]
    t1 = time.perf_counter(); db.big.insert_many(b, ordered=False); lats.append((time.perf_counter() - t1) * 1000)
tot = time.perf_counter() - t0; stop.set(); th.join()
c1 = cache(); d = delta(c0, c1)
print(f'  耗时 {tot:.1f} s({N / tot:,.0f} 个/秒);每批 1000 个的延迟: {lat_stats(lats)}')
print(f'  采样到的缓存占用峰值 {mb(peak[0])}(上限 {mb(w0["maximum bytes configured"])}),结束时 {mb(c1["bytes currently in the cache"])},脏数据 {mb(c1["tracked dirty bytes in the cache"])}')
print(f'  装入期间:读入缓存的页 {d["pages read into cache"]:,},写出的页 {d["pages written from cache"]:,},被淘汰的页(未修改 {d["unmodified pages evicted"]:,} / 已修改 {d["modified pages evicted"]:,}),应用线程自己做的淘汰 {d["pages evicted by application threads"]:,}')
c.admin.command('fsync'); time.sleep(2)
st = db.command('collStats', 'big'); print(f'  集合 dataSize {mb(st["size"])},storageSize {mb(st["storageSize"])}')
def point_reads(ids, cl=None):
    d_ = (cl or c).test.big; ls = []
    for i in ids:
        t1 = time.perf_counter(); d_.find_one({'_id': i}); ls.append((time.perf_counter() - t1) * 1000)
    return ls
def phase(label, ids, reps=1, show_hdr=True):
    point_reads(ids[:2000])   # 预热
    a = cache(); t0 = time.perf_counter(); ls = point_reads(ids); dt = time.perf_counter() - t0; b = cache(); d = delta(a, b)
    print(f'  {label}: {len(ids):,} 次随机读,{len(ids) / dt:,.0f} 次/秒;{lat_stats(ls)};期间读入缓存的页 {d["pages read into cache"]:,}(每次读 {d["pages read into cache"] / len(ids):.2f} 页)')
    return ls
rr = random.Random(5)
print('== 三:工作集小于缓存:只读前 50,000 个文档(约 60 MB),先预热再测——几乎不再有“读入缓存”')
small = [rr.randrange(50000) for _ in range(20000)]
phase('工作集 60 MB / 缓存 256 MB', small)
print('== 四:工作集大于缓存:在全部 500,000 个文档里随机读,缓存装不下,读到不在缓存里的页就要读入(这里来自操作系统文件缓存或磁盘)并淘汰别的页')
big = [rr.randrange(N) for _ in range(20000)]
phase('工作集 600 MB / 缓存 256 MB', big)
a = cache(); phase('再来一轮', [rr.randrange(N) for _ in range(20000)]); b = cache(); print(f'  这一轮的淘汰:未修改页 {b["unmodified pages evicted"] - a["unmodified pages evicted"]:,},已修改页 {b["modified pages evicted"] - a["modified pages evicted"]:,}')
print('== 五:同样的读,缓存加大到 2 GB(重启后):工作集 600 MB 装得下,先读一遍预热')
n.cache = 2; n.restart(); c = n.client(); db = c.test
warm = list(range(0, N, 3)); [db.big.find_one({'_id': i}) for i in warm]
print(f'  预热后缓存占用 {mb(cache()["bytes currently in the cache"])}(上限 {mb(cache()["maximum bytes configured"])})')
phase('工作集 600 MB / 缓存 2 GB', [rr.randrange(N) for _ in range(20000)])
print('== 六:写压力:缓存 256 MB 与 2 GB 下,持续更新随机文档(每次改 1 KB 的随机字节),看应用线程是否被迫帮着淘汰(脏数据超过 20% 时才会)')
def update_load(label, secs=8):
    d_ = n.client().test.big; ls = []; a = cache(); t0 = time.perf_counter(); i = 0; rg = random.Random(77)
    while time.perf_counter() - t0 < secs:
        t1 = time.perf_counter(); d_.update_one({'_id': rg.randrange(N)}, {'$set': {'p': Binary(rg.randbytes(1200))}}); ls.append((time.perf_counter() - t1) * 1000); i += 1
    b = cache(); d = delta(a, b)
    print(f'  {label}: {i:,} 次更新({i / secs:,.0f} 次/秒);{lat_stats(ls)};应用线程做的淘汰 {d["pages evicted by application threads"]:,},应用线程淘汰耗时 {d["application thread time evicting (usecs)"] / 1000:,.0f} ms,读入缓存的页 {d["pages read into cache"]:,}')
update_load('缓存 2 GB')
n.cache = 0.25; n.restart(); c = n.client(); db = c.test
update_load('缓存 256 MB')

print('== 七:写入压力更大时:8 个线程同时 insert_many(每批 1000 个、每个 1.2 KB 随机字节),持续 8 秒,看脏数据和应用线程淘汰')
def insert_pressure(label, secs=8, threads=8):
    stop_t = time.perf_counter() + secs; lat = []; cnt = [0]; lock = threading.Lock(); peakd = [0]; ev = threading.Event()
    def samp():
        cc = n.client()
        while not ev.is_set():
            try:
                w = cc.admin.command('serverStatus')['wiredTiger']['cache']; peakd[0] = max(peakd[0], w['tracked dirty bytes in the cache'])
            except Exception: pass
            time.sleep(0.1)
    def worker(k):
        d_ = n.client().test.get_collection(f'w_{label}'); rg = random.Random(k); base = k * 10_000_000
        while time.perf_counter() < stop_t:
            b = [{'_id': base + cnt_, 'p': Binary(rg.randbytes(1200))} for cnt_ in range(0, 1000)]; base += 1000
            t1 = time.perf_counter(); d_.insert_many(b, ordered=False); l = (time.perf_counter() - t1) * 1000
            with lock: lat.append(l); cnt[0] += 1000
    a = cache(); st_ = threading.Thread(target=samp); st_.start()
    ths = [threading.Thread(target=worker, args=(k,)) for k in range(threads)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
    ev.set(); st_.join(); b_ = cache(); d = delta(a, b_)
    print(f'  {label}: {cnt[0]:,} 个文档({cnt[0] * 1.2 / 1024 / dt:,.0f} MB/s);每批延迟 {lat_stats(lat)};脏数据峰值 {mb(peakd[0])}(上限 {mb(b_["maximum bytes configured"])} 的 {peakd[0] / b_["maximum bytes configured"]:.0%});应用线程淘汰页 {d["pages evicted by application threads"]:,},应用线程淘汰耗时 {d["application thread time evicting (usecs)"] / 1000:,.0f} ms')
db.drop_collection('big')
n.cache = 2; n.restart(); c = n.client(); db = c.test
insert_pressure('cache2GB')
n.cache = 0.25; n.restart(); c = n.client(); db = c.test
insert_pressure('cache256MB')
n.stop()
