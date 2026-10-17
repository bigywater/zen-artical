import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e17')
P = products(); T = timeseries(); N = nested(); PG = pages()
recs_p = [j(x) for x in P]; recs_t = [j(x) for x in T]; recs_n = [j(x) for x in N]
train_p, test_p = recs_p[:5000], recs_p[5000:7000]
def train(samples, size): return zstandard.train_dictionary(size, samples)
def tot(cc, items): return sum(len(cc.compress(x)) for x in items)
raw = sum(map(len, test_p))
print('== 一:单条记录(products 一条约 360 字节)单独压缩:没有字典与有字典(用 5000 条训练、16 KiB 字典,在另外 2000 条上测)')
dct = train(train_p, 16384); zd = zstandard.ZstdCompressor(level=3, dict_data=dct); z0 = zstandard.ZstdCompressor(level=3)
print(f'  {"方式":28s} {"2000 条共":>10s} {"平均每条":>8s} {"压缩比":>7s}')
rows = [('不压缩(紧凑 JSON)', raw), ('gzip-6', sum(len(zlib.compress(x, 6)) for x in test_p)), ('zstd-3,无字典', tot(z0, test_p)), ('zstd-3,16 KiB 字典', tot(zd, test_p)), ('zstd-19,16 KiB 字典', tot(zstandard.ZstdCompressor(level=19, dict_data=dct), test_p))]
for lab, t in rows: print(f'  {lab:28s} {t:10d} {t / len(test_p):8.1f} {raw / t:6.2f}×')
batch = sum(len(z0.compress(b'\\n'.join(test_p[s:s + 100]))) for s in range(0, len(test_p), 100)); print(f'  对照:每 100 条攒成一批、无字典 zstd-3:{batch} 字节(平均每条 {batch / len(test_p):.1f},{raw / batch:.2f}×)')
ok = all(zstandard.ZstdDecompressor(dict_data=dct).decompress(zd.compress(x)) == x for x in test_p[:200]); print(f'  解压校验(200 条):{"全部一致" if ok else "有不一致"}')
print('== 二:字典大小与训练样本数的影响(单条 products,zstd-3,2000 条测试集)')
print(f'  {"字典大小":>8s}' + ''.join(f'{"样本 " + str(n):>12s}' for n in (100, 500, 2000, 5000)))
for ds in (1024, 4096, 16384, 65536, 112640):
    row = ''
    for n in (100, 500, 2000, 5000):
        try: dd = train(train_p[:n], ds); row += f'{tot(zstandard.ZstdCompressor(level=3, dict_data=dd), test_p) / len(test_p):12.1f}'
        except Exception as e: row += f'{"(失败)":>12s}'
    print(f'  {ds / 1024:6.0f}KiB{row}   (平均每条字节)')
print('== 三:记录越大,字典的好处越小(各自用 1000–1500 条训练 16 KiB 字典,在另外 300–500 条上测)')
print(f'  {"记录类型":26s} {"平均大小":>8s} {"无字典":>8s} {"有字典":>8s} {"无字典压缩比":>11s} {"有字典压缩比":>11s}')
for lab, rs in (('timeseries 一行', recs_t), ('products 一条', recs_p), ('nested 一个文档', recs_n), ('pages 一页(13 KiB)', PG)):
    tr, te = (rs[:1000], rs[1000:1300]) if len(rs) <= 1500 else (rs[:1500], rs[1500:2000])
    try: dd = train(tr, 16384)
    except Exception as e: print(f'  {lab}:训练失败 {e}'); continue
    a = tot(z0, te); b = tot(zstandard.ZstdCompressor(level=3, dict_data=dd), te); r_ = sum(map(len, te))
    print(f'  {lab:26s} {r_ / len(te):8.0f} {a / len(te):8.1f} {b / len(te):8.1f} {r_ / a:10.2f}× {r_ / b:10.2f}×')
