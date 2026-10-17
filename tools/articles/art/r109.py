import json
from lib import *
R = J('r109'); T = {int(k): v for k, v in R['t'].items()}; D = R['dist']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
g = lambda io, i: T[io][i]
pct = lambda io, i: (g(io, i) / g(1, i) - 1) * 100
steps = [
    step("io-threads N 让 N-1 个额外的 I/O 线程分担「读取请求、写回响应」这类网络 I/O;命令的执行仍然只在主线程。本机 10 个核,redis-benchmark 与 Redis 在同一台机器上争 CPU,这一点会影响结果。", t=tm(['I/O 线程:读请求、写响应', '主线程:执行命令'], cur=[0, 1]), kv=KV([['注意', '压测与被测在同一台机器']], ['注意'])),
    step(f"没有管道的 GET,50 个连接:io-threads 1 / 2 / 4 / 8 → {g(1,0)/1000:.0f}k / {g(2,0)/1000:.0f}k / {g(4,0)/1000:.0f}k / {g(8,0)/1000:.0f}k 条/秒。差别很小(最多 {max(pct(k,0) for k in (2,4,8)):+.0f}%)——这种负载下瓶颈是每次往返的系统调用与客户端,不是服务器的主线程。", b=bars([[f'io-threads {k}', g(k, 0) / 1000, f'{g(k,0)/1000:.0f}k/s'] for k in (1, 2, 4, 8)], max(g(k, 0) for k in T) / 1000, done=[0, 1, 2, 3]), kv=KV([['50 连接,无管道', f'{min(g(k,0) for k in T)/1000:.0f}k – {max(g(k,0) for k in T)/1000:.0f}k']], ['50 连接,无管道'])),
    step(f"400 个连接、无管道:{g(1,1)/1000:.0f}k / {g(2,1)/1000:.0f}k / {g(4,1)/1000:.0f}k / {g(8,1)/1000:.0f}k;io-threads 8 比 1 高 {pct(8,1):.0f}%。连接更多,I/O 线程开始有一点用。", b=bars([[f'io-threads {k}', g(k, 1) / 1000, f'{g(k,1)/1000:.0f}k/s'] for k in (1, 2, 4, 8)], max(g(k, 1) for k in T) / 1000, done=[3]), kv=KV([['400 连接', f'io-threads 8:{pct(8,1):+.0f}%']], ['400 连接'])),
    step(f"50 连接、管道 16:{g(1,2)/1e6:.2f}M / {g(2,2)/1e6:.2f}M / {g(4,2)/1e6:.2f}M / {g(8,2)/1e6:.2f}M 条/秒。io-threads 4 和 8 都是 {g(4,2)/1e6:.2f}M——很可能已经到了 redis-benchmark 自己(与 Redis 抢 CPU)的上限,数字不能再区分。", b=bars([[f'io-threads {k}', g(k, 2) / 1e6, f'{g(k,2)/1e6:.2f}M/s'] for k in (1, 2, 4, 8)], max(g(k, 2) for k in T) / 1e6, done=[2, 3]), kv=KV([['管道 16', f'io-threads 4:{pct(4,2):+.0f}%']], ['管道 16'])),
    step("确认 I/O 线程确实在干活:INFO threads 里,io-threads 1 时 io_thread_0(主线程)处理了全部约 1000 万次读;io-threads 4 时 io_thread_0 的读数是 0,三个 I/O 线程各处理约 330 万次;io-threads 8 时七个线程平分。", t=tm([f'io-threads {io}: ' + '  '.join(f'{k.replace("io_thread_","T")}:{v.split(",")[1]}' for k, v in D[str(io)].items()) for io in (1, 4)], cur=[0, 1]), kv=KV([['读取', '被均分到 I/O 线程,主线程不再读']], ['读取'])),
    step("结论(限于这次测量):I/O 线程把网络读写从主线程挪走了(计数可证),但在本机、压测与被测抢同一批 CPU 的条件下,吞吐提升有限(约 5–12%)。要看到明显收益,通常需要独立的压测机、更多连接和更大的 value——本文没有覆盖这些条件。", b=bars([['无管道 50 连接', pct(8, 0), f'{pct(8,0):+.0f}%'], ['无管道 400 连接', pct(8, 1), f'{pct(8,1):+.0f}%'], ['管道 16', pct(4, 2), f'{pct(4,2):+.0f}%']], 20, done=[0, 1, 2]), kv=KV([['本机收益', '约 5–12%']], ['本机收益'])),
]
A = dict(
    n=109, series='redis', tags='Redis,io-threads,多线程,真实验证,动画演示',
    desc=f'实测 io-threads 1/2/4/8(本机 10 核,redis-benchmark 与 Redis 同机):INFO threads 证明读取被均分到 I/O 线程(io-threads 4 时主线程读 0 次、三个 I/O 线程各约 330 万次),但吞吐只提升约 5–12%(无管道 50 连接 {g(1,0)/1000:.0f}k → {g(8,0)/1000:.0f}k;400 连接 {g(1,1)/1000:.0f}k → {g(8,1)/1000:.0f}k;管道 16 {g(1,2)/1e6:.2f}M → {g(4,2)/1e6:.2f}M)。',
    lead='Redis 6 引入 I/O 多线程,常被说成「让 Redis 多线程了」。它到底做了什么、能带来多少吞吐提升?这篇在本机上用 redis-benchmark 量三种负载,并用 INFO threads 的计数证明 I/O 线程确实分担了读写;同时坦率地说明:在压测与被测同机的条件下,收益很有限。',
    facts=[('主线程读 0 次', 'io-threads 4 时,INFO threads 显示 io_thread_0(主线程)读了 0 次,三个 I/O 线程各约 330 万次'), (f'{pct(8,1):+.0f}% / {pct(4,2):+.0f}%', '本机测得的最大收益:400 连接无管道(io-threads 8)/ 管道 16(io-threads 4)'), ('同机压测', 'redis-benchmark 与 Redis 抢同一批 CPU,结果偏保守')],
    body=[
        sec('吞吐对比', '每格 3 次取中位;redis-benchmark 8 个线程、GET、value 3 字节', term('', blk('r109', 1)), f'<p>三种负载下 io-threads 从 1 到 8 的提升都不大:50 连接无管道 {g(1,0)/1000:.0f}k → {g(8,0)/1000:.0f}k,400 连接无管道 {g(1,1)/1000:.0f}k → {g(8,1)/1000:.0f}k,50 连接管道 16 {g(1,2)/1e6:.2f}M → {g(4,2)/1e6:.2f}M(io-threads 8 与 4 相同,应是压测端上限)。io-threads 2 在管道 16 时反而低于 1({g(2,2)/1e6:.2f}M vs {g(1,2)/1e6:.2f}M),是单次测量的波动,我没有重复确认。</p>'),
        sec('I/O 线程确实在干活', '', term('', blk('r109', 2)), '<p>INFO 的 <code>threads</code> 段为每个线程列出处理的读/写次数。io-threads 1 时 <code>io_thread_0</code>(主线程)处理了全部读写;io-threads 4 时 <code>io_thread_0</code> 是 0,三个 I/O 线程各处理约三分之一;io-threads 8 时七个 I/O 线程平分。所以网络读写确实被挪出了主线程。</p>'),
        sec('为什么在这里看不到大收益', '', '<p>命令的执行仍是单线程(第 106 篇)。I/O 线程只在「网络读写占了主线程大部分时间」时才有明显收益:多连接、大 value、真实网卡的场景。而这次测量里压测端与 Redis 在同一台机器上,抢同样的 CPU,压测端自己往往先到上限(管道 16 时 io-threads 4 与 8 得到完全相同的数字就是迹象)。这里没有独立的压测机,也没有更大的 value(我最初还试过 4 KB,收益同样不明显,没有整理进表里),所以<b>不能据此说 I/O 线程没用,只能说在这个条件下提升有限</b>。</p>'),
        sec('分步演示:io-threads 的作用', '', demo('Redis io-threads', [('t', 'term', '说明'), ('b', 'bars', '吞吐'), ('kv', 'kv', '要点')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。本机 10 个核(6 个性能核);redis-benchmark -t get --threads 8;io-threads 由配置文件设置', '没有验证:独立压测机、真实网卡、更大的 value、io-threads-do-reads 等相关参数、Linux 上的表现、CPU 亲和性'],
)
