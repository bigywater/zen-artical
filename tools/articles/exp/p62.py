import sys, os, sqlite3, threading, queue, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p62')
d = pdir('p62')
SCHEMA = 'CREATE TABLE r (id INTEGER PRIMARY KEY, url TEXT, status INT, body BLOB)'
BODY = b'x' * 2000
def mk(name, mode='wal', sync='NORMAL'):
    p = d / name
    for suf in ('', '-wal', '-shm', '-journal'):
        try: os.remove(str(p) + suf)
        except FileNotFoundError: pass
    c = sqlite3.connect(p); c.execute(f'PRAGMA journal_mode={mode}'); c.execute(f'PRAGMA synchronous={sync}'); c.execute(SCHEMA); c.commit(); c.close(); return p
def conn(p, **kw):
    c = sqlite3.connect(p, isolation_level=None, **kw); return c           # 自己管事务
def sizes(p): return {s or 'db': round(os.path.getsize(str(p) + s) / 1024) for s in ('', '-wal') if os.path.exists(str(p) + s)}

def rep(f, n=5):
    r = [f() for _ in range(n)]; return statistics.median(r), min(r), max(r)
print('== 一:单线程,每行一个事务(提交一次)——日志模式与 synchronous 对每秒提交次数的影响,每组 2000 行,重复 5 次取中位数(括号里是最小–最大)')
print(f'  sqlite 版本 {sqlite3.sqlite_version},Python sqlite3 模块,数据库文件在本机磁盘的临时目录')
def one(mode, sync):
    p = mk('a.db', mode, sync); c = conn(p); c.execute(f'PRAGMA synchronous={sync}'); t0 = time.perf_counter()
    for i in range(2000): c.execute('BEGIN'); c.execute('INSERT INTO r(url,status,body) VALUES(?,?,?)', (f'http://x/{i}', 200, BODY)); c.execute('COMMIT')
    t = time.perf_counter() - t0; c.close(); return 2000 / t
for mode, sync in (('delete', 'FULL'), ('delete', 'NORMAL'), ('wal', 'FULL'), ('wal', 'NORMAL'), ('wal', 'OFF')):
    m, lo, hi = rep(lambda: one(mode, sync)); p = mk('a.db', mode, sync); c = conn(p); c.execute(f'PRAGMA synchronous={sync}'); print(f'  journal_mode={c.execute("PRAGMA journal_mode").fetchone()[0]:6s} synchronous={sync:6s}(PRAGMA 读回 {c.execute("PRAGMA synchronous").fetchone()[0]}):中位 {m:6.0f} 次提交/秒({lo:.0f}–{hi:.0f})'); c.close()

def writer_threads(p, n, rows, timeout, mode_busy=True, batch=1):
    errs = []; done = []
    def w(k):
        c = conn(p, timeout=timeout); t0 = time.perf_counter(); i = 0
        while i < rows:
            try:
                c.execute('BEGIN IMMEDIATE' if mode_busy else 'BEGIN')
                for j in range(batch):
                    c.execute('INSERT INTO r(url,status,body) VALUES(?,?,?)', (f'http://x/{k}/{i + j}', 200, BODY))
                c.execute('COMMIT'); i += batch
            except sqlite3.OperationalError as e:
                errs.append(str(e)); 
                try: c.execute('ROLLBACK')
                except Exception: pass
                time.sleep(0.001)
        done.append(time.perf_counter() - t0); c.close()
    ths = [threading.Thread(target=w, args=(k,)) for k in range(n)]; t0 = time.perf_counter()
    for t in ths: t.start()
    for t in ths: t.join()
    return time.perf_counter() - t0, errs
print('== 二:4 个线程各自一个连接、各写 500 行(每行一个事务,BEGIN IMMEDIATE),busy 等待时间不同,会发生什么(重复 5 次,行/秒取中位数,括号为最小–最大;locked 次数取中位数)')
for mode in ('delete', 'wal'):
    for to in (0, 0.05, 5):
        rs = []; es = []
        for _ in range(5):
            p = mk('b.db', mode); t, errs = writer_threads(p, 4, 500, to); c = conn(p); n = c.execute('SELECT count(*) FROM r').fetchone()[0]; c.close(); assert n == 2000; rs.append(2000 / t); es.append(len(errs))
        print(f'  journal_mode={mode:6s} busy 等待 timeout={to}:中位 {statistics.median(rs):6.0f} 行/秒({min(rs):.0f}–{max(rs):.0f}),遇到 "database is locked" 并重试的次数中位 {statistics.median(es):.0f}({min(es)}–{max(es)}),每次最后表里都是 2000 行')
