import sys, os, subprocess, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e1')
P = products(); T = timeseries(); N = nested(); B = blobby(); PG = pages()
def keys(o, acc):
    if isinstance(o, dict):
        for k, v in o.items(): acc.add(k); keys(v, acc)
    elif isinstance(o, list):
        for v in o: keys(v, acc)
    return acc
print('== 一:本系列用的五个合成数据集(固定随机种子,脚本生成,不是真实数据)')
print(f'  {"数据集":10s} {"记录数":>6s} {"JSON Lines 字节":>14s} {"平均每条":>8s} {"不同的键名数":>9s}  特点')
for nm, d, note in (('products', P, '爬虫抓到的商品记录:字符串多、字段名每条都重复'), ('timeseries', T, '数值密集:时间戳递增、数值随机游走'), ('nested', N, '嵌套 5 层、键名大量重复的配置式文档')):
    b = jl(d); print(f'  {nm:10s} {len(d):6d} {len(b):14d} {len(b) // len(d):8d} {len(keys(d, set())):9d}  {note}')
nb = sum(len(x['thumb']) for x in B); print(f'  {"blobby":10s} {len(B):6d} {"(含二进制)":>14s} {"":8s} {len(keys(B, set())):9d}  每条带 512 字节随机二进制缩略图(共 {nb / 1024:.0f} KiB,不可压缩)')
print(f'  {"pages":10s} {len(PG):6d} {sum(map(len, PG)):14d} {sum(map(len, PG)) // len(PG):8d} {"":9s}  类 HTML 页面文本,每页约 {sum(map(len, PG)) // len(PG) // 1024} KiB,用于纯压缩实验')
print('== 二:计时:同一个操作(json.dumps products 全部 2 万条)重复 9 次的最小/中位/最大;再对比机器上同时有 CPU 满载进程时')
fn = lambda: json.dumps(P)
t0 = time.perf_counter(); fn(); first = time.perf_counter() - t0
ts = sorted((lambda: (lambda t: (fn(), time.perf_counter() - t)[1])(time.perf_counter()))() for _ in range(9))
print(f'  CPU 核数 {os.cpu_count()};第一次 {first * 1000:.1f} ms;之后 9 次:最小 {ts[0] * 1000:.1f} / 中位 {ts[4] * 1000:.1f} / 最大 {ts[-1] * 1000:.1f} ms(最大是最小的 {ts[-1] / ts[0]:.2f} 倍)')
busy = [subprocess.Popen([sys.executable, '-c', 'while True: pass']) for _ in range(os.cpu_count())]
time.sleep(0.5)
ts2 = sorted((lambda: (lambda t: (fn(), time.perf_counter() - t)[1])(time.perf_counter()))() for _ in range(9))
for p in busy: p.kill(); p.wait()
print(f'  同时跑着 {len(busy)} 个空转进程:最小 {ts2[0] * 1000:.1f} / 中位 {ts2[4] * 1000:.1f} / 最大 {ts2[-1] * 1000:.1f} ms(中位是无负载时的 {ts2[4] / ts[4]:.2f} 倍,最大是最小的 {ts2[-1] / ts2[0]:.2f} 倍)')
print('== 三:同一个压缩结果,基准不同,"压缩比"差别很大(products 2 万条,zstd 级别 3)')
zs = lambda b, lv=3: len(zstandard.ZstdCompressor(level=lv).compress(b))
b_min = json.dumps(P, ensure_ascii=False, separators=(',', ':')).encode(); b_def = json.dumps(P, ensure_ascii=False).encode(); b_ind = json.dumps(P, ensure_ascii=False, indent=2).encode(); b_jl = jl(P)
rows = [('紧凑 JSON(无空格)', b_min), ('默认 json.dumps(逗号冒号后带空格)', b_def), ('indent=2 的 JSON', b_ind), ('JSON Lines(紧凑)', b_jl)]
print(f'  {"基准":30s} {"原始字节":>10s} {"zstd-3 后":>10s} {"原始/压缩后":>10s} {"压缩后/原始":>10s} {"省下":>6s}')
for lab, b in rows:
    z = zs(b); print(f'  {lab:30s} {len(b):10d} {z:10d} {len(b) / z:9.2f}× {z * 100 / len(b):9.1f}% {100 - z * 100 / len(b):5.1f}%')
