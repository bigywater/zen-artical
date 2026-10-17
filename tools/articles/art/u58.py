from lib import *
import re
S = SS('u58')
R = J('u58')
f = lambda pat, txt, g=1: re.search(pat, txt).group(g)
node = f(r'每次 (\d+) 字节', R['alloc']); tot_l = int(f(r'共申请 (\d+) 字节', R['alloc'])); tot_v = int(re.findall(r'共申请 (\d+) 字节', R['alloc'])[1])
il = float(f(r'LinkedList 最快 ([\d.]+) ms', R['iter'])); iv = float(f(r'Vec 最快 ([\d.]+) ms', R['iter'])); ir = round(il / iv, 1)
pb = re.findall(r'LinkedList\s+([\d.]+) ms\s+VecDeque\s+([\d.]+) ms', R['ends']); pl = min(float(a) for a, b in pb); pd = max(float(b) for a, b in pb)
ap_l = f(r'LinkedList::append (\S+)', R['ends']); ap_v = f(r'Vec::append (\S+)', R['ends'])
nth = re.findall(r'nth\(\s*(\d+)\) = \S+\s+用时 (\S+)', R['nth'])
steps = [
    step(f"存 1000 个 u64:LinkedList 要 alloc 1000 次,每次 {node} 字节(元素 8 字节 + 前后两个指针 16 字节),共申请 {tot_l} 字节;Vec 是 1 次 alloc + 8 次 realloc,扩容过程中所有申请加起来 {tot_v} 字节。", t=tl(S(1)), done=lidx(S(1), 'LinkedList<u64> 1000', 'Vec<u64>'), b=bars([['LinkedList 的 alloc 次数', 1000, '1000'], ['Vec 的 alloc + realloc 次数', 9, '9']], 1000, cur=[0], done=[1]), kv=KV([['LinkedList', f'每个元素一次分配,{node} 字节/节点'], ['Vec', '少量大块']], ['LinkedList'])),
    step(f"遍历求和 100 万个 u64(release,取 5 次最小):LinkedList 最快 {il:g} ms,Vec 最快 {iv:g} ms,约 {ir:g} 倍。注意这里的节点是连续分配的,已经接近链表缓存局部性的最好情形。", t=tl(S(2)), done=lidx(S(2), '遍历求和'), b=bars([['LinkedList 遍历', il, f'{il:g} ms'], ['Vec 遍历', iv, f'{iv:g} ms']], il, cur=[0], done=[1]), kv=KV([['遍历 100 万个', f'LinkedList {il:g} ms / Vec {iv:g} ms']], ['遍历 100 万个'])),
    step(f"连 push_back 也不占优:100 万次,LinkedList 最快 {pl:g} ms,VecDeque 最慢 {pd:g} ms。", t=tl(S(3)), done=lidx(S(3), 'push_back 100 万次'), b=bars([['LinkedList push_back', pl, f'{pl:g} ms'], ['VecDeque push_back', pd, f'{pd:g} ms']], pl, cur=[0], done=[1]), kv=KV([['push_back 100 万次', f'LinkedList ≥ {pl:g} ms / VecDeque ≤ {pd:g} ms']], ['push_back 100 万次'])),
    step(f"它真正的优势是拼接:两个 100 万元素的容器,LinkedList::append 用时 {ap_l},Vec::append 用时 {ap_v}。append 只改指针,不搬元素;split_off(2) 把 [0,1,2,3,4] 切成 [0,1] 与 [2,3,4]。", t=tl(S(3)), done=lidx(S(3), 'append'), kv=KV([['LinkedList::append', ap_l], ['Vec::append', ap_v]], ['LinkedList::append'])),
    step("没有下标访问:l[2] 报 error[E0608]: cannot index into a value of type `LinkedList<i32>`。", t=tl(S(4)), mark=lidx(S(4), 'error[E0608]'), kv=KV([['l[2]', 'E0608']], ['l[2]'])),
    step("要第 k 个只能 iter().nth(k) 从头走:" + ';'.join(f' nth({k}) 用时 {t}' for k, t in nth) + '。耗时随 k 线性增长。', t=tl(S(4)), done=lidx(S(4), 'nth('), b=bars([[f'nth({k})', float(re.sub(r'[^\d.]', '', t)) * (1 if 'µs' in t else 0.001 if 'ns' in t else 1000), t] for k, t in nth], 1000, done=[0, 1, 2, 3]), kv=KV([['随机访问', '只能从头走,O(k)']], ['随机访问'])),
]
A = mkart('u58', 58, 'Rust,LinkedList,数据结构,内存分配,真实验证,动画演示',
    f'用真实运行验证 LinkedList 为什么不是首选:1000 个 u64 要 1000 次 alloc,每节点 {node} 字节;遍历 100 万个元素 LinkedList {il:g} ms、Vec {iv:g} ms;push_back 也慢于 VecDeque;优势只有 append/split_off 拼接({ap_l} 对 {ap_v});没有下标,E0608。',
    '教科书里链表两端插入 O(1)、拼接 O(1),但在 Rust 里它很少是第一选择。这篇用分配器计数和 release 计时验证:每个元素一次堆分配、遍历慢几倍、连 push_back 也不占优,链表只赢在 append。',
    [('1000', '存 1000 个 u64 的 alloc 次数(Vec 只要 1 次 alloc 加 8 次 realloc)'), (f'{ir:g}×', '遍历 100 万个 u64,LinkedList 比 Vec 慢的倍数'), ('E0608', '对 LinkedList 使用下标')],
    [('每个元素一次分配', None), ('遍历', '<p>数字是本机 release 模式下的实测;节点在一个干净的堆上连续分配,真实程序里堆碎片化后链表通常更慢,但这一点没有测。</p>'), ('拼接才是优势', '<p>两端队列用 <a href="rust-vecdeque-ring-buffer.html">VecDeque 环形缓冲区</a>。</p>'), ('没有随机访问', None)],
    steps, [ENV_U + '。计时 release + black_box;分配用 #[global_allocator] 计数', '没有验证:堆碎片化之后链表的遍历性能、cursor API(在当前稳定版里没有用到)、LinkedList 的 Drop 在超长链表上的栈深度、在 split_off 之后做大量中间插入的场景'], 'LinkedList')
