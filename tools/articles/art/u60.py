from lib import *
import re
S = SS('u60')
R = J('u60')
bn = re.findall(r'n=\s*(\d+): 插入 HashMap\s+([\d.]+) ms / BTreeMap\s+([\d.]+) ms\s+查找 HashMap\s+([\d.]+) ms / BTreeMap\s+([\d.]+) ms', R['bench'])
n3 = bn[-1]; ri = round(float(n3[2]) / float(n3[1]), 1); rl = round(float(n3[4]) / float(n3[3]), 1)
rg = re.search(r'range 找到 (\d+) 个,用时 (\S+)', R['range']); fl = re.search(r'全表过滤 找到 (\d+) 个,用时 (\S+)', R['range'])
def ms(t): return float(re.sub(r'[^\d.]', '', t)) * (1e-3 if 'µs' in t else 1e-6 if 'ns' in t else 1)  # → ms
rgm, flm = ms(rg.group(2)), ms(fl.group(2)); rr = round(flm / rgm)
ab = re.search(r'BTreeMap<u64,u64> 1000 个:alloc (\d+) 次,最大单次 (\d+)', R['alloc']); ah = re.search(r'HashMap<u64,u64>\s+1000 个:alloc (\d+) 次,最大单次 (\d+)', R['alloc'])
steps = [
    step("BTreeMap 的遍历天然有序:乱序插入 50、20、80、10、60、30、90、40、70 后,keys() 得 [10,20,30,40,50,60,70,80,90]。", t=tl(S(1)), done=lidx(S(1), '遍历'), kv=KV([['遍历', '按键排序']], ['遍历'])),
    step("范围查询:range(30..=60) 得 [30,40,50,60],range(..30) 得 [10,20],range(75..) 得 [80,90];first_key_value、last_key_value、pop_first、pop_last 都是对数时间的有序操作;range(..=45).next_back() 取「小于等于 45 的最大键」得 40。", t=tl(S(1)), done=lidx(S(1), 'range(30..=60)', 'range(..30)', 'first_key_value', 'pop_first', '小于等于 45'), kv=KV([['range', '有序范围'], ['next_back', '前驱查询']], ['range'])),
    step("HashMap 没有 range:m.range(1..5) 报 error[E0599]: no method named `range` found for struct `HashMap<K, V, S, A>`。", t=tl(S(2)), mark=lidx(S(2), 'error[E0599]'), kv=KV([['HashMap.range', 'E0599']], ['HashMap.range'])),
    step("键的要求不同:自定义 P 只实现了 PartialEq、Eq、Hash,放进 HashMap 没问题,放进 BTreeMap 报 error[E0277]: the trait bound `P: Ord` is not satisfied,help 建议 #[derive(Ord)]。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]', 'P: Ord'), kv=KV([['HashMap', 'Hash + Eq'], ['BTreeMap', 'Ord']], ['BTreeMap'])),
    step("顺序由键的 Ord 决定:给 Rev 实现反序的 cmp,BTreeMap 的遍历就是 [Rev(3), Rev(2), Rev(1)]。", t=tl(S(3)), done=lidx(S(3), '自定义 Ord'), kv=KV([['顺序', '来自 Ord::cmp']], ['顺序'])),
    step(f"随机 u64 键,release、取 3 次最小。n = {bn[-1][0]} 时插入:HashMap {n3[1]} ms,BTreeMap {n3[2]} ms(约 {ri} 倍);查找:HashMap {n3[3]} ms,BTreeMap {n3[4]} ms(约 {rl} 倍)。n = 1000 与 100000 时同样 HashMap 更快。", t=tl(S(4)), done=lidx(S(4), 'n='), b=bars([['插入 HashMap', float(n3[1]), f'{n3[1]} ms'], ['插入 BTreeMap', float(n3[2]), f'{n3[2]} ms'], ['查找 HashMap', float(n3[3]), f'{n3[3]} ms'], ['查找 BTreeMap', float(n3[4]), f'{n3[4]} ms']], float(n3[2]), cur=[1, 3], done=[0, 2]), kv=KV([['插入', f'BTreeMap 约慢 {ri}×'], ['查找', f'BTreeMap 约慢 {rl}×']], ['插入'])),
    step(f"但范围查询反过来:100 万个键里取 [3500000, 3501000),BTreeMap::range 找到 {rg.group(1)} 个,用时 {rg.group(2)};HashMap 只能全表过滤,同样找到 {fl.group(1)} 个,用时 {fl.group(2)}(约 {rr} 倍)。", t=tl(S(5)), done=lidx(S(5), 'BTreeMap::range', 'HashMap 全表'), b=bars([['BTreeMap::range', rgm, rg.group(2)], ['HashMap 全表过滤', flm, fl.group(2)]], flm, cur=[0], done=[1]), kv=KV([['范围查询', f'BTreeMap 快约 {rr}×']], ['范围查询'])),
    step(f"内存分配形态不同:1000 个 u64 键值对,BTreeMap 做了 {ab.group(1)} 次小分配(最大一次 {ab.group(2)} 字节,一个节点);HashMap 只做了 {ah.group(1)} 次(最大一次 {ah.group(2)} 字节,整张表)。", t=tl(S(6)), done=lidx(S(6), 'BTreeMap<', 'HashMap<'), b=bars([['BTreeMap alloc 次数', int(ab.group(1)), ab.group(1)], ['HashMap alloc 次数', int(ah.group(1)), ah.group(1)]], int(ab.group(1)), cur=[0], done=[1]), kv=KV([['BTreeMap', f'{ab.group(1)} 次,每次一个节点'], ['HashMap', f'{ah.group(1)} 次,每次整表']], ['BTreeMap'])),
]
A = mkart('u60', 60, 'Rust,BTreeMap,HashMap,有序,真实验证,动画演示',
    f'用真实运行对比 BTreeMap 与 HashMap:BTreeMap 遍历有序、支持 range 与前驱查询,键要 Ord;HashMap 没有 range。100 万个随机 u64 键,插入 HashMap {n3[1]} ms 对 BTreeMap {n3[2]} ms,查找 {n3[3]} ms 对 {n3[4]} ms;范围查询 BTreeMap {rg.group(2)} 对 HashMap 全表过滤 {fl.group(2)}。',
    '选 BTreeMap 还是 HashMap,取决于要不要「有序」。这篇不讲抽象的 O(log n) 与 O(1),而是把有序遍历、范围查询、键的 trait 要求、插入与查找耗时、范围查询耗时和分配形态都真实跑了出来。',
    [(f'{ri}×', f'100 万个随机键插入:BTreeMap 比 HashMap 慢的倍数'), (f'{rr}×', '范围查询:HashMap 全表过滤比 BTreeMap::range 慢的倍数'), (f'{ab.group(1)} 对 {ah.group(1)}', '存 1000 个键值对的 alloc 次数(BTreeMap 对 HashMap)')],
    [('有序遍历与范围', None), ('HashMap 没有 range', '<p>HashMap 的哈希与扩容见<a href="rust-hashmap-hash-resize.html">HashMap 的哈希与扩容</a>。</p>'), ('键的要求', None), ('插入与查找的速度', '<p>耗时是本机 release 模式的实测(取 3 次最小),键为 xorshift 生成的随机 u64;键类型、值大小或机器不同,倍数会变。</p>'), ('范围查询', None), ('分配形态', None)],
    steps, [ENV_U + '。计时 release + black_box', '没有验证:字符串键下的对比、顺序插入(升序键)时的 BTreeMap 速度、并发场景、BTreeMap 节点的具体容量(只看到单次最大分配大小)、其它哈希器(需要下载 crate)'], 'BTreeMap 对 HashMap')
