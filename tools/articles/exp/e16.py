import sys, os, io, subprocess, textwrap; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e16')
d = pdir('e16')
P = products(); PG = pages()
def zc(level=3, **kw): return zstandard.ZstdCompressor(compression_params=zstandard.ZstdCompressionParameters.from_level(level, **kw))
rnd = random.Random(16)
BLOCK = b''.join(PG)[:1 << 20]                     # 1 MiB 的页面文本,会被重复一次
def make(gap_mib):
    """BLOCK + gap_mib MiB 不可压缩的随机填充 + 同一个 BLOCK:重复内容之间相隔 gap_mib MiB"""
    return BLOCK + rnd.randbytes(int(gap_mib * (1 << 20))) + BLOCK
print('== 一:重复的内容相隔多远,窗口就得多大才能找到(数据 = 1 MiB 页面文本 + N MiB 随机填充 + 同样的 1 MiB;zstd 级别 3,windowLog 取不同值)')
print(f'  1 MiB 页面文本单独压缩(级别 3):{len(zc().compress(BLOCK))} 字节;下面每个数据理想情况(第二份完全被匹配掉)约为 单份 + 填充')
WL = (17, 19, 20, 21, 22, 24, 27)
print(f'  {"填充":>8s} {"填充之外的字节":>12s}' + ''.join(f'{"wLog " + str(w):>11s}' for w in WL))
for gap in (0.0, 0.25, 1, 4, 16):
    data = make(gap); base = len(zc().compress(BLOCK)); row = ''
    for w in WL:
        sz = len(zc(3, window_log=w).compress(data)); row += f'{sz - int(gap * (1 << 20)):11d}'
    print(f'  {gap:6.2f}MiB {"(压缩后减去填充)":>12s}{row}')
print(f'  (表里的数字是 压缩后总字节 - 填充字节:约等于 {len(zc().compress(BLOCK))} 表示第二份被匹配掉了,约等于 {2 * len(zc().compress(BLOCK))} 表示第二份没有找到(重复压了一遍))')
print('== 二:长距离匹配(LDM)——不扩大主窗口,另建一个专门找远距离重复的结构(相隔 16 MiB 的重复,窗口 2^27)')
data = make(16)
for lab, kw in (('windowLog 27,不开 LDM', dict(window_log=27)), ('windowLog 27 + enable_ldm', dict(window_log=27, enable_ldm=True)), ('windowLog 20(1 MiB)+ enable_ldm', dict(window_log=20, enable_ldm=True))):
    for lv in (3,):
        c = zc(lv, **kw); t0 = time.perf_counter(); sz = len(c.compress(data)); el = time.perf_counter() - t0
        print(f'  级别 {lv},{lab:34s} → {sz} 字节({sz - 16 * (1 << 20)} 字节减去填充),{el * 1000:.0f} ms')
print('== 三:解压端的窗口限制:压缩时声明了很大的窗口(流式压缩、事先不知道总大小),解压端限制了窗口大小就会拒绝解压')
def stream_frame(data, wl, level=3):
    co = zc(level, window_log=wl).compressobj(); out = []
    for s in range(0, len(data), 1 << 20): out.append(co.compress(data[s:s + (1 << 20)]))
    out.append(co.flush()); return b''.join(out)
big = make(16); fr = {wl: stream_frame(big, wl) for wl in (22, 27, 28)}
for wl, f_ in fr.items(): print(f'  windowLog {wl} 流式压成 {len(f_)} 字节,帧头声明的窗口 {zstandard.get_frame_parameters(f_).window_size / 1048576:.0f} MiB')
for wl in (22, 27, 28):
    for lim in (1 << 22, 1 << 26, 1 << 27):
        try:
            with zstandard.ZstdDecompressor(max_window_size=lim).stream_reader(io.BytesIO(fr[wl])) as rd: n = 0
            res = '成功'
            dd = zstandard.ZstdDecompressor(max_window_size=lim).decompressobj(); out = dd.decompress(fr[wl]); res = f'成功,输出 {len(out)} 字节({"一致" if out == big else "不一致"})'
        except Exception as e: res = f'失败:{type(e).__name__}: {str(e)[:80]}'
        print(f'  帧 windowLog {wl},解压端 max_window_size = {lim / 1048576:.0f} MiB:{res}')