print('== 三:同样的 2000 行,换成"一个写线程 + 队列":多个爬虫线程把结果放进 queue,写线程收齐一批就一次提交')
def queue_writer(p, nprod, rows, batch, qmax=0):
    q = queue.Queue(qmax); stop = object(); stats = dict(commits=0)
    def wr():
        c = conn(p); buf = []
        while True:
            x = q.get()
            if x is stop:
                if buf: c.execute('BEGIN'); c.executemany('INSERT INTO r(url,status,body) VALUES(?,?,?)', buf); c.execute('COMMIT'); stats['commits'] += 1
                break
            buf.append(x)
            if len(buf) >= batch: c.execute('BEGIN'); c.executemany('INSERT INTO r(url,status,body) VALUES(?,?,?)', buf); c.execute('COMMIT'); stats['commits'] += 1; buf = []
        c.close()
    wt = threading.Thread(target=wr); wt.start()
    def prod(k):
        for i in range(rows): q.put((f'http://x/{k}/{i}', 200, BODY))
    ps = [threading.Thread(target=prod, args=(k,)) for k in range(nprod)]; t0 = time.perf_counter()
    for t in ps: t.start()
    for t in ps: t.join()
    q.put(stop); wt.join(); return time.perf_counter() - t0, stats['commits']
for batch in (1, 10, 100, 500):
    rs = []
    for _ in range(5):
        p = mk('c.db', 'wal'); t, commits = queue_writer(p, 4, 500, batch); c = conn(p); n = c.execute('SELECT count(*) FROM r').fetchone()[0]; c.close(); assert n == 2000; rs.append(2000 / t)
    print(f'  4 个生产线程各放 500 行,批大小 {batch:3d}:中位 {statistics.median(rs):6.0f} 行/秒({min(rs):.0f}–{max(rs):.0f}),写线程提交 {commits} 次,表里 2000 行,没有 locked 错误')
print('== 四:有人在写的时候,读连接会怎样(写连接开一个事务插入若干行后停 0.5 秒再提交;读连接在这期间执行 SELECT count(*),timeout=0)')
for mode in ('delete', 'wal'):
    for nrows in (10, 1000):
        p = mk('d.db', mode)
        c0 = conn(p); c0.execute('BEGIN'); c0.executemany('INSERT INTO r(url,status,body) VALUES(?,?,?)', [(f'u{i}', 200, BODY) for i in range(nrows)])
        rc = conn(p, timeout=0); t0 = time.perf_counter()
        try: n = rc.execute('SELECT count(*) FROM r').fetchone()[0]; res = f'读到 {n} 行'
        except sqlite3.OperationalError as e: res = f'错误 "{e}"'
        t = (time.perf_counter() - t0) * 1000
        time.sleep(0.5); c0.execute('COMMIT'); c0.close()
        n2 = rc.execute('SELECT count(*) FROM r').fetchone()[0]; rc.close()
        print(f'  journal_mode={mode:6s} 未提交的写事务里有 {nrows:4d} 行(约 {nrows * 2 / 1024:.1f} MiB):读连接 {res},用时 {t:.1f} ms;写提交之后再读:{n2} 行')
print('== 五:WAL 文件会长到多大(单线程,每 100 行提交一次,共 20000 行,每行约 2 KB)')
for lab, auto, reader in (('默认自动 checkpoint(1000 页)', 1000, False), ('关掉自动 checkpoint', 0, False), ('默认自动 checkpoint,但有一个读连接一直开着读事务', 1000, True)):
    p = mk('e.db', 'wal'); c = conn(p); c.execute(f'PRAGMA wal_autocheckpoint={auto}'); rc = None
    if reader: rc = conn(p); rc.execute('BEGIN'); rc.execute('SELECT count(*) FROM r').fetchone()
    mx = 0
    for b in range(200):
        c.execute('BEGIN'); c.executemany('INSERT INTO r(url,status,body) VALUES(?,?,?)', [(f'u{b}-{i}', 200, BODY) for i in range(100)]); c.execute('COMMIT'); mx = max(mx, os.path.getsize(str(p) + '-wal'))
    end = sizes(p)
    r = c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
    print(f'  {lab}:过程中 -wal 最大 {mx / 1048576:.1f} MiB;写完时文件大小(KiB){end};此时手动 checkpoint(TRUNCATE) 返回 {r}(busy, 日志页数, 已移回页数)')
    if rc: rc.execute('COMMIT'); rc.close()
    r2 = c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone(); print(f'     读事务结束后再 checkpoint(TRUNCATE):{r2},-wal 现在 {sizes(p).get("-wal", 0)} KiB'); c.close()
print('== 六:Python sqlite3 的几个容易踩的点')
p = mk('f.db', 'wal'); c = sqlite3.connect(p)
print(f'  默认 isolation_level={c.isolation_level!r};in_transaction(连接刚建好)={c.in_transaction}', end='')
c.execute('INSERT INTO r(url,status,body) VALUES(?,?,?)', ('u', 200, b'')); print(f';执行一条 INSERT 后 in_transaction={c.in_transaction}(Python 自动开了事务,没 commit 前别的连接看不到)')
c2 = sqlite3.connect(p); print(f'  另一个连接此时 SELECT count(*) = {c2.execute("SELECT count(*) FROM r").fetchone()[0]};commit 后 = ', end=''); c.commit(); print(c2.execute('SELECT count(*) FROM r').fetchone()[0])
res = []
def other():
    try: c.execute('SELECT 1')
    except Exception as e: res.append(f'{type(e).__name__}: {str(e)[:70]}')
t = threading.Thread(target=other); t.start(); t.join(); print(f'  连接默认 check_same_thread=True,在另一个线程里用同一个连接:{res[0] if res else "没有报错"}')
c.close(); c2.close()
purge()
