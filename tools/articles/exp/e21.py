import sys, os, sqlite3, bisect, io; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e21')
d = pdir('e21')
P = products(); PG = pages(); N = len(P)
zc3 = zstandard.ZstdCompressor(level=3); zd3 = zstandard.ZstdDecompressor()
recs = [j(x) for x in P]
dct = zstandard.train_dictionary(16384, recs[:3000]); zcd = zstandard.ZstdCompressor(level=3, dict_data=dct); zdd = zstandard.ZstdDecompressor(dict_data=dct)
def conn(p):
    c = sqlite3.connect(p, isolation_level=None); c.execute('PRAGMA journal_mode=wal'); c.execute('PRAGMA synchronous=NORMAL'); return c
def fresh(name):
    p = d / name
    for suf in ('', '-wal', '-shm'):
        try: os.remove(str(p) + suf)
        except FileNotFoundError: pass
    return p
def fsize(p):
    t = 0
    for suf in ('', '-wal'):
        if os.path.exists(str(p) + suf): t += os.path.getsize(str(p) + suf)
    return t
def ckpt(c): c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
store = {}
print('== 一:2 万条 products 用 8 种方式落盘:文件大小与写入耗时(单次测量;sqlite 用 WAL、批量事务)')
print(f'  {"方式":44s} {"文件字节":>9s} {"写入耗时":>9s} {"相对 JSONL":>9s}')
def rec(lab, p, t): store[lab] = (fsize(p), t); print(f'  {lab:44s} {fsize(p):9d} {t * 1000:7.0f}ms {fsize(p) * 100 / len(jl(P)):8.1f}%')
p = fresh('a.jsonl'); t0 = time.perf_counter(); b = jl(P) + b'\n'; p.write_bytes(b); rec('A  JSON Lines 文本', p, time.perf_counter() - t0)
p = fresh('b.jsonl.zst'); t0 = time.perf_counter(); p.write_bytes(zc3.compress(jl(P) + b'\n')); rec('B  JSON Lines 整个文件一个 zstd-3 帧', p, time.perf_counter() - t0)
p = fresh('c.jsonl.zst'); t0 = time.perf_counter(); chunks = []; offs = [0]
for s in range(0, N, 1000): c_ = zc3.compress(b'\n'.join(recs[s:s + 1000]) + b'\n'); chunks.append(c_); offs.append(offs[-1] + len(c_))
p.write_bytes(b''.join(chunks)); rec('C  JSON Lines 每 1000 条一个 zstd 帧(带偏移索引)', p, time.perf_counter() - t0)
p = fresh('d.db'); t0 = time.perf_counter(); c = conn(p); c.execute('CREATE TABLE r (id INTEGER PRIMARY KEY, doc TEXT)'); c.execute('BEGIN'); c.executemany('INSERT INTO r VALUES (?,?)', [(x['id'], r_.decode()) for x, r_ in zip(P, recs)]); c.execute('COMMIT'); ckpt(c); c.close(); rec('D  sqlite:id + JSON 文本', p, time.perf_counter() - t0)
p = fresh('e.db'); t0 = time.perf_counter(); c = conn(p); c.execute('CREATE TABLE r (id INTEGER PRIMARY KEY, doc BLOB)'); c.execute('BEGIN'); c.executemany('INSERT INTO r VALUES (?,?)', [(x['id'], zc3.compress(r_)) for x, r_ in zip(P, recs)]); c.execute('COMMIT'); ckpt(c); c.close(); rec('E  sqlite:id + 每条单独 zstd-3 的 BLOB', p, time.perf_counter() - t0)
p = fresh('f.db'); t0 = time.perf_counter(); c = conn(p); c.execute('CREATE TABLE r (id INTEGER PRIMARY KEY, doc BLOB)'); c.execute('BEGIN'); c.executemany('INSERT INTO r VALUES (?,?)', [(x['id'], zcd.compress(r_)) for x, r_ in zip(P, recs)]); c.execute('COMMIT'); ckpt(c); c.close(); rec('F  sqlite:id + 每条 zstd-3 + 16 KiB 字典', p, time.perf_counter() - t0)
p = fresh('g.db'); t0 = time.perf_counter(); c = conn(p); c.execute('CREATE TABLE r (id INTEGER PRIMARY KEY, url TEXT, title TEXT, price REAL, currency TEXT, stock INT, rating REAL, tags TEXT, category TEXT, updated_at TEXT, seller_id INT, seller_name TEXT)'); c.execute('BEGIN')
c.executemany('INSERT INTO r VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', [(x['id'], x['url'], x['title'], x['price'], x['currency'], x['stock'], x['rating'], ','.join(x['tags']), x['category'], x['updated_at'], x['seller']['id'], x['seller']['name']) for x in P]); c.execute('COMMIT'); ckpt(c); c.close(); rec('G  sqlite:每个字段一列(关系表)', p, time.perf_counter() - t0)
p = fresh('h.db'); t0 = time.perf_counter(); c = conn(p); c.execute('CREATE TABLE r (first_id INTEGER PRIMARY KEY, doc BLOB)'); c.execute('BEGIN')
c.executemany('INSERT INTO r VALUES (?,?)', [(P[s]['id'], zc3.compress(b'\n'.join(recs[s:s + 100]))) for s in range(0, N, 100)]); c.execute('COMMIT'); ckpt(c); c.close(); rec('H  sqlite:每 100 条一个 zstd-3 的 BLOB', p, time.perf_counter() - t0)
print('== 二:按 id 取一条记录(随机 2000 次,每次的中位耗时,微秒;文件已写好,sqlite 每次新开连接不计,连接复用)')
rr = random.Random(21); picks = [rr.randrange(N) for _ in range(2000)]
def lat(fn):
    ts = []
    for k in picks: t0 = time.perf_counter(); v = fn(k); ts.append(time.perf_counter() - t0); assert json.loads(v)['id'] == P[k]['id']
    ts.sort(); return ts[len(ts) // 2] * 1e6
a_off = [0]
for r_ in recs: a_off.append(a_off[-1] + len(r_) + 1)
fa = open(d / 'a.jsonl', 'rb'); cdat = (d / 'c.jsonl.zst').read_bytes(); bdat = (d / 'b.jsonl.zst').read_bytes()
def la(k): fa.seek(a_off[k]); return fa.read(a_off[k + 1] - a_off[k] - 1)
def lb(k): return zd3.decompress(bdat, max_output_size=1 << 28).split(b'\n')[k]
def lc(k): ch = k // 1000; return zd3.decompress(cdat[offs[ch]:offs[ch + 1]]).split(b'\n')[k % 1000]
cs = {x: conn(d / x) for x in ('d.db', 'e.db', 'f.db', 'g.db', 'h.db')}
def ld(k): return cs['d.db'].execute('SELECT doc FROM r WHERE id=?', (P[k]['id'],)).fetchone()[0]
def le(k): return zd3.decompress(cs['e.db'].execute('SELECT doc FROM r WHERE id=?', (P[k]['id'],)).fetchone()[0])
def lf(k): return zdd.decompress(cs['f.db'].execute('SELECT doc FROM r WHERE id=?', (P[k]['id'],)).fetchone()[0])
def lg(k):
    r_ = cs['g.db'].execute('SELECT * FROM r WHERE id=?', (P[k]['id'],)).fetchone(); return json.dumps({'id': r_[0]})
def lh(k):
    row = cs['h.db'].execute('SELECT first_id, doc FROM r WHERE first_id <= ? ORDER BY first_id DESC LIMIT 1', (P[k]['id'],)).fetchone(); return zd3.decompress(row[1]).split(b'\n')[k % 100]
for lab, fn, n in (('A  JSONL + 行偏移索引', la, 2000), ('B  整个文件一个 zstd 帧(每次解压整个文件!)', lb, 5), ('C  每 1000 条一个帧 + 偏移索引', lc, 2000), ('D  sqlite JSON 文本', ld, 2000), ('E  sqlite 每条 zstd BLOB', le, 2000), ('F  sqlite 每条 zstd + 字典', lf, 2000), ('G  sqlite 列(取一整行)', lg, 2000), ('H  sqlite 每 100 条一个 BLOB', lh, 2000)):
    save = picks; picks = save[:n]; v = lat(fn); picks = save
    print(f'  {lab:44s} {v:10.1f} 微秒')
print('== 三:扫全表做统计——"库存大于 100 的商品的价格总和"(各 3 次中位数,毫秒)')
truth = sum(x['price'] for x in P if x['stock'] > 100)
def sa(): return sum(o['price'] for o in map(json.loads, open(d / 'a.jsonl', 'rb').read().split(b'\n')[:-1]) if o['stock'] > 100)
def sb(): return sum(o['price'] for o in map(json.loads, zd3.decompress(bdat, max_output_size=1 << 28).split(b'\n')[:-1]) if o['stock'] > 100)
def sd_json1(): return cs['d.db'].execute("SELECT sum(json_extract(doc,'$.price')) FROM r WHERE json_extract(doc,'$.stock') > 100").fetchone()[0]
def se(): return sum(o['price'] for o in (json.loads(zd3.decompress(r_[0])) for r_ in cs['e.db'].execute('SELECT doc FROM r')) if o['stock'] > 100)
def sg(): return cs['g.db'].execute('SELECT sum(price) FROM r WHERE stock > 100').fetchone()[0]
for lab, fn in (('A  JSONL 逐行 json.loads', sa), ('B  zstd 帧解压后逐行 json.loads', sb), ('D  sqlite JSON 文本,SQL 里 json_extract', sd_json1), ('E  sqlite zstd BLOB,逐行解压 + json.loads', se), ('G  sqlite 列,SQL 直接聚合', sg)):
    m = timeit(fn, 3)[0]; v = fn(); print(f'  {lab:44s} {m * 1000:8.1f} ms  结果 {v:.2f} {"✓" if abs(v - truth) < 1e-6 else "✗"}')
print(f'  正确结果 {truth:.2f}')
print('== 四:原始页面 1500 页(共 20.8 MB):放成一个个文件、sqlite 原样、sqlite 每页 zstd、每页 zstd + 字典')
pdirp = d / 'pagesdir'; pdirp.mkdir()
for i, pg in enumerate(PG): (pdirp / f'{i}.html').write_bytes(pg)
logical = sum(map(len, PG)); disk = sum(os.stat(f).st_blocks * 512 for f in pdirp.iterdir())
dpg = zstandard.train_dictionary(65536, PG[:500]); zcp = zstandard.ZstdCompressor(level=3, dict_data=dpg); z3 = zstandard.ZstdCompressor(level=3)
for nm, enc in (('p_raw.db', lambda b: b), ('p_zstd.db', z3.compress), ('p_dict.db', zcp.compress)):
    p = fresh(nm); c = conn(p); c.execute('CREATE TABLE p (id INTEGER PRIMARY KEY, body BLOB)'); c.execute('BEGIN'); c.executemany('INSERT INTO p VALUES (?,?)', [(i, enc(pg)) for i, pg in enumerate(PG)]); c.execute('COMMIT'); ckpt(c); c.close()
big = z3.compress(b''.join(PG)); print(f'  逻辑大小 {logical} 字节;1500 个文件的磁盘占用(按块计){disk} 字节({disk * 100 / logical:.1f}%,每个文件向上取整到文件系统的块大小)')
for nm, lab in (('p_raw.db', 'sqlite 原样存放'), ('p_zstd.db', 'sqlite 每页 zstd-3'), ('p_dict.db', 'sqlite 每页 zstd-3 + 64 KiB 字典')): print(f'  {lab:34s} {fsize(d / nm):9d} 字节({fsize(d / nm) * 100 / logical:.1f}%)')
print(f'  对照:全部页面拼成一个 zstd-3 帧 {len(big)} 字节({len(big) * 100 / logical:.1f}%);字典本身 {len(dpg.as_bytes())} 字节(要和数据一起保存)')
print('== 五:更新 1000 条记录的价格(随机,各一次):JSONL 要重写整个文件;sqlite 改行;压缩的 BLOB 要解压、改、再压缩')
ids = random.Random(5).sample(range(N), 1000)
t0 = time.perf_counter(); newrecs = list(recs)
for k in ids: o = dict(P[k]); o['price'] = round(o['price'] * 1.1, 2); newrecs[k] = j(o)
(d / 'a2.jsonl').write_bytes(b'\n'.join(newrecs) + b'\n'); print(f'  A  JSONL:重写整个文件(7.2 MB){(time.perf_counter() - t0) * 1000:8.0f} ms')
for lab, db, upd in (('D  sqlite JSON 文本', 'd.db', lambda c, k: c.execute('UPDATE r SET doc=? WHERE id=?', (j(dict(P[k], price=round(P[k]['price'] * 1.1, 2))).decode(), P[k]['id']))),
                     ('E  sqlite 每条 zstd BLOB', 'e.db', lambda c, k: c.execute('UPDATE r SET doc=? WHERE id=?', (zc3.compress(j(dict(P[k], price=round(P[k]['price'] * 1.1, 2)))), P[k]['id']))),
                     ('G  sqlite 列', 'g.db', lambda c, k: c.execute('UPDATE r SET price=? WHERE id=?', (round(P[k]['price'] * 1.1, 2), P[k]['id'])))):
    c = cs[db]; t0 = time.perf_counter(); c.execute('BEGIN')
    for k in ids: upd(c, k)
    c.execute('COMMIT'); print(f'  {lab:28s} {(time.perf_counter() - t0) * 1000:8.0f} ms')
c = cs['h.db']; t0 = time.perf_counter(); c.execute('BEGIN'); done = set()
for k in ids:
    s = (k // 100) * 100
    row = c.execute('SELECT doc FROM r WHERE first_id=?', (P[s]['id'],)).fetchone(); lines = zd3.decompress(row[0]).split(b'\n'); o = json.loads(lines[k - s]); o['price'] = round(o['price'] * 1.1, 2); lines[k - s] = j(o); c.execute('UPDATE r SET doc=? WHERE first_id=?', (zc3.compress(b'\n'.join(lines)), P[s]['id']))
c.execute('COMMIT'); print(f'  H  sqlite 每 100 条一个 BLOB(每条更新都要重压 100 条)     {(time.perf_counter() - t0) * 1000:8.0f} ms')
print('== 六:删掉一半记录后文件会缩小吗(sqlite 不会自动缩小:空出的整页进入空闲列表,留在文件里,要 VACUUM)')
def fresh_db():
    p = fresh('v.db'); c = conn(p); c.execute('CREATE TABLE r (id INTEGER PRIMARY KEY, doc TEXT)'); c.execute('BEGIN'); c.executemany('INSERT INTO r VALUES (?,?)', [(x['id'], r_.decode()) for x, r_ in zip(P, recs)]); c.execute('COMMIT'); ckpt(c); return p, c
ps = None
for lab, where in (('隔行删除(id 为偶数的行)', 'id % 2 = 0'), ('连续删除(前一半 id)', f'id < {P[N // 2]["id"]}')):
    p, c = fresh_db(); s0 = fsize(p); ps = c.execute('PRAGMA page_size').fetchone()[0]; total = c.execute('PRAGMA page_count').fetchone()[0]
    c.execute(f'DELETE FROM r WHERE {where}'); ckpt(c); s1 = fsize(p); free = c.execute('PRAGMA freelist_count').fetchone()[0]
    t0 = time.perf_counter(); c.execute('VACUUM'); ckpt(c); tv = time.perf_counter() - t0; s2 = fsize(p); c.close()
    print(f'  {lab}:写入后 {s0} 字节({total} 页 × {ps});删除后文件 {s1} 字节,空闲页 {free} 个({free * 100 / total:.1f}%);VACUUM 后 {s2} 字节(用时 {tv * 1000:.0f} ms)')
purge()
