from lib import *
import re
S = SS('u95')
R = J('u95')
cores = re.search(r'可用并行度 (\d+)', R['basic']).group(1)
h = re.search(r'串行 iter\s+([\d.]+) ms.*\n并行 par_iter\s+([\d.]+) ms.*加速 ([\d.]+)×', R['heavy']); hs, hp, hx = h.group(1), h.group(2), h.group(3)
sm = re.findall(r'n=\s*(\d+): 串行\s+([\d.]+) µs\s+并行\s+([\d.]+) µs\s+(\S+)', R['small'])
sc = re.findall(r'线程数\s+(\d+):\s+([\d.]+) ms\s+相对 1 线程 ([\d.]+)×', R['scale'])
mx = re.search(r'Mutex\s+([\d.]+) ms.*\n.*reduce\s+([\d.]+) ms.*\n串行 sum\s+([\d.]+) ms', R['mutex']); mm, mr, ms_ = mx.group(1), mx.group(2), mx.group(3)
steps = [
    step(f"rayon(从 crates.io 下载编译):把 iter() 换成 par_iter() 就并行了。这台机器可用并行度 {cores},rayon 线程数也是 {cores}。par_iter().map().collect() 保持原顺序(true),sum 结果与串行相同(210);但 for_each 里的执行顺序不是 0..16 的顺序(false),内容是齐全的。", t=tl(S(1)), done=lidx(S(1), '可用并行度', '保持原顺序', 'par_iter().sum()'), mark=lidx(S(1), 'for_each'), kv=KV([['collect', '保序'], ['for_each 的执行顺序', '不保证'], ['线程数', f'= 核数 {cores}']], ['for_each 的执行顺序'])),
    step(f"CPU 密集任务:2000 万个数求 sin 之和(release,取 3 次最小),串行 {hs} ms,par_iter {hp} ms,加速 {hx}×({cores} 个线程)。两个结果在小数点后约 9 位一致 —— 并行的加法顺序不同,浮点结果不保证逐位相同。", t=tl(S(2)), done=lidx(S(2), '并行 par_iter'), b=bars([['串行 iter', float(hs), f'{hs} ms'], ['并行 par_iter', float(hp), f'{hp} ms']], float(hs), cur=[1], done=[0]), kv=KV([['串行', f'{hs} ms'], ['并行', f'{hp} ms'], ['加速', f'{hx}×']], ['加速'])),
    step("任务太小时并行更慢:求和 " + ';'.join(f"n={n}:串行 {a} µs / 并行 {b} µs({c})" for n, a, b, c in sm) + "。线程调度与任务拆分有固定开销,数据要大到一定程度才划算(这里的交叉点在 100 万到 1 亿之间,没有精确测)。", t=tl(S(3)), mark=lidx(S(3), '串行更快'), done=lidx(S(3), '并行更快'), b=bars([[f'n={n} 并行/串行', round(float(b) / float(a), 2), f'{float(b) / float(a):.2f}×'] for n, a, b, c in sm], max(float(b) / float(a) for n, a, b, c in sm) * 1.1, done=list(range(len(sm)))), kv=KV([[f'n={n}', c] for n, a, b, c in sm], [f'n={sm[-1][0]}'])),
    step("线程数与加速:用 ThreadPoolBuilder 指定线程数,1000 万个数求 sin 之和:" + ';'.join(f"{n} 线程 {t} ms({x}×)" for n, t, x in sc) + "。前几步接近线性,最后几个线程收益变小。", t=tl(S(4)), done=lidx(S(4), '线程数'), b=bars([[f'{n} 线程', float(x), f'{x}×'] for n, t, x in sc], float(sc[-1][2]) + 0.5, done=list(range(len(sc)))), kv=KV([[f'{n} 线程', f'{t} ms / {x}×'] for n, t, x in sc], [f'{sc[-1][0]} 线程'])),
    step(f"在并行闭包里共享可变状态会毁掉并行:500 万个数求和,par_iter + for_each + Mutex 要 {mm} ms,比串行的 {ms_} ms 慢得多;用 reduce(每个线程先局部累加再合并)只要 {mr} ms。能用 reduce / fold / sum 就不要共享状态。", t=tl(S(5)), done=lidx(S(5), 'reduce'), mark=lidx(S(5), 'Mutex'), b=bars([['par_iter + Mutex', float(mm), f'{mm} ms'], ['串行 sum', float(ms_), f'{ms_} ms'], ['par_iter + reduce', float(mr), f'{mr} ms']], float(mm), cur=[0], done=[1, 2]), kv=KV([['Mutex', f'{mm} ms'], ['串行', f'{ms_} ms'], ['reduce', f'{mr} ms']], ['reduce'])),
    step("rayon 仍然受 Send / Sync 约束:在 into_par_iter().for_each 里使用 RefCell,报 error[E0277]: `RefCell<i32>` cannot be shared between threads safely,指向闭包。并行的安全由类型系统保证。", t=tl(S(6)), mark=lidx(S(6), 'error[E0277]'), kv=KV([['闭包捕获 RefCell', 'E0277:不是 Sync']], ['闭包捕获 RefCell'])),
]
A = mkart('u95', 95, 'Rust,rayon,并行迭代,真实验证,动画演示',
    f'真实下载 rayon 验证并行迭代器:par_iter 保序 collect;2000 万个 sin 求和串行 {hs} ms 对并行 {hp} ms({hx}×,{cores} 线程);小任务并行更慢;线程数从 1 到 {sc[-1][0]} 的加速曲线;for_each + Mutex 慢到 {mm} ms 而 reduce 只要 {mr} ms;闭包仍受 Sync 约束(E0277)。',
    'rayon 让「把 iter 改成 par_iter」成为可能,但到底能快多少?什么时候反而更慢?线程数怎么影响?闭包里能不能随便改共享状态?这篇每个问题都在本机跑出数字。',
    [(f'{hx}×', f'{cores} 线程下,2000 万个 sin 求和的加速比'), ('慢于串行', '数据量 100 万以下时 par_iter 的表现'), (f'{mm} 对 {mr} ms', 'par_iter 用 Mutex 共享累加与用 reduce 的耗时')],
    [('par_iter 的基本行为', '<p>rayon 1.x 从 crates.io 下载(需要联网)。线程的基础见<a href="rust-thread-spawn-join.html">线程创建与 Join</a>。</p>'), ('CPU 密集任务', None), ('任务太小', None), ('线程数与加速', None), ('共享可变状态', '<p>Mutex 的开销见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>。</p>'), ('Send / Sync 约束', None)],
    steps, [ENV_U + '。10 核机器,rayon 1.x;耗时 release 构建', '没有验证:work-stealing 的具体调度、par_bridge、嵌套并行与死锁风险、par_sort 的加速、不同核数的机器上的曲线、线程池创建开销、内存带宽受限任务的加速比'], 'rayon')