print(f'  压缩后的字节数:紧凑 {zs(b_min)}、默认 {zs(b_def)}、indent=2 {zs(b_ind)}——相差不大,"压缩比"主要是被不同的基准拉开的')
print('== 四:一条条压缩与整批压缩(products,zstd 级别 3):每批 1、10、100、1000、全部 20000 条')
raw_total = sum(len(j(x)) for x in P)
for bs in (1, 10, 100, 1000, 20000):
    z = 0; cc = zstandard.ZstdCompressor(level=3)
    for s in range(0, len(P), bs): z += len(cc.compress(jl(P[s:s + bs])))
    print(f'  每批 {bs:5d} 条:共 {z:8d} 字节,压缩比 {raw_total / z:5.2f}×(原始 JSON 字节 {raw_total}),平均每条 {z / len(P):6.1f} 字节')
print('== 五:数据本身的重复程度决定压缩比(每种 1 MiB,gzip -6 / zstd -3 / lz4 默认)')
r = random.Random(9); N1 = 1 << 20
kinds = [('随机字节 randbytes', r.randbytes(N1)), ('随机小写字母', bytes(r.choice(b'abcdefghijklmnopqrstuvwxyz') for _ in range(N1))),
         ('词表里的词(4000 个词随机拼)', (' '.join(r.choice(VOC) for _ in range(N1 // 5)).encode())[:N1]), ('products 的 JSON Lines(截 1 MiB)', b_jl[:N1]),
         ('重复的 1 KiB 块', (r.randbytes(1024) * 1024)[:N1]), ('全零', bytes(N1))]
print(f'  {"内容":34s} {"gzip-6":>10s} {"zstd-3":>10s} {"lz4":>10s}   (压缩比 = 1 MiB / 压缩后)')
for lab, b in kinds:
    g = len(zlib.compress(b, 6)); z = zs(b); l = len(lz4.frame.compress(b)); print(f'  {lab:34s} {len(b) / g:9.2f}× {len(b) / z:9.2f}× {len(b) / l:9.2f}×')
print('== 六:可复现吗:同一份 products 数据,同一个级别,重复压缩的字节是否一样;多线程压缩的输出和单线程一样吗')
hs = {hashlib.sha256(zstandard.ZstdCompressor(level=3).compress(b_jl)).hexdigest()[:12] for _ in range(5)}
print(f'  单线程 zstd-3 压缩 5 次:不同的输出有 {len(hs)} 种({sorted(hs)})')
sz = {}
for th in (0, 2, 4):
    out = zstandard.ZstdCompressor(level=3, threads=th).compress(b_jl); sz[th] = (len(out), hashlib.sha256(out).hexdigest()[:12])
print(f'  threads=0/2/4 的输出:{sz};{"字节完全相同" if len({v[1] for v in sz.values()}) == 1 else "字节不同(体积也略有差别)"}')
tt = [timeit(lambda: zstandard.ZstdCompressor(level=3, threads=th).compress(b_jl), 5)[0] * 1000 for th in (0, 2, 4)]
print(f'  压缩 {len(b_jl) / 1048576:.1f} MiB 的中位耗时:threads=0 {tt[0]:.1f} ms、threads=2 {tt[1]:.1f} ms、threads=4 {tt[2]:.1f} ms')
big = b''.join(PG); res = {}
for th in (0, 4):
    t0 = time.perf_counter(); out = zstandard.ZstdCompressor(level=3, threads=th).compress(big); res[th] = (len(out), hashlib.sha256(out).hexdigest()[:12], (time.perf_counter() - t0) * 1000)
print(f'  换成 {len(big) / 1048576:.1f} MiB 的 pages 数据:threads=0 {res[0][0]} 字节({res[0][2]:.0f} ms)、threads=4 {res[4][0]} 字节({res[4][2]:.0f} ms);{"字节相同" if res[0][1] == res[4][1] else "字节不同"}')
purge()
