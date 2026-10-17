import sys, os, binascii, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m40'); reset()
n = Node('m40', cache=0.5); n.start(); c = n.client(); db = c.test
N = 200000; r = random.Random(40)
def hexs(k): return binascii.hexlify(r.randbytes(k // 2 + 1)).decode()[:k]
rows = []
for i in range(N):
    rows.append({'_id': i, 'i32': i, 'i64': Int64(i * 1000003), 'dbl': r.random() * 1e9, 'oid': ObjectId(), 'seq32': f'user-{i:027d}'[:32], 'rnd32': hexs(32),
                 's8': hexs(8), 's16': hexs(16), 's64': hexs(64), 's128': hexs(128), 'pre': 'common-prefix-of-fifty-characters-aaaaaaaaaaaaaaaaaa' + hexs(8), 'cat': r.choice(['red', 'green', 'blue', 'amber'])})
fill(db.t, N, lambda i: rows[i], batch=20000)
fields = ['i32', 'i64', 'dbl', 'oid', 'seq32', 'rnd32', 's8', 's16', 's64', 's128', 'pre', 'cat']
for f in fields: db.t.create_index(f)
c.admin.command('fsync'); time.sleep(2); c.admin.command('fsync')
sz = db.command('collStats', 't')['indexSizes']
def raw(f): return sum(len(bson.encode({'x': d[f]})) - 8 for d in rows[:2000]) / 2000   # 值本身的 BSON 字节数(去掉文档头尾和键名)
print(f'== 一:同一个集合 {N:,} 个文档,每个字段一个单字段索引,看每个索引多大(字节),平均每条索引条目多少字节;对照“值本身的 BSON 大小”')
print(f'  {"字段":<8}{"值的类型":<24}{"值的 BSON 字节":>14}{"索引大小":>14}{"每条目字节":>12}')
desc = {'i32': 'int32 递增', 'i64': 'int64', 'dbl': 'double 随机', 'oid': 'ObjectId', 'seq32': '32 字符,按顺序递增', 'rnd32': '32 字符随机十六进制', 's8': '8 字符随机', 's16': '16 字符随机', 's64': '64 字符随机', 's128': '128 字符随机', 'pre': '60 字符,前 52 个相同', 'cat': '4 个取值的枚举'}
for f in fields:
    k = f'{f}_1'; print(f'  {f:<8}{desc[f]:<24}{raw(f):>14.1f}{sz[k]:>14,}{sz[k] / N:>12.1f}')
print(f'  _id_ (int 递增)                              {sz["_id_"]:>14,}{sz["_id_"] / N:>12.1f}')
print(f'  数据本身 storageSize {db.command("collStats", "t")["storageSize"]:,};所有索引合计 {sum(sz.values()):,}')
print('== 二:前缀压缩:同样 32 字符,顺序递增的 seq32 比随机的 rnd32 小很多;前 52 个字符相同的 pre 并不比 8 字符的 s8 大太多')
print(f'  seq32 {sz["seq32_1"]:,} 字节;rnd32 {sz["rnd32_1"]:,} 字节(是顺序递增的 {sz["rnd32_1"] / sz["seq32_1"]:.1f} 倍)')
print(f'  pre(60 字符,前缀 52 相同){sz["pre_1"]:,} 字节;s8(8 字符随机){sz["s8_1"]:,} 字节;s64(64 字符随机){sz["s64_1"]:,} 字节')
print('== 三:字段越长索引越大:随机十六进制字符串 8 / 16 / 32 / 64 / 128 个字符的每条目字节数')
pts = [('s8', 8), ('s16', 16), ('rnd32', 32), ('s64', 64), ('s128', 128)]
for f, L in pts: print(f'  {L:>3} 字符:每条目 {sz[f"{f}_1"] / N:.1f} 字节')
(f1, L1), (f2, L2) = pts[0], pts[-1]
print(f'  从 8 到 128 字符,每多 1 个字符,每条索引条目平均多 {(sz[f"{f2}_1"] - sz[f"{f1}_1"]) / N / (L2 - L1):.2f} 字节')
print('== 四:关掉索引的前缀压缩:createIndex 时用 storageEngine.wiredTiger.configString 指定 prefix_compression=false')
db.np.insert_many([dict(x) for x in rows], ordered=False)
db.np.create_index('seq32', storageEngine={'wiredTiger': {'configString': 'prefix_compression=false'}}); db.np.create_index('pre', storageEngine={'wiredTiger': {'configString': 'prefix_compression=false'}})
c.admin.command('fsync'); time.sleep(2); c.admin.command('fsync')
sz2 = db.command('collStats', 'np')['indexSizes']
for f in ('seq32', 'pre'): print(f'  {f}_1:有前缀压缩(默认){sz[f + "_1"]:,} 字节;prefix_compression=false {sz2[f + "_1"]:,} 字节(是默认的 {sz2[f + "_1"] / sz[f + "_1"]:.1f} 倍)')
print('== 五:一个复合索引还是两个单字段索引?(cat 4 个取值 + rnd32)')
db.t.create_index([('cat', 1), ('rnd32', 1)], name='cat_rnd32'); c.admin.command('fsync'); time.sleep(2); c.admin.command('fsync')
sz3 = db.command('collStats', 't')['indexSizes']
print(f'  复合 {{cat, rnd32}} {sz3["cat_rnd32"]:,} 字节;单字段 cat {sz3["cat_1"]:,} + rnd32 {sz3["rnd32_1"]:,} = {sz3["cat_1"] + sz3["rnd32_1"]:,} 字节')
print('== 六:索引大小随文档数线性增长吗?rnd32 索引在 5 万 / 10 万 / 20 万个文档时的大小')
for m in (50000, 100000, 200000):
    coll = db[f'g{m}']; coll.insert_many(rows[:m], ordered=False); coll.create_index('rnd32'); c.admin.command('fsync'); time.sleep(1.5); c.admin.command('fsync')
    s = db.command('collStats', f'g{m}')['indexSizes']['rnd32_1']; print(f'  {m:>7,} 个文档:{s:,} 字节(每条目 {s / m:.1f} 字节)')
n.stop()
