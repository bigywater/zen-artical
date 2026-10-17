from lib import *
import re
S = SS('u57')
bn = [l for l in S(3) if 'Vec::insert' in l]
ms = [(float(re.search(r'insert\(0\)\s+([\d.]+) ms', l).group(1)), float(re.search(r'push_front\s+([\d.]+) ms', l).group(1))) for l in bn]
vi = min(m[0] for m in ms); vd = max(m[1] for m in ms); ratio = round(vi / vd)
steps = [
    step("VecDeque::with_capacity(8) 得 cap 8。push_back 1..=5 后 as_slices 是 ([1,2,3,4,5], []):数据在缓冲区里连续,第二段为空。", t=tl(S(1)), done=lidx(S(1), 'with_capacity', 'push_back 1..=5'), kv=KV([['as_slices', '(连续段, 空)']], ['as_slices'])),
    step("pop_front 两次后头部前移(数据 [3,4,5]),再 push_back 6..=9:逻辑上是 [3,4,5,6,7,8,9],as_slices 却是 ([3,4,5,6,7,8], [9]) —— 9 绕回了缓冲区开头,这就是环形缓冲区。push_front(0) 也不搬数据,只是头部再往前一格。", t=tl(S(1)), done=lidx(S(1), '再 push_back', 'push_front(0)'), mark=lidx(S(1), '绕回'), kv=KV([['逻辑顺序', '[3..9]'], ['物理存放', '两段:[3..8] + [9]']], ['物理存放'])),
    step("make_contiguous() 把数据整理成一段:之后 as_slices = ([0,3,4,5,6,7,8,9], [])。这是一次搬动,不是免费的。", t=tl(S(1)), done=lidx(S(1), 'make_contiguous', '之后 as_slices'), kv=KV([['make_contiguous', '整理成连续,有搬动成本']], ['make_contiguous'])),
    step("用元素地址对照缓冲区起点:cap 4 的 VecDeque,头部在槽位 2,逻辑下标 0、1 在物理槽位 2、3,逻辑下标 2、3(值 10、11)回到物理槽位 0、1。", t=tl(S(2)), done=lidx(S(2), '物理槽位 0', '物理槽位 1'), cells=None, kv=KV([['槽位 2、3', '逻辑 0、1'], ['槽位 0、1', '逻辑 2、3']], ['槽位 0、1'])),
    step(f"5 万次头部插入(release):Vec::insert(0) 每次要把全部元素后移,最快一次 {vi:g} ms;VecDeque::push_front 最慢一次 {vd:g} ms,相差约 {ratio} 倍以上。", t=tl(S(3)), b=bars([['Vec::insert(0)(最快一次)', vi, f'{vi:g} ms'], ['VecDeque::push_front(最慢一次)', vd, f'{vd:g} ms']], vi, cur=[0], done=[1]), kv=KV([['Vec::insert(0)', 'O(n) 每次'], ['push_front', 'O(1) 摊还']], ['push_front'])),
    step("VecDeque 支持下标和 get:d = [3,4,5,1,2] 时 d[0]=3、d[4]=2、get(9)=None。但 let sl: &[i32] = &d 报 error[E0308]: mismatched types,expected `&[i32]` found `&VecDeque<i32>`:它不是切片。", t=tl(S(4)), mark=lidx(S(4), 'error[E0308]'), done=lidx(S(4), 'd[0] = 3'), kv=KV([['d[i] / get', '支持'], ['&VecDeque → &[T]', 'E0308']], ['&VecDeque → &[T]'])),
    step("要切片就 make_contiguous():d.make_contiguous().sort() 后得 [1,2,3,4,5];VecDeque 与 Vec 可用 into() 互转,Vec → VecDeque 之后 as_slices 是单段 ([1,2,3,4,5], [])。", t=tl(S(4)), done=lidx(S(4), 'make_contiguous().sort()', 'VecDeque → Vec', 'Vec → VecDeque'), kv=KV([['排序', 'make_contiguous().sort()']], ['排序'])),
]
A = mkart('u57', 57, 'Rust,VecDeque,环形缓冲区,数据结构,真实验证,动画演示',
    f'用真实运行验证 VecDeque 的环形缓冲区:as_slices 暴露出逻辑连续的数据在物理上分成两段,元素地址证明回绕到槽位 0;make_contiguous 整理成一段;5 万次头部插入 Vec::insert(0) 最快 {vi:g} ms,VecDeque::push_front 最慢 {vd:g} ms;&VecDeque 不能当 &[T](E0308)。',
    'VecDeque 两端 O(1) 的秘密是环形缓冲区:头尾指针在固定缓冲区里绕圈,不搬数据。这篇用 as_slices 和元素地址直接看到「绕回」,并实测头部插入与 Vec 的差距,再看它为什么不能当切片用。',
    [('2 段', '回绕后 as_slices 返回的两段切片'), (f'{ratio}×+', '5 万次头部插入,Vec::insert(0) 最快一次对 VecDeque 最慢一次的倍数下限'), ('E0308', '&VecDeque 当 &[T] 用')],
    [('环形布局', None), ('用地址证明回绕', None), ('比 Vec 快多少', '<p>Vec 的扩容见<a href="rust-vec-growth.html">Vec 扩容机制</a>。这里的毫秒数是本机 release 模式的实测,绝对值因机器而异。</p>'), ('不是切片', None)],
    steps, [ENV_U + '。耗时用 release + black_box,每组测 3 次', '没有验证:VecDeque 扩容时搬动数据的具体做法、其它容量下的回绕、迭代与 Vec 迭代的速度差、内部 head/len 字段(不是公开 API,只用 as_slices 和元素地址间接观察)'], 'VecDeque')
