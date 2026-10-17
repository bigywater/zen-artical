from lib import *
import re
S = SS('u136')
R = J('u136')
rs = re.search(r'RSS 从 ([\d.]+) MB 变成 ([\d.]+) MB', R['lazy']); r2 = re.search(r'写了 2 个字节.*RSS = ([\d.]+) MB', R['lazy']); r3 = re.search(r'遍历全部 (\d+) 个页之后 RSS = ([\d.]+) MB', R['lazy'])
sq = [float(x) for x in re.findall(r'([\d.]+) ms\s+\(校验', R['seq'])]
rd = [float(x) for x in re.findall(r'([\d.]+) ms\s+\(校验', R['rand'])]; rr = round(rd[1] / rd[0])
sig = R['sigbus']
steps = [
    step("memmap2(从 crates.io 下载)把文件映射成内存:Mmap::map(&f) 之后当作 &[u8] 读,\"hello mmap world\" 的 [6..10] 是 \"mmap\"。用 MmapMut 修改前 5 字节并 flush,再用普通的 fs::read 读文件,得到 \"HELLO mmap world\" —— 通过内存写入,文件内容真的变了。", t=tl(S(1)), done=lidx(S(1), '映射 16 字节', 'MmapMut'), kv=KV([['Mmap', '只读视图'], ['MmapMut + flush', '改内存 = 改文件']], ['MmapMut + flush'])),
    step(f"映射是惰性的:对一个 1 GiB 的稀疏文件做 map_mut,进程 RSS 只是从 {rs.group(1)} MB 变成 {rs.group(2)} MB(映射本身不占物理内存);写 2 个字节(文件头和 500 MiB 处)后 RSS = {r2.group(1)} MB(只调入了 2 个页);每 4 KiB 读一个字节遍历全部 {r3.group(1)} 个页之后,RSS 涨到 {r3.group(2)} MB —— 内存是按页在第一次访问时才分配。", t=tl(S(2)), done=lidx(S(2), '映射 1 GiB', '写了 2 个字节'), mark=lidx(S(2), '遍历全部'), b=bars([['映射后', float(rs.group(2)), f'{rs.group(2)} MB'], ['写 2 字节后', float(r2.group(1)), f'{r2.group(1)} MB'], ['读遍所有页后', float(r3.group(2)), f'{r3.group(2)} MB']], float(r3.group(2)), done=[0, 1], cur=[2]), kv=KV([['映射后', f'{rs.group(2)} MB'], ['触碰 2 页', f'{r2.group(1)} MB'], ['读遍全部页', f'{r3.group(2)} MB']], ['触碰 2 页'])),
    step(f"顺序读 256 MiB 文件求和(页缓存已热,release,取 3 次最小):mmap 映射后直接遍历 {sq[0]:g} ms;read_to_end 读进 Vec 再遍历 {sq[1]:g} ms;1 MiB 缓冲循环读边读边算 {sq[2]:g} ms。mmap 省掉了一次拷贝,略快(约 {sq[1] / sq[0]:.1f} 倍于 read_to_end),但对「读一遍」这种场景优势不大,和分块读差别也小。", t=tl(S(3)), done=lidx(S(3), 'mmap 映射', 'read_to_end', '缓冲循环'), b=bars([['mmap', sq[0], f'{sq[0]:g} ms'], ['缓冲循环读', sq[2], f'{sq[2]:g} ms'], ['read_to_end', sq[1], f'{sq[1]:g} ms']], sq[1], done=[0, 1, 2]), kv=KV([['mmap', f'{sq[0]:g} ms'], ['缓冲循环', f'{sq[2]:g} ms'], ['read_to_end', f'{sq[1]:g} ms']], ['mmap'])),
    step(f"随机访问才是 mmap 的强项:在 256 MiB 文件里随机读 20 万个 8 字节(页缓存已热),mmap 切片下标 {rd[0]:g} ms,seek + read_exact 每次一对系统调用 {rd[1]:g} ms,约 {rr} 倍。结果校验值相同。", t=tl(S(4)), done=lidx(S(4), 'mmap 随机读', 'seek + read_exact'), b=bars([['mmap', rd[0], f'{rd[0]:g} ms'], ['seek + read', rd[1], f'{rd[1]:g} ms']], rd[1], cur=[1], done=[0]), kv=KV([['mmap', f'{rd[0]:g} ms'], ['seek + read_exact', f'{rd[1]:g} ms(约 {rr}×)']], ['mmap'])),
    step(f"代价:映射的文件被截断后,再访问被截掉的页会收到 SIGBUS。程序映射 64 KiB 文件,m[60000] = 7;另一个句柄把文件截到 4096 字节后,再读 m[60000],进程被信号 {-sig[0]}(SIGBUS)杀死,退出码 {sig[0]}。所以 Mmap::map 是 unsafe:Rust 没法保证别的进程不会改文件。", t=tl(S(5)), mark=lidx(S(5), '退出码', '截断'), kv=KV([['文件被截断后访问', f'SIGBUS(信号 {-sig[0]})'], ['Mmap::map', 'unsafe']], ['文件被截断后访问'])),
]
A = mkart('u136', 136, 'Rust,mmap,内存映射,memmap2,真实验证,动画演示',
    f'下载 memmap2 验证内存映射:读写与 flush;1 GiB 稀疏文件映射后 RSS 仅 {rs.group(2)} MB,读遍所有页后 {r3.group(2)} MB(按页惰性加载);256 MiB 顺序求和 mmap {sq[0]:g} ms 对 read_to_end {sq[1]:g} ms;20 万次随机读 mmap {rd[0]:g} ms 对 seek+read {rd[1]:g} ms(约 {rr}×);文件被截断后访问触发 SIGBUS。',
    'mmap 把文件当内存来读写,听起来很美。它到底惰性到什么程度?顺序读与随机读各快多少?为什么在 Rust 里它必须是 unsafe?这篇用 RSS 观察、计时和一次真实的 SIGBUS 回答。',
    [(f'{rs.group(2)} → {r3.group(2)} MB', '映射 1 GiB 文件后与读遍所有页后的进程 RSS'), (f'约 {rr}×', '随机读:mmap 对 seek + read_exact'), ('SIGBUS', '映射的文件被截断后访问被截掉的页的结果')],
    [('映射与读写', '<p>memmap2 0.9 从 crates.io 下载(需要联网)。普通文件读写见<a href="rust-std-fs.html">std::fs 文件读写</a>;缓冲读取见<a href="rust-bufreader.html">BufReader 与缓冲读取</a>。</p>'), ('惰性加载', '<p>RSS 通过 ps 读取,是系统报告值。</p>'), ('顺序读', '<p>页缓存已热,没有测冷读。注意:基准里每一轮的结果都要 black_box,否则优化器会删掉没人用的求和,取多轮最小值时会选中被删掉的那一轮,得到接近 0 的耗时(见 Benchmark 一篇)。</p>'), ('随机读', None), ('SIGBUS', '<p>unsafe 的含义见<a href="rust-unsafe-boundary.html">unsafe 的安全边界</a>。</p>')],
    steps, [ENV_U + '。memmap2 0.9;计时 release', '没有验证:冷页缓存下的读取、madvise / MAP_POPULATE、大文件写入时的脏页回写性能、Linux 上的 RSS 与 SIGBUS 信号编号、Windows 的映射语义、mmap 与 O_DIRECT 的比较'], 'mmap')
