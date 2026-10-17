from lib import *
import re
S = SS('u69')
R = J('u69')
sp = {k: (float(a), float(b)) for k, a, b in re.findall(r'^(\S+)\s+sort\s+([\d.]+) ms\s+sort_unstable\s+([\d.]+) ms', R['speed'], re.M)}
rs, ru = sp['随机']; ds, du = sp['大量重复']; os_, ou = sp['已有序']
first = re.search(r'sort 发生堆分配的元素个数.*?: Some\((\d+)\)', R['mem']).group(1)
big = re.search(r'n=\s*10000: sort 分配 (\d+) 次 (\d+) 字节', R['mem'])
kc = re.search(r'sort_by_key 的 key 函数被调用 (\d+) 次;sort_by_cached_key 调用 (\d+) 次', R['key']); k1, k2 = kc.group(1), kc.group(2)
bad = re.search(r'相邻两个 key 相同的元素 (\(\d+, \d+\)) 排在 (\(\d+, \d+\)) 前面', R['stab'])
steps = [
    step(f"200 个元素、只有 3 种 key:sort_by_key 保持了相同 key 的原来顺序(true),sort_unstable_by_key 没有(false)。一个真实的例子:{bad.group(1)} 排到了 {bad.group(2)} 前面,它们 key 相同而原始序号反了。两种排序的 key 序列本身相同,区别只在相同 key 内部的顺序。", t=tl(S(1)), mark=lidx(S(1), 'sort_unstable 打乱'), done=lidx(S(1), '200 个元素', 'key 序列相同'), kv=KV([['sort', '稳定'], ['sort_unstable', '不保证稳定']], ['sort_unstable'])),
    step(f"内存:sort_unstable 在所有规模下都不分配。sort 在小数组(10、20、100 个 u64)上也不分配,在 1..=5000 里从 {first} 个 u64 开始才出现堆分配;1 万个 u64 时分配 {big.group(1)} 次、{big.group(2)} 字节(正好是元素数据大小)。注:512 个 u64 恰好 4096 字节,但「小数组用栈上缓冲」是我的推测,没有读标准库源码验证。", t=tl(S(2)), done=lidx(S(2), 'n=    10:', 'n=   100:'), mark=lidx(S(2), '第一个让 sort', 'n= 10000'), b=bars([['sort 的分配字节(n=10000)', int(big.group(2)), f'{big.group(2)} B'], ['sort_unstable 的分配字节', 0, '0']], int(big.group(2)), cur=[0], done=[1]), kv=KV([['sort 开始分配', f'{first} 个 u64'], ['sort_unstable', '0 次']], ['sort 开始分配'])),
    step(f"速度(release,100 万个 u64,取 5 次最小):随机数据 sort {rs:g} ms,sort_unstable {ru:g} ms;只有 10 种值的大量重复 sort {ds:g} ms,sort_unstable {du:g} ms。已有序的输入两者都只要 {os_:g} ms 左右(几乎是一次线性扫描),逆序也很快。", t=tl(S(3)), done=lidx(S(3), '随机', '已有序', '逆序', '大量重复'), b=bars([['随机 sort', rs, f'{rs:g} ms'], ['随机 sort_unstable', ru, f'{ru:g} ms'], ['重复 sort', ds, f'{ds:g} ms'], ['重复 sort_unstable', du, f'{du:g} ms']], rs, done=[0, 1, 2, 3]), kv=KV([['随机', f'{rs:g} vs {ru:g} ms'], ['大量重复', f'{ds:g} vs {du:g} ms'], ['已有序', f'{os_:g} ms']], ['随机'])),
    step(f"key 函数的调用次数:1000 个元素,sort_by_key 的 key 闭包被调用 {k1} 次(每次比较都重新计算),sort_by_cached_key 只调用 {k2} 次(每个元素算一次后缓存),结果相同。key 计算很贵时(解析字符串、分配)应该用后者。", t=tl(S(4)), done=lidx(S(4), '1000 个元素'), b=bars([['sort_by_key', int(k1), k1], ['sort_by_cached_key', int(k2), k2]], int(k1), cur=[0], done=[1]), kv=KV([['sort_by_key', f'{k1} 次'], ['sort_by_cached_key', f'{k2} 次']], ['sort_by_cached_key'])),
    step("f64 没有 Ord:vec![2.5, 1.0].sort() 报 error[E0277]: the trait bound `{float}: Ord` is not satisfied,note 指出 sort 需要 T: Ord。", t=tl(S(5)), mark=lidx(S(5), 'error[E0277]'), kv=KV([['f64.sort()', 'E0277:没有 Ord']], ['f64.sort()'])),
    step("两个出路:sort_by(|a, b| a.total_cmp(b)) 能排含 NaN 与 -0.0 的数据,结果 [-1.0, -0.0, 0.0, 1.0, 2.5, NaN](-0.0 在 0.0 前,NaN 在最后);sort_by(partial_cmp.unwrap()) 对没有 NaN 的数据可用,遇到 NaN 会 panic(这次只测了无 NaN 的数据)。", t=tl(S(5)), done=lidx(S(5), 'total_cmp:', 'partial_cmp.unwrap()'), kv=KV([['total_cmp', '全序,含 NaN 与 -0.0'], ['partial_cmp.unwrap()', '有 NaN 会 panic(未测)']], ['total_cmp'])),
]
A = mkart('u69', 69, 'Rust,sort,sort_unstable,排序,真实验证,动画演示',
    f'用真实运行对比 sort 与 sort_unstable:稳定性(sort_unstable 真的打乱了相同 key 的顺序);分配(sort_unstable 不分配,sort 在 {first} 个 u64 起分配);100 万个随机 u64 sort {rs:g} ms 对 sort_unstable {ru:g} ms;sort_by_key 调用 {k1} 次 key 函数而 sort_by_cached_key 只调用 {k2} 次;f64 需用 total_cmp。',
    '稳定排序和不稳定排序的区别不只是「相同元素会不会换位置」。这篇用相同 key 的例子证明稳定性,用分配器计数看内存,用 100 万个元素测速度,再看 key 函数的调用次数和 f64 排序的出路。',
    [(f'{first} 个', 'sort 开始产生堆分配的 u64 元素个数'), (f'{k1} 对 {k2}', 'sort_by_key 与 sort_by_cached_key 的 key 函数调用次数(1000 个元素)'), ('E0277', 'f64 直接 sort')],
    [('稳定性', None), ('内存', None), ('速度', '<p>耗时是本机 release 实测,元素是 u64;更大的元素或昂贵的比较函数会改变结论。</p>'), ('sort_by_key 与缓存', None), ('浮点数排序', '<p>f64 没有 Ord 的原因与 NaN 有关,这里只验证了编译错误与 total_cmp 的输出。</p>')],
    steps, [ENV_U + '。计时 release + black_box,取最小值', '没有验证:sort 与 sort_unstable 的具体算法(没读源码)、元素很大时的差别、比较函数不满足全序时的行为(可能 panic)、partial_cmp 遇到 NaN 的 panic、select_nth_unstable'], 'sort 对 sort_unstable')