print('== 四:字典里是什么(products 的 16 KiB 字典)')
db = dct.as_bytes(); print(f'  字典共 {len(db)} 字节,字典 ID {dct.dict_id()};开头 4 字节魔数 {db[:4].hex()};后面先是熵编码的表(Huffman/FSE 表),最后是一段样本里常见的原始内容')
tail = db[-1500:]; txt = tail.decode('utf-8', 'replace'); print(f'  字典最后 300 字节(原始内容部分):{txt[-300:]!r}')
c = zd.compress(test_p[0]); fp = zstandard.get_frame_parameters(c); print(f'  用字典压缩的帧头里记录了字典 ID:{fp.dict_id}(与字典自己的 ID {dct.dict_id()} {"一致" if fp.dict_id == dct.dict_id() else "不一致"});无字典压缩的帧头 dict_id = {zstandard.get_frame_parameters(z0.compress(test_p[0])).dict_id}')
print('== 五:字典的泛化:用 products 训练的字典去压缩别的数据,以及字典太"旧"')
other = recs_t[:500]; own = zstandard.ZstdCompressor(level=3, dict_data=train(recs_t[500:2500], 16384))
print(f'  products 字典压 timeseries 一行:无字典 {tot(z0, other) / 500:.1f} 字节/条,products 字典 {tot(zd, other) / 500:.1f} 字节/条,自己的字典 {tot(own, other) / 500:.1f} 字节/条')
# 改变分布:换一套词表、增加字段
r = random.Random(99); voc2 = [''.join(r.choice('bcdfghjklmnprstvwz') + r.choice('aeiou') for _ in range(r.randint(2, 4))) for _ in range(1500)]
drift = [j(dict(x, title=' '.join(r.choice(voc2) for _ in range(r.randint(5, 12))), tags=[f'tag-{r.choice(voc2)}' for _ in range(3)], brand=r.choice(voc2), warehouse=f'W{r.randint(1, 50)}')) for x in P[5000:5500]]
print(f'  数据漂移(换了词表、新增 brand 和 warehouse 字段)的 products:无字典 {tot(z0, drift) / 500:.1f} 字节/条,旧字典 {tot(zd, drift) / 500:.1f} 字节/条;而同样字段不漂移的测试集:无字典 {tot(z0, test_p[:500]) / 500:.1f},旧字典 {tot(zd, test_p[:500]) / 500:.1f}')
drift_dict = zstandard.ZstdCompressor(level=3, dict_data=train(drift + [j(dict(x, brand='x', warehouse='W1')) for x in P[:100]], 16384)); print(f'  用漂移后的数据重新训练的字典(新数据 500 条 + 少量旧数据):漂移数据 {tot(drift_dict, drift) / 500:.1f} 字节/条')
print('== 六:字典的使用代价:压缩/解压速度,解压端必须有同一份字典')
for lab, cc in (('无字典', z0), ('16 KiB 字典', zd)):
    ts = timeit(lambda: [cc.compress(x) for x in test_p[:500]], 5)[0]; print(f'  {lab}:压缩 500 条单条记录 中位 {ts * 1000:.1f} ms(平均每条 {ts / 500 * 1e6:.0f} 微秒)', end='')
    cs = [cc.compress(x) for x in test_p[:500]]; dec = zstandard.ZstdDecompressor(dict_data=dct) if cc is zd else zstandard.ZstdDecompressor(); ts = timeit(lambda: [dec.decompress(c) for c in cs], 5)[0]; print(f';解压 500 条 中位 {ts * 1000:.1f} ms(平均每条 {ts / 500 * 1e6:.0f} 微秒)')
c = zd.compress(test_p[0])
for lab, dec in (('不带字典的解压器', zstandard.ZstdDecompressor()), ('带另一份字典的解压器', zstandard.ZstdDecompressor(dict_data=train(recs_t[:2000], 16384)))):
    try: dec.decompress(c); res = '成功'
    except Exception as e: res = f'失败:{type(e).__name__}: {str(e)[:70]}'
    print(f'  {lab}解压带字典的帧:{res}')
purge()
