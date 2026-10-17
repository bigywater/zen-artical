import json
from lib import *
R = J('r106'); th = {r[0]: r[1] + 1 for r in R['threads']}; sc = dict((k, v) for k, v in R['scale']); cpu = R['cpu']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
c99 = max(float(x[1]) for x in cpu)
steps = [
    step(f"「Redis 是单线程」指的是执行命令的那个线程。默认启动后进程里其实有 {th['默认']} 个线程(macOS 用 ps -M / top 数出来):1 个主线程 + {th['默认']-1} 个后台线程(BIO,第 107 篇)。", b=bars([['默认线程数', th['默认'], str(th['默认'])]], 8, done=[0]), kv=KV([['默认', f"{th['默认']} 个线程"]], ['默认'])),
    step(f"配置 io-threads 4 后是 {th['io-threads 4']} 个线程:多了 3 个 I/O 线程(第 109 篇)。再开 appendonly yes 线程数不变——AOF 的 fsync 走已有的后台线程。", b=bars([['默认', th['默认'], str(th['默认'])], ['io-threads 4', th['io-threads 4'], str(th['io-threads 4'])], ['+ appendonly', th['io-threads 4 + appendonly yes'], str(th['io-threads 4 + appendonly yes'])]], 8, done=[1, 2]), kv=KV([['io-threads 4', f"{th['io-threads 4']} 个线程"]], ['io-threads 4'])),
    step(f"用 redis-benchmark(C 程序,不受 Python GIL 限制)加压,SET、管道 16:1 个连接 {sc[1]/1000:.0f}k 条/秒,4 个连接 {sc[4]/1000:.0f}k,16 个连接 {sc[16]/1000:.0f}k,64 个连接 {sc[64]/1000:.0f}k——16 个连接之后不再增长。", b=bars([[f'{k} 个连接', sc[k] / 1000, f'{sc[k]/1000:.0f}k/s'] for k in (1, 4, 16, 64)], sc[16] / 1000, done=[2, 3]), kv=KV([['吞吐上限', f'约 {sc[16]/1000:.0f}k 条/秒']], ['吞吐上限'])),
    step(f"压测期间 top 采样 Redis 进程:CPU 达到 {c99:.1f}%,线程数是 4,其中同一时刻只有 1 个在运行——一个核被主线程占满,这就是吞吐平台的原因。", b=bars([[f'采样 {i+1}', float(x[1]), f'{x[1]}%'] for i, x in enumerate(cpu)], 100, mark=[len(cpu) - 1]), kv=KV([['主线程 CPU', f'{c99:.1f}%']], ['主线程 CPU'])),
    step("含义:命令是一个接一个执行的,所以一个慢命令(第 96、81 篇量过:KEYS、大 key 的 MIGRATE/DEL)会让所有客户端一起等;扩容要靠多个实例(分片/集群),而不是给一个实例加连接。", b=bars([['同一时刻执行命令的线程数', 1, '1']], 4, done=[0]), kv=KV([['结论', '一个慢命令 = 全体等待']], ['结论'])),
]
A = dict(
    n=106, series='redis', tags='Redis,线程模型,真实验证,动画演示',
    desc=f'验证 Redis 的线程模型:默认进程有 {th["默认"]} 个线程(主线程 + {th["默认"]-1} 个后台线程),io-threads 4 时 {th["io-threads 4"]} 个;redis-benchmark 加压时 SET 吞吐在约 {sc[16]/1000:.0f}k 条/秒处趋平(16 个连接 {sc[16]/1000:.0f}k、64 个连接 {sc[64]/1000:.0f}k),同时 Redis 进程 CPU {c99:.0f}%——一个核被主线程占满。',
    lead='「Redis 是单线程的」这句话对也不对:命令确实是一个线程在执行,但进程里有好几个线程。这篇数一数线程,再用真正的压测工具把「单线程执行」的后果量出来:吞吐的上限在哪里、CPU 长什么样。',
    facts=[(f'{th["默认"]} 个线程', f'默认进程的线程数(1 主 + {th["默认"]-1} 后台);io-threads 4 时 {th["io-threads 4"]} 个'), (f'{sc[16]/1000:.0f}k / {sc[64]/1000:.0f}k', '16 个连接 vs 64 个连接的 SET 吞吐(条/秒):不再增长'), (f'{c99:.0f}%', '压测时 Redis 进程的 CPU:一个核被占满')],
    body=[
        sec('数线程', '', term('', blk('r106', 1)), f'<p>默认配置下进程有 {th["默认"]} 个线程:主线程负责接收请求、执行命令、回复;另外 {th["默认"]-1} 个是后台线程(第 107 篇看它们做什么)。<code>io-threads 4</code> 增加了 3 个 I/O 线程,总共 {th["io-threads 4"]} 个(第 109 篇)。线程数取自 <code>ps -M</code> 与 <code>top</code> 的输出,macOS 上没法直接看线程名,所以「哪个是 BIO」这里没有验证。</p>'),
        sec('吞吐的平台', 'redis-benchmark,SET,管道 16,50 万条,每格 2 次取中位', term('', blk('r106', 2)), f'<p>1 个连接 {sc[1]/1000:.0f}k 条/秒,4 个连接 {sc[4]/1000:.0f}k,16 个连接 {sc[16]/1000:.0f}k,64 个连接 {sc[64]/1000:.0f}k。前面是客户端不够快,加连接就涨;16 个连接之后到顶——服务器处理不过来了。(我先用 Python 线程做过一次类似实验,结果被 GIL 限制成客户端瓶颈,没有意义,换成了 C 写的 redis-benchmark。)</p>'),
        sec('CPU:一个核', '', term('', blk('r106', 3)), f'<p>压测时 <code>top</code> 三次采样,Redis 进程的 CPU 到 {c99:.1f}%(第一次采样在压测刚开始,数值低),线程数 4,同一时刻只有 1 个线程在运行。这是主线程跑满一个核。</p>'),
        sec('这意味着什么', '', '<p>命令是串行执行的:一个慢命令占着主线程,所有客户端都排在后面(第 96 篇的排队实验、第 81 篇的 MIGRATE 阻塞)。单实例的吞吐上限就是这个平台,想更高只能多实例(分片/集群,第 68 篇)或开启 I/O 多线程分担网络读写(第 109 篇)。</p>'),
        sec('分步演示:单线程执行', '', demo('Redis 单线程模型与后台线程', [('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。redis-benchmark -t set -P 16;线程数由 ps -M / top 得到', '没有验证:Linux 上的线程名与数量、后台线程各自的职责(第 107 篇)、命令执行期间主线程是否让出(有些命令分批执行)、超线程 / 多核机器上 I/O 线程的收益(第 109 篇)'],
)
