from lib import *
import re
S = SS('u92')
R = J('u92')
lost = int(re.search(r'load \+ store:.*?实际 (\d+)', R['count']).group(1))
cost = {m[0]: (float(m[1]), float(m[2])) for m in re.findall(r'^(\w+)\s+单线程\s+([\d.]+) ns/次\s+4 线程争用\s+([\d.]+) ns/次', R['cost'], re.M)}
mp = R['mp']; rel_list = [x[0] for x in mp]; acq_list = [x[1] for x in mp]
steps = [
    step(f"4 个线程各加 100 万次:fetch_add 是一条原子的「读-改-写」,结果恰好 4000000;而 load 之后再 store(v + 1) 虽然每一步都是原子操作,合起来不是,两个线程会读到同一个值,更新被覆盖,这次只剩 {lost}。原子类型保证的是单个操作的原子性,不是你的逻辑。", t=tl(S(1)), done=lidx(S(1), 'fetch_add'), mark=lidx(S(1), 'load + store'), b=bars([['fetch_add', 4000000, '4000000'], ['load + store', lost, str(lost)]], 4000000, cur=[1], done=[0]), kv=KV([['fetch_add', '4000000'], ['load + store', f'{lost}(丢更新)']], ['load + store'])),
    step(f"不同 Ordering 的成本(release,取 3 次最小):单线程每次 fetch_add,Relaxed {cost['Relaxed'][0]:g} ns,AcqRel {cost['AcqRel'][0]:g} ns,SeqCst {cost['SeqCst'][0]:g} ns;4 个线程争用同一个变量时,每次操作的平均墙钟时间 Relaxed {cost['Relaxed'][1]:g} ns,AcqRel {cost['AcqRel'][1]:g} ns,SeqCst {cost['SeqCst'][1]:g} ns。在这台 aarch64 机器上 Relaxed 最快,但 AcqRel 与 SeqCst 之间没有稳定的差别(争用时 AcqRel 反而比 SeqCst 慢,说明测量有噪声)。", t=tl(S(2)), done=lidx(S(2), 'Relaxed', 'AcqRel', 'SeqCst'), b=bars([['Relaxed 单线程', cost['Relaxed'][0], f"{cost['Relaxed'][0]:g} ns"], ['AcqRel 单线程', cost['AcqRel'][0], f"{cost['AcqRel'][0]:g} ns"], ['SeqCst 单线程', cost['SeqCst'][0], f"{cost['SeqCst'][0]:g} ns"]], cost['SeqCst'][0] * 1.2, done=[0, 1, 2]), kv=KV([['Relaxed', f"{cost['Relaxed'][0]:g} / {cost['Relaxed'][1]:g} ns"], ['AcqRel', f"{cost['AcqRel'][0]:g} / {cost['AcqRel'][1]:g} ns"], ['SeqCst', f"{cost['SeqCst'][0]:g} / {cost['SeqCst'][1]:g} ns"]], ['Relaxed'])),
    step(f"弱内存序真的会出现:消息传递测试,线程 A 先写 data=1 再写 flag=1,线程 B 读到 flag=1 之后再读 data,若读到 0 就是「看到了 flag 却没看到 data」。flag 用 Relaxed 写/读时,4 次运行(每次 100 万轮)各出现 {'、'.join(map(str, rel_list))} 次这种异常(aarch64 允许重排);flag 用 Release 写/Acquire 读时 4 次运行都是 {'、'.join(map(str, acq_list))} 次。", t=tl(S(3)), mark=lidx(S(3), '第 2 次', '第 4 次'), done=lidx(S(3), '第 1 次', '第 3 次'), b=bars([[f'第 {i + 1} 次 Relaxed', v, str(v)] for i, v in enumerate(rel_list)] + [['Release/Acquire(4 次合计)', sum(acq_list), str(sum(acq_list))]], max(rel_list) + 10, cur=[3], done=[0, 1, 2, 4]), kv=KV([['Relaxed 异常次数', '、'.join(map(str, rel_list))], ['Release/Acquire', '、'.join(map(str, acq_list))]], ['Relaxed 异常次数'])),
    step("结论:Release 写与 Acquire 读建立「happens-before」:读到 flag=1 的线程一定能看到写 flag 之前的写入。Relaxed 只保证原子性,不保证和其他变量之间的顺序。同样的 Relaxed 代码在 x86(强内存模型)上可能一直测不出问题,在 aarch64 上就会出现 —— 但本文没有在 x86 上验证。", t=tl(S(3)), kv=KV([['Release → Acquire', '建立 happens-before'], ['Relaxed', '只保证原子性']], ['Release → Acquire'])),
]
A = mkart('u92', 92, 'Rust,原子类型,内存序,Ordering,真实验证,动画演示',
    f'用真实运行验证原子类型与内存序:fetch_add 恰好 4000000 而 load+store 只剩 {lost};Relaxed/AcqRel/SeqCst 的单线程与争用成本;在 aarch64 上消息传递测试里 Relaxed 4 次运行出现 {"、".join(map(str, rel_list))} 次「看到 flag 却没看到 data」,Release/Acquire 为 0。',
    '内存序是 Rust 并发里最难直觉的部分。这篇先证明原子操作与原子逻辑不是一回事,再测不同 Ordering 的成本,最后在 aarch64 上真的跑出 Relaxed 的异常结果,让 Release / Acquire 的作用变得可见。',
    [(f'{lost}', 'load + store 版计数器的最终值(期望 4000000)'), (f'{max(rel_list)} 次', 'Relaxed 下,单次运行(100 万轮)里出现的最大异常次数'), ('0 次', 'Release / Acquire 在所有运行里的异常次数')],
    [('原子操作 ≠ 原子逻辑', None), ('Ordering 的成本', '<p>耗时是本机微基准,各次测量之间有噪声。</p>'), ('Relaxed 真的会乱序', '<p>下一篇讲 CAS:<a href="rust-atomic-cas.html">Atomic CAS 操作</a>。</p>')],
    steps, [ENV_U + '。aarch64(弱内存模型);release 构建', '没有验证:x86_64 上的 Relaxed 行为、SeqCst 与 AcqRel 在存储缓冲(SB)测试里的区别、fence 的用法、Consume 序(Rust 没有)、其它架构、更大的线程数下的争用成本'], '原子类型与内存序')
