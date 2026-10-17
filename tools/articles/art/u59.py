from lib import *
import re
S = SS('u59')
R = J('u59')
procs = R['procs']; ndist = len(set(procs))
caps = re.findall(r'第\s+(\d+) 个元素时 capacity =\s+(\d+)\s+累计 alloc (\d+) dealloc (\d+)', R['cap'])
resizes = len(caps) - 1
c5 = re.search(r'删 90 个:len (\d+) cap\(\) (\d+)', R['wc']); l5, cap5 = c5.group(1), c5.group(2)
zero = re.findall(r'n=\s*(\d+): 默认哈希\s+([\d.]+) ms\s+恒等于 0 的哈希\s+([\d.]+) ms', R['zero'])
z1, z4 = zero[0], zero[-1]; zr = round(float(z4[2]) / float(z1[2]), 1); nr = int(z4[0]) // int(z1[0])
steps = [
    step(f"默认 HashMap 的哈希带随机种子:同一个程序里,相同的 8 个键、相同的插入顺序,三个 map 的遍历顺序各不相同(第一个 map 的顺序)。再运行同一个程序 4 次,第一个 map 的顺序分别是 {'、'.join(procs)},共 {ndist} 种。所以不能依赖 HashMap 的遍历顺序。", t=tl(S(1)), done=lidx(S(1), 'map0', 'map1', 'map2', '再运行'), kv=KV([['4 次运行', f'{ndist} 种不同顺序']], ['4 次运行'])),
    step("用 BuildHasherDefault<DefaultHasher>(种子固定)时,两个 map 的遍历顺序完全相同;同一个 RandomState 对 \"hello\" 哈希两次值相同,另一个 RandomState 的值不同;DefaultHasher::new() 两次相同。随机性来自 RandomState 里的种子,不是哈希函数本身。", t=tl(S(2)), done=lidx(S(2), '固定种子', '同一个 RandomState', 'DefaultHasher::new()'), mark=lidx(S(2), '另一个 RandomState'), kv=KV([['固定种子', '顺序可复现'], ['RandomState', '每个实例不同种子']], ['RandomState'])),
    step(f"逐个 insert 1000 个 u64:第 1 个元素时 capacity 从 0 变 3,之后在第 {'、'.join(c[0] for c in caps[2:])} 个元素处扩容,capacity 依次 {' → '.join(c[1] for c in caps[1:])}(从 7 开始每次约翻倍)。每次扩容分配一块新表并释放旧表:一共 {resizes} 次变化,分配器累计 alloc {caps[-1][2]} 次、dealloc {caps[-1][3]} 次。", t=tl(S(3)), done=lidx(S(3), '第    1', '第    4', '第 1792', '897'), b=bars([[f'第 {c[0]} 个', int(c[1]), c[1]] for c in caps[1:]], int(caps[-1][1]), done=list(range(len(caps) - 1))), kv=KV([['capacity 序列', ' → '.join(c[1] for c in caps[1:])], ['alloc / dealloc', f'{caps[-1][2]} / {caps[-1][3]}']], ['capacity 序列'])),
    step("with_capacity(100) 得到 capacity 112(比请求的 100 大),只分配 1 次;之后插 100、101 个都不再分配。", t=tl(S(4)), done=lidx(S(4), 'with_capacity(100)', '插入 100 个后', '第 101 个后'), kv=KV([['with_capacity(100)', 'cap 112,alloc 1 次']], ['with_capacity(100)'])),
    step(f"删除不释放内存:另一个 map 插 100 个再删 90 个,len {l5}、capacity() 报 {cap5}(这个值每次运行可能不同),但删除期间 alloc 0、dealloc 0。shrink_to_fit 换成小块(cap() 14,alloc 1 dealloc 1);clear() 之后 cap() 仍是 14、没有 dealloc。", t=tl(S(4)), done=lidx(S(4), '删 90 个', 'shrink_to_fit', 'clear()'), kv=KV([['remove', '不释放内存'], ['shrink_to_fit', '换小块'], ['clear', '不释放']], ['shrink_to_fit'])),
    step("键必须同时实现 Hash 和 Eq:HashMap<f64, i32>::insert 报 error[E0599]: the method `insert` exists for struct `HashMap<f64, i32>`, but its trait bounds were not satisfied,note 列出 `f64: Eq` 和 `f64: Hash` 都不满足(浮点数有 NaN,不满足 Eq)。", t=tl(S(5)), mark=lidx(S(5), 'error[E0599]', 'f64: Eq', 'f64: Hash'), kv=KV([['f64 当键', 'E0599:缺 Eq 和 Hash']], ['f64 当键'])),
    step(f"哈希函数差会拖垮 HashMap:自定义 Hasher 让 finish() 恒返回 0,所有键落到同一个探测序列。n 从 {z1[0]} 增到 {z4[0]}(×{nr}),默认哈希 {z1[1]} ms → {z4[1]} ms,恒 0 哈希 {z1[2]} ms → {z4[2]} ms(约 ×{zr},增长快于线性)。", t=tl(S(5)), done=lidx(S(5), 'n='), b=bars([[f'n={n} 默认', float(a), f'{a} ms'] for n, a, b in zero] + [[f'n={n} 恒0', float(b), f'{b} ms'] for n, a, b in zero], float(z4[2]), cur=[4, 5, 6, 7]), kv=KV([['恒 0 哈希', f'{z1[2]} → {z4[2]} ms'], ['默认哈希', f'{z1[1]} → {z4[1]} ms']], ['恒 0 哈希'])),
]
A = mkart('u59', 59, 'Rust,HashMap,哈希,扩容,真实验证,动画演示',
    f'用真实运行验证 HashMap:默认哈希带随机种子,4 次运行得到 {ndist} 种遍历顺序,固定种子则可复现;逐个 insert 时 capacity 3→7→14→…→1792,每次扩容 alloc 一块新表并释放旧表;remove 不释放内存、shrink_to_fit 才缩;f64 不能当键;恒为 0 的哈希让插入从 {z1[2]} ms 涨到 {z4[2]} ms。',
    'HashMap 的遍历顺序为什么每次不同?容量是怎么长的?删光了内存还在吗?这篇用多次运行、分配器计数和自定义 Hasher 把默认哈希的随机种子、扩容序列、容量回收和哈希退化都真实跑了一遍。',
    [(f'{ndist}/4', '同一程序 4 次运行第一个 map 的遍历顺序有几种'), (f'{resizes} 次', '插入 1000 个 u64 过程中 capacity 变化次数(3 → 1792)'), (f'×{zr}', f'恒为 0 的哈希在 n 从 {z1[0]} 到 {z4[0]} 时耗时的增长倍数')],
    [('随机种子', None), ('固定种子与哈希值', None), ('扩容序列', '<p>Vec 的 2 倍扩容见<a href="rust-vec-growth.html">Vec 扩容机制</a>;HashMap 的 capacity 序列(3、7、14、28、……)是实测值,没有去读内部的桶数。</p>'), ('with_capacity 与删除', None), ('键的要求与哈希退化', '<p>BTreeMap 不依赖哈希,见<a href="rust-btreemap-vs-hashmap.html">BTreeMap 与 HashMap 对比</a>。</p>')],
    steps, [ENV_U + '。扩容与回收用 #[global_allocator] 计数,耗时用 release', '没有验证:SipHash 的具体算法与是否抗 HashDoS(只证明了种子随机)、hashbrown 内部的控制字节与 SIMD 探测、替换哈希器(FxHash、ahash)的性能(需要下载 crate)、表大小到容量的映射在其它版本是否一样'], 'HashMap')
