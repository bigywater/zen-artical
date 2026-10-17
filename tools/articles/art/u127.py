from lib import *
import re
S = SS('u127')
R = J('u127'); P = R['prof']; V = R['var']; ov = R['ovf_dev'], R['ovf_release']
def tm(prof): return [float(x) for x in re.findall(r'([\d.]+) ms', P[prof]['out'])]
td, tr = tm('dev'), tm('release')
sp = [round(a / b, 1) for a, b in zip(td, tr)]
steps = [
    step(f"同一个程序(collatz 最长链、HashMap 50 万次更新、100 万个数排序)分别用 cargo build(dev)与 cargo build --release 编译运行。dev:collatz {td[0]:g} ms、HashMap {td[1]:g} ms、排序 {td[2]:g} ms;release:{tr[0]:g} ms、{tr[1]:g} ms、{tr[2]:g} ms,分别快 {sp[0]}、{sp[1]}、{sp[2]} 倍。结果校验值完全相同。差别最大的是依赖大量泛型与迭代器抽象的排序和哈希表。", t=tl(S(1)), done=lidx(S(1), 'dev', 'release'), b=bars([['dev 排序', td[2], f'{td[2]:g} ms'], ['release 排序', tr[2], f'{tr[2]:g} ms'], ['dev HashMap', td[1], f'{td[1]:g} ms'], ['release HashMap', tr[1], f'{tr[1]:g} ms']], td[2], done=[0, 1, 2, 3]), kv=KV([['collatz', f'{sp[0]}× 快'], ['HashMap', f'{sp[1]}× 快'], ['排序', f'{sp[2]}× 快']], ['排序'])),
    step(f"程序里用 cfg!(debug_assertions) 打印:dev 里是 true,release 里是 false。二进制大小:dev {P['dev']['size']:,} 字节,release {P['release']['size']:,} 字节(这个小程序里 release 更小,但 dev 带有更多调试信息与未优化的代码)。本机上编译时间都不到 1 秒,差别可以忽略,没有测大型项目。", t=tl(S(1)), done=lidx(S(1), 'debug_assertions'), kv=KV([['dev 二进制', f"{P['dev']['size']:,} 字节"], ['release 二进制', f"{P['release']['size']:,} 字节"]], ['release 二进制'])),
    step(f"哪个开关决定速度?只把 dev 的 opt-level 改成 3:collatz {V['dev + opt-level=3'][0]:g} ms、HashMap {V['dev + opt-level=3'][1]:g} ms、排序 {V['dev + opt-level=3'][2]:g} ms,基本追平 release({V['release(默认)'][0]:g} / {V['release(默认)'][1]:g} / {V['release(默认)'][2]:g} ms),而此时 debug_assertions 与溢出检查仍然是开的。可见 dev 慢的主要原因是 opt-level=0,不是这些检查。", t=tl(S(2)), done=lidx(S(2), 'dev + opt-level=3', 'release(默认)'), kv=KV([['dev 默认', f"{V['dev(默认)'][2]:g} ms(排序)"], ['dev + opt-level=3', f"{V['dev + opt-level=3'][2]:g} ms"], ['release', f"{V['release(默认)'][2]:g} ms"]], ['dev + opt-level=3'])),
    step(f"反过来给 release 开检查:加 overflow-checks = true 后 collatz 从 {V['release(默认)'][0]:g} ms 变成 {V['release + overflow-checks'][0]:g} ms(这个循环全是加乘,检查有可见成本);加 debug-assertions = true 后排序从 {V['release(默认)'][2]:g} ms 变成 {V['release + debug-assertions'][2]:g} ms(标准库里的 debug_assert 被打开了)。两个开关的代价都因程序而异。", t=tl(S(2)), mark=lidx(S(2), 'release + overflow-checks', 'release + debug-assertions'), kv=KV([['+ overflow-checks', f"collatz {V['release + overflow-checks'][0]:g} ms"], ['+ debug-assertions', f"排序 {V['release + debug-assertions'][2]:g} ms"]], ['+ debug-assertions'])),
    step("行为差异不只是速度:250u8 + 1 * 6 在 dev 里 panic(退出码 101,「attempt to add with overflow」),在 release 里回绕得到 0,退出码 0。如果程序依赖溢出会 panic 来发现 bug,发布前要在 release + overflow-checks 下也测一遍。", t=tl(S(3)), mark=lidx(S(3), 'dev ', 'release '), kv=KV([['dev', '溢出 panic,退出码 101'], ['release', '回绕为 0,退出码 0']], ['release'])),
]
A = mkart('u127', 127, 'Rust,debug,release,Cargo,构建配置,真实验证,动画演示',
    f'用 cargo 的 dev 与 release 构建同一个程序验证差异:速度 {sp[0]}/{sp[1]}/{sp[2]} 倍(collatz/HashMap/排序);只把 dev 的 opt-level 调到 3 就追平 release;release 加 overflow-checks 让 collatz 从 {V["release(默认)"][0]:g} 变 {V["release + overflow-checks"][0]:g} ms,加 debug-assertions 让排序从 {V["release(默认)"][2]:g} 变 {V["release + debug-assertions"][2]:g} ms;溢出在 dev panic、release 回绕。',
    'debug 和 release 的区别到底在哪?是优化,还是断言,还是溢出检查?这篇用同一个程序和 Cargo profile 的几个开关,把速度差异和行为差异分别归到各自的原因上。',
    [(f'{sp[2]}×', 'release 对 dev 的排序加速倍数'), ('opt-level', '决定速度差异的主要开关(dev 改成 3 就追平)'), ('回绕 对 panic', '250u8 + 6 在 release 与 dev 里的结果')],
    [('dev 与 release 的速度', '<p>迭代器链在 debug 与 release 下的差别见<a href="rust-iterator-chain-performance.html">Iterator 链的性能</a>;编译阶段见<a href="rust-compile-stages.html">Rust 编译阶段</a>。</p>'), ('哪个开关起作用', '<p>profile 的完整配置见<a href="rust-cargo-profile.html">Cargo Profile</a>。</p>'), ('行为差异', '<p>溢出与 panic 的更多细节见<a href="rust-panic-unwrap-expect.html">panic!、unwrap 与 expect</a>。</p>')],
    steps, [ENV_U + '。每组计时是一次运行,不同次之间有几毫秒到百分之十几的波动', '没有验证:大型项目的编译时间差异(这里的程序编译不到 1 秒)、debuginfo 对二进制体积的影响(没有单独量)、incremental 与 codegen-units 对 release 编译时间和速度的影响、其它平台'], 'Debug 与 Release')
