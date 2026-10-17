from lib import *
import re
S = SS('u61')
R = J('u61')
bn = re.findall(r'(HashSet collect|sort_unstable \+ dedup|BTreeSet collect)\s+([\d.]+) ms \(去重后 (\d+) 个\)', R['bench'])
th, ts, tb = (float(x[1]) for x in bn); nu = bn[0][2]
lens = R['bad']; cnt = len(set(lens))
steps = [
    step("insert 的返回值就是「是否新增」:HashSet 里 insert(3) → true、insert(5) → true,再 insert(3) → false,len 为 2;remove(&5) → true,remove(&9) → false(不存在)。", t=tl(S(1)), done=lidx(S(1), 'insert 3', 'remove 5'), kv=KV([['insert', '返回 bool:是否新增'], ['remove', '返回 bool:是否存在过']], ['insert'])),
    step("集合运算:a = {1,2,3,4},b = {3,4,5}:交 [3,4]、并 [1,2,3,4,5]、差 a-b [1,2]、对称差 [1,2,5];也可以用 &a | &b 与 &a & &b。HashSet 的相等与插入顺序无关:{1,2,3} == {3,2,1}。", t=tl(S(1)), done=lidx(S(1), '交 [', 'is_subset', '相等与顺序无关', '&a |'), kv=KV([['交', '[3, 4]'], ['并', '[1..5]'], ['对称差', '[1, 2, 5]']], ['交'])),
    step("对 [3,1,3,2,1,5,2] 去重:用 HashSet 记已见 + filter(|x| seen.insert(*x)) 保持首次出现顺序 [3,1,2,5];sort + dedup 和 BTreeSet 得到排序后的 [1,2,3,5];只调用 dedup 不排序得到原样 [3,1,3,2,1,5,2],因为 dedup 只去掉相邻的重复。", t=tl(S(2)), done=lidx(S(2), '保持首次', 'sort + dedup', 'BTreeSet'), mark=lidx(S(2), '只 dedup'), kv=KV([['保序去重', 'HashSet + filter'], ['排序去重', 'sort + dedup'], ['只 dedup', '只去相邻重复']], ['保序去重'])),
    step(f"100 万个元素(约 10 万种取值)去重,release、取 3 次最小:HashSet collect {th:g} ms、sort_unstable + dedup {ts:g} ms、BTreeSet collect {tb:g} ms,去重后都是 {nu} 个。三种差距不大。", t=tl(S(3)), done=lidx(S(3), 'HashSet collect', 'sort_unstable', 'BTreeSet collect'), b=bars([['HashSet collect', th, f'{th:g} ms'], ['sort_unstable + dedup', ts, f'{ts:g} ms'], ['BTreeSet collect', tb, f'{tb:g} ms']], max(th, ts, tb), done=[0, 1, 2]), kv=KV([['HashSet', f'{th:g} ms'], ['sort + dedup', f'{ts:g} ms'], ['BTreeSet', f'{tb:g} ms']], ['sort + dedup'])),
    step("自定义类型只用 id 判等和哈希:同 id 不同 name 的 User 再 insert 返回 false,集合里保留的仍是旧值 alice;只有 replace 才会替换,并返回旧值 Some(\"alice\"),之后里面是 \"ALICE\"。", t=tl(S(4)), done=lidx(S(4), 'false', 'replace'), kv=KV([['insert 同键', '不覆盖旧值'], ['replace', '替换并返回旧值']], ['replace'])),
    step(f"Eq 与 Hash 必须一致:让 eq 恒为 true、哈希却按内部值,20 个元素本该只剩 1 个。同一个程序运行 12 次,len 分别是 {lens},出现了 {cnt} 种结果,没有一次是 1,而且每次运行(随机种子)结果不同。", t=tl(S(4)), mark=lidx(S(4), '12 次'), kv=KV([['规则', 'a == b ⇒ hash(a) == hash(b)'], ['破坏后', f'12 次运行得到 {cnt} 种 len']], ['破坏后'])),
]
A = mkart('u61', 61, 'Rust,HashSet,BTreeSet,去重,真实验证,动画演示',
    f'用真实运行验证 HashSet 与去重:insert/remove 返回 bool、集合运算、保序去重与 sort+dedup 的区别(dedup 只去相邻重复);100 万元素去重三种方式 {th:g}/{ts:g}/{tb:g} ms;自定义类型 Eq 与 Hash 不一致时,12 次运行 len 得到 {cnt} 种结果。',
    'HashSet 看起来只是「没有值的 HashMap」,但 insert 的返回值、集合运算、保序去重、dedup 的陷阱和 Eq 与 Hash 的一致性都有细节。这篇每一点都用真实运行验证。',
    [('bool', 'insert 与 remove 的返回值:是否真的改变了集合'), (f'{cnt} 种', 'Eq 与 Hash 不一致时,12 次运行得到的不同结果数'), (f'{th:g} ms', '100 万个元素去重,HashSet collect 的耗时')],
    [('insert 与集合运算', '<p>HashMap 的细节见<a href="rust-hashmap-hash-resize.html">HashMap 的哈希与扩容</a>。</p>'), ('去重的写法', None), ('去重的速度', '<p>耗时是本机 release 实测,键是 xorshift 生成的 0..100000 随机数;换成字符串或更多重复率,排名可能不同。</p>'), ('自定义类型的 Eq 与 Hash', None)],
    steps, [ENV_U + '。计时 release + black_box', '没有验证:字符串元素的去重速度、HashSet::retain/drain 的行为、集合运算在大集合上的复杂度(只验证了结果)、Eq/Hash 不一致时在其它容量下的结果分布'], 'HashSet 去重')
