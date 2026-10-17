from lib import *
import re
S = SS('u132')
R = J('u132')
c1 = re.search(r'读了同样 (\d+) 字节,底层 read 调用 (\d+) 次', R['calls']); unb = re.search(r'底层 read 调用 (\d+) 次(每个字节一次)', R['calls'])
caps = re.findall(r'with_capacity\(\s*(\d+)\):底层 read 调用\s+(\d+) 次', R['calls'])
bm = {k: float(v) for k, v in [('rts', re.search(r'read_to_string 一次读完再 lines\(\):\s+([\d.]+) ms', R['bench']).group(1)), ('lines', re.search(r'每行分配一个 String\):\s+([\d.]+) ms', R['bench']).group(1)), ('rl', re.search(r'复用同一个 String:\s+([\d.]+) ms', R['bench']).group(1)), ('rl1m', re.search(r'缓冲区 1 MiB:\s+([\d.]+) ms', R['bench']).group(1))]}
unb_full = float(re.search(r'折算整个文件约 (\d+) ms', R['bench']).group(1))
wh = re.search(r'File::read_to_string ([\d.]+) ms\s+BufReader::read_to_string ([\d.]+) ms', R['whole'])
steps = [
    step(f"数底层 read 调用(给 File 套一个计数的 Read 包装器):读 100000 字节的文件,无缓冲 File + bytes() 逐字节读,底层 read 调用 100001 次(每个字节一次);BufReader 默认容量 8192 字节,同样读完 {c1.group(1)} 字节只调用 {c1.group(2)} 次。每次 read 就是一次系统调用,这就是缓冲的价值。", t=tl(S(1)), done=lidx(S(1), '无缓冲 File', 'BufReader::new'), b=bars([['无缓冲', 100001, '100001 次'], ['BufReader 8 KiB', int(c1.group(2)), f'{c1.group(2)} 次']], 100001, cur=[0], done=[1]), kv=KV([['无缓冲', '100001 次 read'], ['BufReader 8192', f'{c1.group(2)} 次 read']], ['BufReader 8192'])),
    step("缓冲区容量决定调用次数,约等于文件大小 / 容量:with_capacity(64) 是 " + caps[0][1] + " 次,1024 是 " + caps[1][1] + " 次,65536 是 " + caps[2][1] + " 次。", t=tl(S(1)), done=lidx(S(1), 'with_capacity'), kv=KV([[f'容量 {c}', f'{n} 次 read'] for c, n in caps], [f'容量 {caps[-1][0]}'])),
    step(f"读 20 MB(100 万行)的文件,几种读法(release,取 3 次最小):read_to_string 一次读完再 lines() {bm['rts']:g} ms;BufReader::lines()(每行分配一个 String){bm['lines']:g} ms;BufReader + read_line 复用同一个 String {bm['rl']:g} ms;缓冲区放大到 1 MiB {bm['rl1m']:g} ms。把整个文件一次读进内存最快,复用 String 比 lines() 省近一半,而放大缓冲区几乎没有帮助。", t=tl(S(2)), done=lidx(S(2), 'read_to_string', 'BufReader::lines', 'read_line 复用', '1 MiB'), b=bars([['read_to_string', bm['rts'], f"{bm['rts']:g} ms"], ['read_line 复用', bm['rl'], f"{bm['rl']:g} ms"], ['lines()', bm['lines'], f"{bm['lines']:g} ms"]], bm['lines'], done=[0, 1, 2]), kv=KV([['一次读完', f"{bm['rts']:g} ms"], ['read_line 复用', f"{bm['rl']:g} ms"], ['lines()', f"{bm['lines']:g} ms"]], ['read_line 复用'])),
    step(f"无缓冲逐字节读慢得多:只读前 20 万字节(文件的 1%)就用了约 83 ms,按字节数折算整个 20 MB 约 {unb_full:.0f} ms,是一次读完的 {unb_full / bm['rts']:.0f} 倍(折算值,不是实测整个文件)。", t=tl(S(2)), mark=lidx(S(2), '无缓冲 File 逐字节读'), kv=KV([['无缓冲逐字节', f'折算约 {unb_full:.0f} ms'], ['一次读完', f"{bm['rts']:g} ms"]], ['无缓冲逐字节'])),
    step("BufRead 的底层接口:缓冲区容量设成 8,fill_buf() 看到 \"alpha\\nbe\"(8 字节)但还没消费;consume(3) 之后 buffer() 是 \"ha\\nbe\";read_until(b'\\n') 得到 \"ha\\n\"(包含分隔符)。lines() 把 \\n 与 \\r\\n 都去掉,最后一行没有换行也算一行:[\"alpha\", \"beta\", \"gamma\"]。", t=tl(S(3)), done=lidx(S(3), 'fill_buf', 'consume(3)', 'read_until', 'lines()'), kv=KV([['fill_buf', '看缓冲区,不消费'], ['consume(n)', '标记已用'], ['lines()', '去掉 \\\\n 和 \\\\r\\\\n']], ['fill_buf'])),
    step(f"一次读完整个文件时 BufReader 没有收益:4 MB 文件,File::read_to_string {wh.group(1)} ms,BufReader::read_to_string {wh.group(2)} ms,基本一样。缓冲对「很多次小读」有用,对「一次大读」没用。", t=tl(S(4)), done=lidx(S(4), 'File::read_to_string'), kv=KV([['File::read_to_string', f'{wh.group(1)} ms'], ['BufReader::read_to_string', f'{wh.group(2)} ms']], ['BufReader::read_to_string'])),
]
A = mkart('u132', 132, 'Rust,BufReader,缓冲IO,文件读取,真实验证,动画演示',
    f'用计数的 Read 包装器与真实文件验证 BufReader:逐字节读 10 万字节,无缓冲 100001 次 read 对 BufReader 8192 容量 {c1.group(2)} 次;调用数约等于文件大小/容量;20 MB 文件几种读法 {bm["rts"]:g}/{bm["rl"]:g}/{bm["lines"]:g} ms;一次读完整个文件时 BufReader 没有收益。',
    'BufReader 为什么能让读文件快几个数量级?默认缓冲多大?lines() 为什么比 read_line 慢?什么时候不需要它?这篇用 read 调用计数和 20 MB 文件的计时回答。',
    [('100001 对 ' + c1.group(2), '读 10 万字节:无缓冲与 BufReader 的底层 read 调用次数'), (f'{bm["lines"]:g} 对 {bm["rl"]:g} ms', 'lines() 与复用 String 的 read_line 读 100 万行的耗时'), ('8192', 'BufReader 的默认缓冲区容量(字节)')],
    [('read 调用次数', '<p>文件读写基础见<a href="rust-std-fs.html">std::fs 文件读写</a>;写入侧见<a href="rust-bufwriter.html">BufWriter 与批量写入</a>。</p>'), ('耗时对比', '<p>文件在系统缓存中(不是冷读),耗时是本机 release 实测的最小值;无缓冲整文件耗时是按前 20 万字节折算的。</p>'), ('BufRead 的底层接口', None), ('不需要 BufReader 的场景', None)],
    steps, [ENV_U + '。read 调用次数是在 Rust 层包装 File 统计的,不等同于内核里的系统调用统计(没有使用 dtruss/strace)', '没有验证:冷缓存(磁盘)读取、mmap 读取(见内存映射一篇)、大文件上缓冲区大小的最佳值、BufReader 与 Stdin::lock 的组合、异步文件读取'], 'BufReader')
