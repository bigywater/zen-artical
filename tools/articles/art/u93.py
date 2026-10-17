from lib import *
import re
S = SS('u93')
R = J('u93')
m = re.search(r'(\d+) 次 CAS 循环调用,最终值 (\d+)', R['loop']); calls, final = m.group(1), m.group(2)
ex = int(re.search(r'循环体共执行 (\d+) 次', R['loop']).group(1)); retry = ex - int(calls)
wf = re.search(r'虚假失败 (\d+) / (\d+) 次', R['weak'])
steps = [
    step("compare_exchange(期望, 新值, 成功序, 失败序):当前值等于期望才写入。5 → 9 成功返回 Ok(5),现在是 9;再用期望 5 → 7,当前值已是 9,不写入,返回 Err(9)(把当前值交还给你)。swap(1) 返回旧值 9,fetch_max(10) 返回旧值 1,最终 10。", t=tl(S(1)), done=lidx(S(1), 'expect 5 → 9', 'swap(1)'), mark=lidx(S(1), 'expect 5 → 7'), kv=KV([['成功', 'Ok(旧值)'], ['失败', 'Err(当前值)']], ['失败'])),
    step(f"CAS 循环能实现没有专用指令的原子操作:手写 fetch_mul3(读当前值,算新值,compare_exchange_weak 试写,失败就用返回的当前值重试)。4 个线程共调用 {calls} 次,最终值 {final} 与单线程顺序应用 {calls} 次的结果完全相同(乘法可交换)。循环体共执行 {ex} 次,其中 {retry} 次是 CAS 失败后的重试。", t=tl(S(2)), done=lidx(S(2), '次 CAS 循环调用'), mark=lidx(S(2), '循环体共执行'), b=bars([['调用次数', int(calls), calls], ['循环体执行次数', ex, str(ex)]], ex, cur=[1], done=[0]), kv=KV([['结果', '与顺序应用相同'], ['重试', f'{retry} 次']], ['重试'])),
    step("fetch_update 是 CAS 循环的封装:只在值小于 20 时加 5,三次调用得到 Ok(10)、Ok(15)、Err(20)(闭包返回 None 就不写入并返回当前值)。", t=tl(S(2)), done=lidx(S(2), 'fetch_update'), kv=KV([['fetch_update', '封装的 CAS 循环,闭包返回 None 则放弃']], ['fetch_update'])),
    step(f"compare_exchange_weak 在文档里允许「虚假失败」(值相等也可能返回 Err),所以只能用在循环里。这台机器上单线程、期望值永远正确的情况下,实测 weak 虚假失败 {wf.group(1)} / {wf.group(2)} 次。原因见最后一步:两者在 aarch64 上编译成了同样的指令。", t=tl(S(3)), done=lidx(S(3), 'compare_exchange_weak'), kv=KV([['weak 的虚假失败', f'{wf.group(1)} / {wf.group(2)}(本机)']], ['weak 的虚假失败'])),
    step("用 CAS 手写自旋锁保护一个非原子的计数(UnsafeCell<u64>):lock 是 while compare_exchange_weak(false, true, Acquire, Relaxed).is_err() 自旋,unlock 是 store(false, Release)。4 线程 × 10 万次后计数 = 400000,没有丢更新。", t=tl(S(4)), done=lidx(S(4), '400000'), kv=KV([['lock', 'CAS(false → true, Acquire)'], ['unlock', 'store(false, Release)']], ['lock'])),
    step("ABA 问题:CAS 只比较值。线程 1 读到 1,别的线程把它改成 2 再改回 1,线程 1 的 CAS(期望 1)仍返回 Ok(1) —— 它看不到中间的变化。把值和版本号打包进同一个 u64(低 32 位值,高 32 位版本),每次写入版本号 +1,同样的操作 CAS 失败(false),当前是 值1/版本2。", t=tl(S(5)), mark=lidx(S(5), '无版本号'), done=lidx(S(5), '有版本号'), kv=KV([['无版本号', 'A→B→A 后 CAS 仍成功'], ['有版本号', 'CAS 失败,发现被改过']], ['有版本号'])),
    step(f"这台机器上两种 CAS 的汇编完全相同:strong 与 weak 都是 mov mov casal cmp cset ret —— 一条 casal(ARMv8.1 的原子比较交换指令),不会虚假失败,所以第 4 步测到 {wf.group(1)} 次。在用 ldxr/stxr 循环实现 CAS 的 CPU 上,weak 才会比 strong 省掉外层循环,但这一点没有在那类机器上验证。", t=tl(S(6)), done=lidx(S(6), 'strong', 'weak'), kv=KV([['strong', 'casal'], ['weak', 'casal(相同)']], ['weak'])),
]
A = mkart('u93', 93, 'Rust,原子类型,CAS,compare_exchange,真实验证,动画演示',
    f'用真实运行验证 compare_exchange:成功返回 Ok(旧值)、失败返回 Err(当前值);手写 CAS 循环 fetch_mul3({calls} 次调用结果与顺序执行相同,{retry} 次重试);fetch_update;自旋锁保护 400000;ABA 问题与版本号;本机 aarch64 上 weak 与 strong 都编译成 casal,虚假失败 {wf.group(1)} 次。',
    'CAS(比较并交换)是几乎所有无锁数据结构的基础。这篇验证它的返回值语义、怎么用循环实现任意读-改-写、手写自旋锁、经典的 ABA 问题,以及 compare_exchange_weak 在本机上到底有没有「虚假失败」。',
    [('casal', '本机上 compare_exchange 与 compare_exchange_weak 都编译成的单条指令'), (f'{retry} 次', f'手写 CAS 循环 {calls} 次调用中因 CAS 失败而重试的次数'), ('ABA', '只比较值的 CAS 看不到 A→B→A 的中间变化')],
    [('compare_exchange 的语义', '<p>内存序的基础见<a href="rust-atomics-memory-ordering.html">原子类型与内存序</a>。</p>'), ('CAS 循环', None), ('虚假失败', None), ('自旋锁', '<p>用 Mutex 的版本见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>。</p>'), ('ABA 问题', None), ('汇编层面', None)],
    steps, [ENV_U + '。aarch64;release 构建', '没有验证:x86_64 与 ldxr/stxr 架构上 weak 的虚假失败率、完整的无锁栈/队列(需要处理内存回收)、crossbeam-epoch 等回收方案、compare_exchange 的失败序为 Acquire 时的作用、自旋锁在高争用下的公平性与 CPU 消耗'], 'CAS')
