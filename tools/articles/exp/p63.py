import sys, os, sqlite3, threading, queue, time, statistics, subprocess, textwrap, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p63')
d = pdir('p63')
SCHEMA = 'CREATE TABLE r (id INTEGER PRIMARY KEY, url TEXT UNIQUE, status INT, body BLOB)'
INS = 'INSERT INTO r(url,status,body) VALUES(?,?,?)'
def mk(name):
    p = d / name
    for suf in ('', '-wal', '-shm'):
        try: os.remove(str(p) + suf)
        except FileNotFoundError: pass
    c = sqlite3.connect(p, isolation_level=None); c.execute('PRAGMA journal_mode=wal'); c.execute('PRAGMA synchronous=NORMAL'); c.execute(SCHEMA); c.close(); return p
def conn(p): return sqlite3.connect(p, isolation_level=None)
def med(f, n=3): r = sorted(f() for _ in range(n)); return r[len(r) // 2], r[0], r[-1]
def load(p, rows, body, batch):
    c = conn(p); lat = []; t0 = time.perf_counter()
    for s in range(0, rows, batch):
        t1 = time.perf_counter(); c.execute('BEGIN'); c.executemany(INS, [(f'u{i}', 200, body) for i in range(s, min(s + batch, rows))]); c.execute('COMMIT'); lat.append((time.perf_counter() - t1) * 1000)
    t = time.perf_counter() - t0; c.close(); return rows / t, lat

print('== 一:批大小对写入速度的影响(单线程,WAL + synchronous=NORMAL,每行正文 200 字节,共 50000 行,每个批大小重复 3 次取中位数,括号为最小–最大)')
for batch in (1, 10, 100, 1000, 10000, 50000):
    res = []; lats = []
    for _ in range(3):
        p = mk('a.db'); r, lat = load(p, 50000, b'x' * 200, batch); res.append(r); lats.append(lat)
    res_s = sorted(res); allat = sorted(l for lat in lats for l in lat)
    print(f'  批大小 {batch:5d}:中位 {res_s[1]:8.0f} 行/秒({res_s[0]:.0f}–{res_s[2]:.0f});提交次数 {len(lats[0]):5d};单个批事务(含组装参数)耗时 中位 {allat[len(allat) // 2]:.2f} ms,最大 {allat[-1]:.1f} ms')
print('== 二:每行大一些(正文 20 KB,不可压缩的随机内容,共 5000 行 ≈ 100 MB):批大小的影响')
body = os.urandom(20000)
for batch in (1, 10, 100, 1000):
    res = []
    for _ in range(3): p = mk('b.db'); r, lat = load(p, 5000, body, batch); res.append(r)
    res.sort(); print(f'  批大小 {batch:4d}:中位 {res[1]:6.0f} 行/秒({res[0]:.0f}–{res[2]:.0f}),相当于 {res[1] * 20000 / 1048576:.0f} MiB/秒;一批在内存里的正文共 {batch * 20000 / 1048576:.1f} MiB')
print('== 三:同样 50000 行、批大小 1000:executemany / 循环 execute / 一条多行 VALUES')
def way(kind):
    p = mk('c.db'); c = conn(p); t0 = time.perf_counter(); rows = [(f'u{i}', 200, b'x' * 200) for i in range(50000)]
    for s in range(0, 50000, 1000):
        chunk = rows[s:s + 1000]; c.execute('BEGIN')
        if kind == 'executemany': c.executemany(INS, chunk)
        elif kind == 'loop': 
            for r in chunk: c.execute(INS, r)
        else:
            for k in range(0, 1000, 300):          # sqlite 单条语句的参数个数有上限,这里每条 300 行 × 3 个参数
                sub = chunk[k:k + 300]; c.execute('INSERT INTO r(url,status,body) VALUES ' + ','.join(['(?,?,?)'] * len(sub)), [x for r in sub for x in r])
        c.execute('COMMIT')
    t = time.perf_counter() - t0; c.close(); return 50000 / t
for kind, lab in (('executemany', 'executemany'), ('loop', '循环 execute(同一个事务里)'), ('values', '多行 VALUES(每条 300 行)')):
    m, lo, hi = med(lambda: way(kind), 5); print(f'  {lab:28s} 中位 {m:8.0f} 行/秒({lo:.0f}–{hi:.0f})')
print('== 四:怎么触发一批:只按条数 / 条数或超时(到时间就提交)——生产者的速度忽快忽慢时,一行数据在内存里待多久才落盘')
def stale(batch, flush_s):
    q = queue.Queue(); STOP = object(); ages = []; commits = [0]
    p = mk('d.db'); 
    def wr():
        c = conn(p); buf = []; first = None
        while True:
            to = None if not buf or flush_s is None else max(0, first + flush_s - time.monotonic())
            try: x = q.get(timeout=to)
            except queue.Empty: x = None
            if x is STOP: break
            if x is not None:
                if not buf: first = time.monotonic()
                buf.append(x)
            if buf and (len(buf) >= batch or (flush_s is not None and time.monotonic() - first >= flush_s)):
                c.execute('BEGIN'); c.executemany(INS, [(f'u{i}', 200, b'') for i, _ in buf]); c.execute('COMMIT'); now = time.monotonic(); ages.extend(now - t for _, t in buf); commits[0] += 1; buf = []
        if buf: c.execute('BEGIN'); c.executemany(INS, [(f'u{i}', 200, b'') for i, _ in buf]); c.execute('COMMIT'); now = time.monotonic(); ages.extend(now - t for _, t in buf); commits[0] += 1
        c.close()
    th = threading.Thread(target=wr); th.start(); i = 0
    for phase_rate, dur in ((1000, 1.0), (20, 2.0), (1000, 1.0)):       # 每秒 1000 行 → 每秒 20 行 → 每秒 1000 行
        t0 = time.monotonic()
        while time.monotonic() - t0 < dur:
            q.put((i, time.monotonic())); i += 1; time.sleep(1 / phase_rate)
    q.put(STOP); th.join(); a = sorted(ages); return i, commits[0], a[len(a) // 2], a[int(len(a) * 0.99)], a[-1]
for batch, fl, lab in ((500, None, '只按条数,每 500 行提交'), (500, 0.2, '每 500 行或每 0.2 秒,先到者'), (50, None, '只按条数,每 50 行提交')):
    n, cm, a50, a99, amax = stale(batch, fl); print(f'  {lab}:生产 {n} 行,提交 {cm} 次;行从产生到落盘的等待:中位 {a50 * 1000:.0f} ms、p99 {a99 * 1000:.0f} ms、最大 {amax * 1000:.0f} ms(生产速度:1 秒 1000 行/s → 2 秒 20 行/s → 1 秒 1000 行/s;时间由 sleep 控制,实际速度略低)')
print('== 五:进程被 kill -9 时,内存里没提交的那批丢多少(子进程每生产一行就往管道写一个字节,批满才提交;跑 2.3 秒后 SIGKILL;每个批大小重复 3 次)')
CHILD = textwrap.dedent("""
    import sys, os, sqlite3, time
    p, batch, flush = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
    c = sqlite3.connect(p, isolation_level=None); buf = []; i = 0; first = None
    while True:
        i += 1; buf.append((f'u{i}', 200, b'x' * 200)); os.write(1, b'.')
        if first is None: first = time.monotonic()
        if len(buf) >= batch or (flush > 0 and time.monotonic() - first >= flush):
            c.execute('BEGIN'); c.executemany('INSERT INTO r(url,status,body) VALUES(?,?,?)', buf); c.execute('COMMIT'); buf = []; first = None
        time.sleep(0.001)
""")
open(d / 'child.py', 'w').write(CHILD)
for batch, fl in ((1, 0), (100, 0), (1000, 0), (1000, 0.2)):
    lost = []; made = []
    for _ in range(3):
        p = mk('e.db'); pr = subprocess.Popen([sys.executable, str(d / 'child.py'), str(p), str(batch), str(fl)], stdout=subprocess.PIPE); time.sleep(2.3); pr.send_signal(signal.SIGKILL); out = pr.stdout.read(); pr.wait()
        c = conn(p); n = c.execute('SELECT count(*) FROM r').fetchone()[0]; ok = c.execute('PRAGMA integrity_check').fetchone()[0]; c.close(); made.append(len(out)); lost.append(len(out) - n)
    print(f'  批大小 {batch:4d}{"(或 0.2 秒)" if fl else "          "}:生产 {made} 行,kill 之后库里少了 {lost} 行;integrity_check:{ok}')
print('== 六:一批里有一行违反约束(url 重复)时')
p = mk('f.db'); c = conn(p); c.execute(INS, ('u250', 200, b'')); 
rows = [(f'u{i}', 200, b'x') for i in range(500)]
c.execute('BEGIN')
try: c.executemany(INS, rows); c.execute('COMMIT'); res = '成功'
except sqlite3.IntegrityError as e: c.execute('ROLLBACK'); res = f'IntegrityError: {e}'
n1 = c.execute('SELECT count(*) FROM r').fetchone()[0]
print(f'  整批 executemany(500 行,第 251 行重复):{res};回滚之后库里 {n1} 行(只有开始前插入的那 1 行,另外 499 行也一起没了)')
c.execute('BEGIN'); ok = bad = 0
for r in rows:
    c.execute('SAVEPOINT s')
    try: c.execute(INS, r); c.execute('RELEASE s'); ok += 1
    except sqlite3.IntegrityError: c.execute('ROLLBACK TO s'); c.execute('RELEASE s'); bad += 1
c.execute('COMMIT'); n2 = c.execute('SELECT count(*) FROM r').fetchone()[0]
print(f'  整批失败后改成同一个事务里逐行 SAVEPOINT:成功 {ok} 行、跳过 {bad} 行,库里 {n2} 行(重复行带来的开销:每行多两条语句)')
tc0 = c.total_changes; c.execute('BEGIN'); c.executemany('INSERT OR IGNORE INTO r(url,status,body) VALUES(?,?,?)', [(f'v{i}', 200, b'x') for i in range(500)] + [('u250', 200, b'')]); c.execute('COMMIT')
print(f'  用 INSERT OR IGNORE 一次插入 500 个新行加 1 个重复行:库里 {c.execute("SELECT count(*) FROM r").fetchone()[0]} 行(重复的被静默跳过,不报错;连接的 total_changes 增加了 {c.total_changes - tc0},比 501 少 {501 - (c.total_changes - tc0)},靠它能算出跳过了几行)')
c.close()
purge()
