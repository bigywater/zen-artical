import sys, os, lzma, subprocess, tempfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e14')
d = pdir('e14')
P = products(); PG = pages()
DATA = {'products JSON Lines': jl(P), 'pages(类 HTML)': b''.join(PG)[:8 << 20]}
def bench(comp, dec, data, reps):
    ct = []; 
    for _ in range(reps): t0 = time.perf_counter(); c = comp(data); ct.append(time.perf_counter() - t0)
    dt = []
    for _ in range(max(3, reps)): t0 = time.perf_counter(); r = dec(c); dt.append(time.perf_counter() - t0)
    assert r == data; ct.sort(); dt.sort(); mb = len(data) / 1048576
    return len(c), mb / ct[len(ct) // 2], mb / dt[len(dt) // 2]
print(f'== 一:zstd 各级别的压缩比与速度(zstandard {zstandard.__version__},libzstd {".".join(map(str, zstandard.backend_features and [zstandard.ZSTD_VERSION[0], zstandard.ZSTD_VERSION[1], zstandard.ZSTD_VERSION[2]]))};速度单位 MiB/s,按原始数据大小算)')
LV = (-5, -1, 1, 3, 5, 7, 9, 12, 15, 17, 19, 22)
res = {}
for nm, data in DATA.items():
    print(f'  --- {nm},{len(data) / 1048576:.1f} MiB ---'); print(f'  {"级别":>5s} {"压缩后":>9s} {"压缩比":>7s} {"压缩速度":>9s} {"解压速度":>9s}')
    for lv in LV:
        zc = zstandard.ZstdCompressor(level=lv); zd = zstandard.ZstdDecompressor()
        sz, cs, ds = bench(zc.compress, zd.decompress, data, 1 if lv >= 15 else 3); res[(nm, lv)] = (sz, cs, ds)
        print(f'  {lv:5d} {sz:9d} {len(data) / sz:6.2f}× {cs:8.1f} {ds:9.0f}')
print('== 二:每个级别在 zstd 内部对应的参数(zstandard 库的 ZstdCompressionParameters.from_level,数据大小未知时的取值)')
print(f'  {"级别":>5s} {"strategy":>9s} {"windowLog":>9s} {"chainLog":>8s} {"hashLog":>7s} {"searchLog":>9s} {"minMatch":>8s} {"targetLength":>12s}')
for lv in (1, 3, 5, 7, 9, 12, 15, 17, 19, 22):
    p = zstandard.ZstdCompressionParameters.from_level(lv)
    print(f'  {lv:5d} {p.strategy:9d} {p.window_log:9d} {p.chain_log:8d} {p.hash_log:7d} {p.search_log:9d} {p.min_match:8d} {p.target_length:12d}')
print('  (strategy 编号:1 fast、2 dfast、3 greedy、4 lazy、5 lazy2、6 btlazy2、7 btopt、8 btultra、9 btultra2——这个对应关系我是按 zstd 的头文件记忆写的,没有在本机核对)')
print('== 三:各压缩器的"压缩比—速度"位置(products JSON Lines,7.2 MB;速度 MiB/s)')
data = DATA['products JSON Lines']; rows = []
for lv in (1, 3, 9, 19):
    zc = zstandard.ZstdCompressor(level=lv); rows.append((f'zstd-{lv}',) + bench(zc.compress, zstandard.ZstdDecompressor().decompress, data, 1 if lv >= 15 else 3))
for lv in (1, 6, 9): rows.append((f'gzip(zlib)-{lv}',) + bench(lambda b, lv=lv: zlib.compress(b, lv), zlib.decompress, data, 3))
rows.append(('lz4 默认',) + bench(lz4.frame.compress, lz4.frame.decompress, data, 3))
for lv in (6, 12): rows.append((f'lz4 HC-{lv}',) + bench(lambda b, lv=lv: lz4.frame.compress(b, compression_level=lv), lz4.frame.decompress, data, 1 if lv >= 12 else 3))
rows.append(('snappy',) + bench(snappy.compress, snappy.decompress, data, 3))
for pr in (0, 6, 9): rows.append((f'xz 预设 {pr}',) + bench(lambda b, pr=pr: lzma.compress(b, preset=pr), lzma.decompress, data, 1))
for q in (1, 5, 9, 11):
    tmp = d / 'in'; tmp.write_bytes(data); t0 = time.perf_counter(); subprocess.run(['brotli', '-q', str(q), '-c', str(tmp)], stdout=open(d / 'out.br', 'wb'), check=True); ct = time.perf_counter() - t0
    t0 = time.perf_counter(); subprocess.run(['brotli', '-d', '-c', str(d / 'out.br')], stdout=subprocess.DEVNULL, check=True); dt = time.perf_counter() - t0
    rows.append((f'brotli -q{q}(命令行)', (d / 'out.br').stat().st_size, len(data) / 1048576 / ct, len(data) / 1048576 / dt))
print(f'  {"压缩器":22s} {"压缩后":>9s} {"压缩比":>7s} {"压缩速度":>9s} {"解压速度":>9s}')
for lab, sz, cs, ds in rows: print(f'  {lab:22s} {sz:9d} {len(data) / sz:6.2f}× {cs:8.1f} {ds:9.0f}')
print('  (brotli 命令行的速度包含启动进程和读写文件的时间,和库内调用不完全可比;xz 只测了 1 次)')
print('== 四:解压速度几乎不随压缩级别变化(同一个解压器,products;3 次中位数)')
for lv in (1, 3, 9, 19):
    sz, cs, ds = res[('products JSON Lines', lv)] if ('products JSON Lines', lv) in res else (0, 0, 0)
    print(f'  zstd-{lv}:压缩后 {sz} 字节,解压 {ds:.0f} MiB/s')
print('== 五:高级别的内存与窗口:在独立子进程里压缩 8 MiB 的 pages,再解压,看峰值内存(ru_maxrss)的增量')
import textwrap
CH = textwrap.dedent(f'''
    import sys, resource, zstandard
    sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__)) + '/..'!r}); import ec
    data = b''.join(ec.pages())[:8 << 20]; lv = int(sys.argv[1]); r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    c = zstandard.ZstdCompressor(level=lv).compress(data); r1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    open(sys.argv[2], 'wb').write(c); print((r1 - r0) / 1048576, len(c))
''')
CD = textwrap.dedent('''
    import sys, resource, zstandard
    c = open(sys.argv[1], 'rb').read(); r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out = zstandard.ZstdDecompressor().decompress(c); r1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print((r1 - r0) / 1048576, len(out))
''')
(d / 'c.py').write_text(CH); (d / 'd.py').write_text(CD)
for lv in (1, 3, 9, 15, 19, 22):
    p = zstandard.ZstdCompressionParameters.from_level(lv)
    a_ = subprocess.run([sys.executable, str(d / 'c.py'), str(lv), str(d / f'z{lv}')], capture_output=True, text=True).stdout.split(); b_ = subprocess.run([sys.executable, str(d / 'd.py'), str(d / f'z{lv}')], capture_output=True, text=True).stdout.split()
    print(f'  级别 {lv:2d}:窗口 2^{p.window_log} = {2 ** p.window_log / 1048576:.1f} MiB;压缩峰值内存增量 {float(a_[0]):6.1f} MiB(压缩后 {a_[1]} 字节);解压峰值内存增量 {float(b_[0]):5.1f} MiB')
print('  (这是对 8 MiB 输入的测量:输入比窗口小时,实际用到的内存可能比窗口小;输入的 8 MiB 和输出本身也计在内)')
print('== 六:多线程压缩(pages 全部 19.9 MiB;threads=0 单线程 与 threads=4)')
data = b''.join(PG)
for lv in (3, 10, 19):
    out = []
    for th in (0, 4):
        zc = zstandard.ZstdCompressor(level=lv, threads=th); t0 = time.perf_counter(); c = zc.compress(data); el = time.perf_counter() - t0; out.append((len(c), len(data) / 1048576 / el))
    print(f'  级别 {lv:2d}:threads=0 {out[0][0]} 字节、{out[0][1]:.1f} MiB/s;threads=4 {out[1][0]} 字节、{out[1][1]:.1f} MiB/s({out[1][1] / out[0][1]:.1f} 倍速度,体积{"+" if out[1][0] > out[0][0] else ""}{100 * (out[1][0] - out[0][0]) / out[0][0]:.2f}%)')
purge()
