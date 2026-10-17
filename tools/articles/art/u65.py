from lib import *
import re
S = SS('u65')
R = J('u65')
m = re.search(r'flat_map 链 ([\d.]+) ms\s+双重 for ([\d.]+) ms\s+先对每行 sum 再 sum ([\d.]+) ms', R['bench']); fa, fb, fc = (float(m.group(i)) for i in (1, 2, 3))
steps = [
    step("[[1,2],[],[3,4,5]] 的三种展平写法结果相同 [1,2,3,4,5]:flat_map(|row| row.iter().copied())、map(...).flatten()、直接 iter().flatten().copied()。空的内层 Vec 不产出任何元素。", t=tl(S(1)), done=lidx(S(1), 'flat_map [1'), kv=KV([['flat_map(f)', '= map(f).flatten()']], ['flat_map(f)'])),
    step("展开嵌套数据:按行拆词得 [\"to\",\"be\",\"or\",\"not\",\"to\",\"be\"];字符串切成 char;Option 当作 0 或 1 个元素,[Some(1), None, Some(3)] 得 [1,3];一对多 (1..=3).flat_map(|n| 1..=n) 得 [1,1,2,1,2,3];笛卡尔积 [(1,'a'),(1,'b'),(2,'a'),(2,'b')]。", t=tl(S(1)), done=lidx(S(1), '按行拆词', '字符:', 'Option', '一对多', '笛卡尔积'), kv=KV([['Option', '0 或 1 个元素'], ['笛卡尔积', 'flat_map + map(move)']], ['笛卡尔积'])),
    step("内层闭包借用外层变量会报错:(1..=2).flat_map(|x| (1..=2).map(|y| (x, y))) 报 error[E0373]: closure may outlive the current function, but it borrows `x`;help 建议用 move。上一步的笛卡尔积写成 map(move |c| (x, c)) 就没问题。", t=tl(S(2)), mark=lidx(S(2), 'error[E0373]', 'move'), kv=KV([['内层闭包', '借用 x → E0373'], ['修复', 'move']], ['内层闭包'])),
    step("惰性:(1..=1000).flat_map(|n| 内层迭代器) 只取 take(7) = [0,0,1,0,1,2,0],内层迭代器只创建了 4 个(外层有 1000 个),内层元素共产出 7 个。后面的外层元素根本没有被展开。", t=tl(S(3)), done=lidx(S(3), 'take(7)', '创建了 4 个'), b=bars([['内层迭代器创建数', 4, '4 / 1000'], ['内层元素产出数', 7, '7']], 10, done=[0, 1]), kv=KV([['创建的内层迭代器', '4 / 1000'], ['产出元素', '7']], ['创建的内层迭代器'])),
    step("flatten 是双端的:[[1,2],[3],[4,5,6]] 上 rev 得 [6,5,4,3,2,1];size_hint 在展开前是 (0, None)(单层 iter 是 (3, Some(3))),因为不知道内层长度,这会影响 collect 的预分配;Result 也能 flatten,Err 被丢弃得 [1,3]。", t=tl(S(4)), done=lidx(S(4), 'rev', 'size_hint', 'Result 展开'), kv=KV([['flatten 的 size_hint', '(0, None)'], ['rev', '支持(双端)']], ['flatten 的 size_hint'])),
    step(f"1000×1000 的 Vec<Vec<u32>> 求和,release、取 5 次最小:flat_map 链 {fa:g} ms、双重 for {fb:g} ms、先对每行 sum 再 sum {fc:g} ms,结果相同。三种写法数量级相同,在这个例子里没有量到 flat_map 的额外开销。", t=tl(S(5)), done=lidx(S(5), 'flat_map 链'), b=bars([['flat_map 链', fa, f'{fa:g} ms'], ['双重 for', fb, f'{fb:g} ms'], ['先逐行 sum', fc, f'{fc:g} ms']], max(fa, fb, fc) * 1.2, done=[0, 1, 2]), kv=KV([['flat_map', f'{fa:g} ms'], ['双重 for', f'{fb:g} ms'], ['逐行 sum', f'{fc:g} ms']], ['flat_map'])),
]
A = mkart('u65', 65, 'Rust,Iterator,flat_map,flatten,真实验证,动画演示',
    f'用真实运行验证 flat_map:等价于 map + flatten,Option/Result 可当作 0 或 1 个元素展开;内层闭包借用外层变量报 E0373 要加 move;take(7) 只创建 4 个内层迭代器;flatten 的 size_hint 是 (0, None);100 万个元素展平求和 flat_map {fa:g} ms 对双重 for {fb:g} ms。',
    '嵌套数据怎么展开?flat_map 与 flatten 有什么区别?内层闭包为什么经常要加 move?它惰性到什么程度?这篇把二维数组、拆词、Option、笛卡尔积的展开和惰性计数、size_hint、性能一次跑清楚。',
    [('E0373', '内层闭包借用外层变量的错误'), ('4 / 1000', 'take(7) 时实际创建的内层迭代器数 / 外层元素数'), ('(0, None)', '展开前 flatten 的 size_hint')],
    [('展平与展开', '<p>惰性的基础见<a href="rust-iterator-lazy.html">Iterator 的惰性执行</a>。</p>'), ('内层闭包要 move', None), ('惰性', None), ('flatten 的类型细节', '<p>size_hint 对 collect 预分配的影响见<a href="rust-collect-inference.html">collect 类型推断</a>。</p>'), ('性能', '<p>数字是本机 release 实测;数据很小(1M 个 u32),不同形状(很多很短的内层)可能不同,没有测。</p>')],
    steps, [ENV_U + '。计时 release + black_box', '没有验证:很多极短内层迭代器的性能、flat_map 中返回 Vec(每次分配)与返回迭代器的差别、汇编层面是否与双重循环一致'], 'flat_map')
