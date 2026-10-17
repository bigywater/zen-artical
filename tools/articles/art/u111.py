from lib import *
import re
S = SS('u111')
R = J('u111'); A1 = R['asm']; A2 = R['asm2']
d = re.search(r'fold:\s+([\d.]+) ms\s+裸 f64 \+ for 循环:\s+([\d.]+) ms', R['dr_dbg']); r_ = re.search(r'fold:\s+([\d.]+) ms\s+裸 f64 \+ for 循环:\s+([\d.]+) ms', R['dr_rel'])
same = [k for k, v in A1.items() if v[0]]; diff = [k for k, v in A1.items() if not v[0]]
def row(k, v): return [k, f"{v[1]} / {v[2]} 条,{'逐行相同' if v[0] else '不同'}"]
steps = [
    step(f"Rust 的「零开销抽象」:把高层写法与手写底层写法分别编译(-O,aarch64),比较汇编。{len(same)} 组逐行相同:" + '、'.join(same) + "。例如 Newtype 包装 Meters(f64) 的加法与直接加 f64 都是 2 条指令;Option<&u32> 的 match 与裸指针判空都是 3 条;泛型 max<i32> 与具体写法 3 条;闭包调用与直接计算 3 条。", t=tl(S(1)), done=lidx(S(1), 'Newtype', 'Option<&T>', '泛型 max', '闭包调用'), kv=KV([[k, f"{A1[k][1]} 条 = {A1[k][2]} 条"] for k in same[:4]], [same[0]])),
    step(f"并非每一组都逐行相同,但差别很小:iter().sum() 与 for 循环是 {A1['iter().sum() vs for 循环'][1]} 对 {A1['iter().sum() vs for 循环'][2]} 条(都向量化了循环,指令排布略有不同);map().sum() 与手写累加都是 {A1['map().sum() vs 手写累加'][1]} 条但不是逐行相同;&dyn Fn 与 fn 指针调用都是 3 条,措辞略不同。「零开销」指的是不多付出可观的运行时代价,不等于机器码一字不差。", t=tl(S(1)), mark=lidx(S(1), 'iter().sum()', 'map().sum()', '&dyn Fn'), kv=KV([[k, f"{v[1]} / {v[2]} 条"] for k, v in A1.items() if not v[0]], ['iter().sum() vs for 循环'])),
    step(f"有些抽象是有开销的 —— 这些开销来自安全检查,而不是抽象本身:v[i](带边界检查)是 {A2['下标访问 v[i](有边界检查)'][0]} 条指令,get_unchecked 只要 {A2['下标访问 v[i](有边界检查)'][1]} 条;checked_add {A2['checked_add vs 回绕加'][0]} 条,wrapping_add {A2['checked_add vs 回绕加'][1]} 条;Rc 克隆 {A2['Rc 克隆 vs 复制 u32'][0]} 条(要增加计数),复制 u32 {A2['Rc 克隆 vs 复制 u32'][1]} 条。你为安全性、共享所有权付出的是你明确要求的那部分。", t=tl(S(2)), done=lidx(S(2), '下标访问', 'checked_add', 'Rc 克隆'), b=bars([[k.split('(')[0].split(' ')[0] + ' 带检查', v[0], f'{v[0]} 条'] for k, v in A2.items()], 12, done=[0, 1, 2]), kv=KV([[k, f'{v[0]} vs {v[1]} 条'] for k, v in A2.items()], [list(A2)[0]])),
    step(f"零开销依赖优化:同样的 Newtype(Meters 实现 Add)+ 迭代器 fold 与裸 f64 + for 循环,500 万个元素:release 构建 {r_.group(1)} ms 对 {r_.group(2)} ms,几乎相同;debug 构建 {d.group(1)} ms 对 {d.group(2)} ms,抽象的多层函数调用没被内联,差了约 {float(d.group(1)) / float(d.group(2)):.1f} 倍。", t=tl(S(3)), done=lidx(S(3), 'release', 'debug'), b=bars([['debug 抽象', float(d.group(1)), f'{d.group(1)} ms'], ['debug 手写', float(d.group(2)), f'{d.group(2)} ms'], ['release 抽象', float(r_.group(1)), f'{r_.group(1)} ms'], ['release 手写', float(r_.group(2)), f'{r_.group(2)} ms']], float(d.group(1)), done=[0, 1, 2, 3]), kv=KV([['release', f'{r_.group(1)} vs {r_.group(2)} ms'], ['debug', f'{d.group(1)} vs {d.group(2)} ms']], ['release'])),
]
A = mkart('u111', 111, 'Rust,零开销抽象,汇编,优化,真实验证,动画演示',
    f'用 aarch64 汇编对比验证零开销抽象:{len(same)} 组高层写法与手写逐行相同(Newtype、Option<&T>、泛型、闭包),迭代器链差别很小;带来开销的是边界检查(11 条对 2 条)、checked_add、Rc 计数这类明确要求的安全;debug 构建里抽象不被内联,耗时 {d.group(1)} 对 {d.group(2)} ms。',
    '“零开销抽象”常被当口号。这篇给它做实验:把 7 组高层写法与手写底层写法编译成汇编逐行比较,再看真正有开销的抽象是哪些,以及优化关闭时这个说法还成不成立。',
    [(f'{len(same)} / {len(A1)}', '高层写法与手写汇编逐行相同的组数'), ('11 对 2 条', 'v[i] 带边界检查与 get_unchecked 的指令数'), (f'{float(d.group(1)) / float(d.group(2)):.1f}×', 'debug 构建里 Newtype + 迭代器比裸写慢的倍数(release 里约 1×)')],
    [('抽象与手写', '<p>迭代器链的汇编见<a href="rust-iterator-chain-performance.html">Iterator 链的性能</a>;泛型单态化见<a href="rust-monomorphization.html">泛型单态化</a>。</p>'), ('开销来自哪里', None), ('debug 构建', '<p>汇编指令数来自 aarch64 的 -O 输出,换平台数字会不同;耗时为本机单次微基准。</p>')],
    steps, [ENV_U + '。汇编用 rustc --emit=asm -O,规范化局部标签后比较', '没有验证:x86_64 汇编、LTO 与 PGO 对结论的影响、更大的程序里内联预算耗尽时的行为、Box<dyn Trait> 的虚调用相对静态分发的实际耗时(见静态分发与动态分发一篇)'], '零开销抽象')
