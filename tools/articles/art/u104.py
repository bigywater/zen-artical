from lib import *
import re
S = SS('u104')
R = J('u104')
ks = re.findall(r'(\d+) 个阻塞任务 / 4 个工作线程:主任务 sleep\(10 ms\) 实际晚醒了约\s+(\d+) ms', R['k'])
sb = re.search(r'晚醒了约 (\d+) ms', R['sb']).group(1); bip = re.search(r'晚醒了约 (\d+) ms', R['bip']).group(1); cpu = re.search(r'用了约 (\d+) ms', R['cpu']).group(1)
k3 = dict(ks)
steps = [
    step("tokio 多线程运行时有 4 个工作线程。同时让 k 个任务用 std::thread::sleep(300 ms) 阻塞,主任务 sleep(10 ms),它醒来的延迟(实际时间减去 10 ms):" + ';'.join(f'k = {k}:约 {v} ms' for k, v in ks) + "。k 小于线程数时延迟只有几毫秒;k 达到 4 时,延迟跳到约 " + k3['4'] + " ms —— 四个工作线程都被占住,没有线程来驱动定时器,也没有线程来 poll 任务。", t=tl(S(1)), done=lidx(S(1), '0 个阻塞', '1 个阻塞', '2 个阻塞', '3 个阻塞'), mark=lidx(S(1), '4 个阻塞', '6 个阻塞'), b=bars([[f'k = {k}', int(v), f'{v} ms'] for k, v in ks], 270, cur=[4, 5], done=[0, 1, 2, 3]), kv=KV([['k < 4', '几毫秒'], ['k ≥ 4', f'约 {k3["4"]}–{k3["6"]} ms']], ['k ≥ 4'])),
    step(f"同样的 300 ms 阻塞工作用 spawn_blocking(6 个同时在跑,运行时仍然只有 4 个工作线程):主任务的 sleep(10 ms) 只晚了约 {sb} ms。阻塞任务在独立的阻塞线程池里,不占用工作线程。", t=tl(S(2)), done=lidx(S(2), '6 个 spawn_blocking'), kv=KV([['spawn_blocking', f'晚醒约 {sb} ms'], ['工作线程', '没被占用']], ['spawn_blocking'])),
    step(f"block_in_place:把运行时配成 2 个工作线程,2 个任务各用 block_in_place 阻塞 300 ms,主任务的 sleep(10 ms) 只晚了约 {bip} ms。它在多线程运行时里告诉调度器「这个线程要阻塞了」,其它任务不受影响。", t=tl(S(3)), done=lidx(S(3), '2 个 block_in_place'), kv=KV([['block_in_place', f'晚醒约 {bip} ms']], ['block_in_place'])),
    step("block_in_place 只能用在多线程运行时:在 current_thread 运行时里调用,panic:can call blocking only when running on the multi-threaded runtime。", t=tl(S(3)), mark=lidx(S(3), 'panicked', 'can call blocking'), kv=KV([['current_thread 里 block_in_place', 'panic']], ['current_thread 里 block_in_place'])),
    step(f"纯 CPU 计算(没有 await)同样会「阻塞」:4 个 200 ms 的计算任务占满 4 个工作线程时,主任务的 sleep(10 ms) 实际用了约 {cpu} ms。对计算密集的工作也要用 spawn_blocking 或专门的线程池(rayon)。", t=tl(S(4)), done=lidx(S(4), '4 个 200 ms'), kv=KV([['4 个计算任务占满 4 线程', f'sleep(10 ms) 用了约 {cpu} ms']], ['4 个计算任务占满 4 线程'])),
]
A = mkart('u104', 104, 'Rust,tokio,阻塞,spawn_blocking,真实验证,动画演示',
    f'下载 tokio 验证阻塞代码混入异步:4 个工作线程时,k = 3 个阻塞任务时 sleep(10 ms) 只晚几毫秒,k = 4 时晚约 {k3["4"]} ms(线程全被占满);spawn_blocking 晚 {sb} ms;block_in_place 晚 {bip} ms 但在 current_thread 里 panic;纯 CPU 计算占满 4 线程时 sleep(10 ms) 用了 {cpu} ms。',
    '异步代码里调用阻塞函数会怎样?影响有多大?阻塞多少个任务才会出问题?怎么修?这篇在一个 4 线程的 tokio 运行时里,把阻塞任务数从 0 增加到 6,量出延迟的跳变点,再验证 spawn_blocking 与 block_in_place。',
    [(f'{k3["3"]} 对 {k3["4"]} ms', '3 个与 4 个阻塞任务时,主任务 sleep(10 ms) 的延迟'), (f'{sb} ms', '同样的阻塞工作改用 spawn_blocking 后的延迟'), ('panic', 'block_in_place 用在 current_thread 运行时的结果')],
    [('阻塞任务数与延迟', '<p>tokio 的调度见<a href="rust-tokio-scheduling.html">Tokio 任务调度</a>;手写执行器中的同类现象见<a href="rust-async-runtime.html">Async Runtime 做了什么</a>。</p>'), ('spawn_blocking', None), ('block_in_place', None), ('CPU 密集的计算', '<p>并行计算见<a href="rust-rayon.html">Rayon 并行迭代</a>。</p>')],
    steps, [ENV_U + '。tokio 1.x;release 构建,每组只测一次(延迟有几毫秒波动)', '没有验证:阻塞线程池的默认上限与线程回收、block_in_place 的内部实现(是否补充工作线程)、async-std 的行为、阻塞 I/O(文件、DNS)在 tokio 里的默认处理'], '阻塞代码混入异步')
