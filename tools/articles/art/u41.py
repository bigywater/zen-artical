import re
from lib import *
S = SS('u41')
v = [float(x) for x in re.findall(r'每个对象 ([\d.]+) ns', '\n'.join(S(1)))]
st, dsame, dalt, drand, en = v
steps = [
    step(f"100 万个对象、每种遍历 20 次取中位数(release):静态分发 Vec<Circle> 每个对象约 {st:.2f} ns;动态分发 Vec<Box<dyn Shape>> 全是 Circle 约 {dsame:.2f} ns —— 几乎没有差别;三种类型按 0,1,2 规律交替约 {dalt:.2f} ns;三种类型随机排列约 {drand:.2f} ns(间接调用的目标预测失败,慢了 {drand/st:.1f} 倍);enum 分发(match,可内联)约 {en:.2f} ns。", t=tl(S(1)), mark=lidx(S(1), '随机排列'), b=bars([['静态 Vec<Circle>', st, f'{st:.2f} ns'], ['dyn 全是 Circle', dsame, f'{dsame:.2f} ns'], ['dyn 规律交替', dalt, f'{dalt:.2f} ns'], ['dyn 随机排列', drand, f'{drand:.2f} ns'], ['enum match', en, f'{en:.2f} ns']], drand, mark=[3], done=[0, 1, 4]), kv=KV([['dyn 目标可预测', f'≈ 静态({dsame:.2f} vs {st:.2f} ns)'], ['dyn 目标随机', f'{drand:.2f} ns']], ['dyn 目标随机'])),
    step("汇编层面的差别:static_call(&Circle) 的函数体直接把 3.14159 * x * x 算出来(ldr、mov/movk 装常量、fmul、fmul、ret),调用方可以把它内联进去;dyn_call(&dyn Shape) 只有两条指令 ldr x1, [x1, #24] ; br x1 —— 从 vtable 偏移 24 处(drop、size、align 三个字之后的第一个方法槽)取出函数指针然后跳过去,编译器不知道目标是什么,所以不能内联、不能向量化。", t=tl(S(2)), mark=lidx(S(2), 'dyn_call'), kv=KV([['静态', '可内联、可向量化'], ['动态', 'ldr + br:一次间接跳转']], ['动态'])),
]
A = mkart('u41', 41, 'Rust,静态分发,动态分发,性能,真实验证,动画演示',
    f'用真实基准比较静态分发与动态分发:100 万对象每个约 {st:.2f} ns(静态)、{dsame:.2f} ns(dyn 全是同一类型)、{dalt:.2f} ns(规律交替)、{drand:.2f} ns(随机类型);enum 分发约 {en:.2f} ns;汇编上 dyn 调用是 ldr + br 一次间接跳转而静态调用可内联。',
    '「动态分发更慢」这句话对不对?这篇用同一个遍历循环做四种对照:全是同一种类型、规律交替、随机排列、改用 enum。结论是:动态分发的代价不在「查 vtable」本身,而在分支预测与无法内联 —— 目标可预测时几乎免费,不可预测时慢好几倍。',
    [(f'{drand/st:.1f} 倍', 'dyn 随机排列相对静态分发的每对象耗时'), (f'{dsame:.2f} vs {st:.2f} ns', 'dyn 全是同一种类型时与静态分发几乎一样'), ('ldr + br', 'dyn 调用在 aarch64 上的全部指令:取 vtable 槽、跳转')],
    [('四种遍历的耗时', '<p>基准用 <code>Instant</code> 计时、release 构建,每种配置取 20 次中位数;这个循环本身受内存访问影响很大,所以静态分发没有显著领先于全是同一类型的 dyn。数字只对这台机器与这个负载有意义。</p>'), ('汇编里的差别', '<p>对象怎么布局、胖指针里有什么,见<a href="rust-trait-object-dynamic-dispatch.html">Trait Object 与动态分发</a>;单态化的代码体积代价见<a href="rust-monomorphization.html">泛型单态化</a>。</p>')],
    steps, [ENV_U + '。release 构建,Apple 芯片;随机排列用固定种子的线性同余生成器', '没有验证:x86 上的间接分支预测表现、为何静态分发 Vec<Circle> 没有比 dyn 同类型更快(我猜是内存带宽受限,没有用性能计数器验证)、PGO 对 dyn 调用的去虚化(devirtualization)、对象很大时缓存未命中的影响'], '静态与动态分发')