(d / 'w28.zst').write_bytes(fr[28]); (d / 'w22.zst').write_bytes(fr[22])
for nm, extra in (('windowLog 22 的帧', []), ('windowLog 28 的帧', [])):
    f_ = d / ('w22.zst' if '22' in nm else 'w28.zst')
    r = subprocess.run(['zstd', '-d', '-c', str(f_)], capture_output=True); print(f'  命令行 zstd -d:{nm}:退出码 {r.returncode},输出 {len(r.stdout)} 字节,stderr:{r.stderr.decode().strip()[:150]!r}')
r = subprocess.run(['zstd', '-d', '-c', '--long=28', str(d / 'w28.zst')], capture_output=True); print(f'  命令行 zstd -d --long=28:windowLog 28 的帧:退出码 {r.returncode},输出 {len(r.stdout)} 字节')
print('== 四:gzip 的窗口固定 32 KiB;zstd 的窗口可调——pages(每页约 13 KiB,页面之间有共同的模板和重复的词),前 8 MiB')
data = b''.join(PG)[:8 << 20]
print(f'  zlib-9(窗口 32 KiB):{len(zlib.compress(data, 9))} 字节(压缩比 {len(data) / len(zlib.compress(data, 9)):.2f}×)')
print(f'  {"zstd 级别":>9s}' + ''.join(f'{"wLog " + str(w):>11s}' for w in (15, 17, 20, 23)))
for lv in (3, 9, 19):
    print(f'  {lv:9d}' + ''.join(f'{len(zc(lv, window_log=w).compress(data)):11d}' for w in (15, 17, 20, 23)))
print('== 五:窗口大小与压缩/解压端的内存(独立子进程,pages 全部 19.9 MiB 用流式压缩成一个帧,zstd 级别 3;流式解压每次只取 64 KiB,ru_maxrss 增量)')
CH = textwrap.dedent(f'''
    import sys, io, resource, zstandard
    sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__)) + '/..'!r}); import ec
    data = b''.join(ec.pages()); wl = int(sys.argv[1]); r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    co = zstandard.ZstdCompressor(compression_params=zstandard.ZstdCompressionParameters.from_level(3, window_log=wl)).compressobj(); parts = []
    for s in range(0, len(data), 1 << 20): parts.append(co.compress(data[s:s + (1 << 20)]))
    parts.append(co.flush()); c = b''.join(parts); r1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    r2 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; n = 0
    with zstandard.ZstdDecompressor(max_window_size=1 << 30).stream_reader(io.BytesIO(c)) as rd:
        while True:
            x = rd.read(65536)
            if not x: break
            n += len(x)
    r3 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print((r1 - r0) / 1048576, (r3 - r2) / 1048576, len(c), n == len(data))
''')
(d / 'm.py').write_text(CH)
print(f'  {"windowLog":>9s} {"窗口":>8s} {"压缩后":>9s} {"压缩多用内存":>11s} {"流式解压多用内存":>14s}')
for wl in (15, 18, 21, 24, 27):
    o = subprocess.run([sys.executable, str(d / 'm.py'), str(wl)], capture_output=True, text=True).stdout.split(); print(f'  {wl:9d} {2 ** wl / 1048576:7.2f}M {o[2]:>9s} {float(o[0]):9.1f} MiB {float(o[1]):12.1f} MiB   解出长度{"一致" if o[3] == "True" else "不一致"}')
print('== 六:每个对象单独压缩,等于每次重置窗口:pages 8 MiB 切成不同大小的块各自压缩(zstd 级别 3,窗口足够大)')
print(f'  {"每块大小":>10s} {"块数":>6s} {"压缩后总字节":>12s} {"压缩比":>7s} {"比一整块大":>10s}')
whole = len(zc(3).compress(data))
for bs in (4096, 16384, 65536, 262144, 1 << 20, 8 << 20):
    tot = sum(len(zc(3).compress(data[s:s + bs])) for s in range(0, len(data), bs)); print(f'  {bs / 1024:8.0f}KiB {len(data) // bs:6d} {tot:12d} {len(data) / tot:6.2f}× {100 * (tot - whole) / whole:9.1f}%')
purge()
