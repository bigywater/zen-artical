from lib import *
S = SS('m78')
steps = [
    step("原始 TCP 连接(各发一次 hello)从 0 加到 1,000:connections.current 4 → 104 → 503 → 1003,mongod 的线程数 73 → 173 → 572 → 1072,RSS 100.3 → 118.8 → 143.4 → 173.3 MB。每多一个连接多一个线程(1000 个连接多了 999 个线程),每个连接大约 73 KB 的 RSS;建立 1,000 个连接(含各一次 hello)共 1.78 秒。", t=tl(S(1)), mark=lidx(S(1), '基线', '再加到 100', '再加到 500', '再加到 1000', '共 1.78'), done=lidx(S(1), '基线'), b=bars([['0 个', 73, '73 线程'], ['100 个', 173, '173'], ['500 个', 572, '572'], ['1000 个', 1072, '1072']], 1072, mark=[3], done=[0, 1, 2]), kv=KV([['connections.current', '4 → 1003'], ['线程数', '73 → 1072'], ['RSS', '100.3 → 173.3 MB']], ['线程数'])),
    step("连接全部关掉后:connections.current 降到 3,线程数在 0.3 秒内就回落到 72(2 秒 72,5 秒 71),但 RSS 没有回落:142.4 MB → 142.6 MB——线程退出了,内存没有还给操作系统(比 100.3 MB 的基线高出约 42 MB)。", t=tl(S(2)), mark=lidx(S(2), '关闭后约'), done=lidx(S(2), '关闭后约 0.3'), kv=KV([['0.3 秒后线程数', '72(回落)'], ['5 秒后线程数', '71'], ['RSS', '142.6 MB(基线 100.3)']], ['RSS'])),
    step("--maxConns 50(配置文件里叫 net.maxIncomingConnections):开始 current = 6、available = 44。依次建立 60 个连接各发一次 hello:成功 44 个、失败 16 个——失败的客户端看到 ConnectionError(recv 返回空)或 ConnectionResetError(Errno 54)。服务端 connections 变成 current = 50、available = 0、rejected = 16;日志每次拒绝一条:Connection refused because there are too many open connections(共 16 条)。", t=tl(S(3)), mark=lidx(S(3), '成功 44 个', '失败的情况', '服务器端', '日志里含'), done=lidx(S(3), 'serverStatus.connections'), b=bars([['成功', 44, '44'], ['失败', 16, '16']], 44, mark=[1], done=[0]), kv=KV([['maxConns', '50'], ['成功 / 失败', '44 / 16'], ['connections.rejected', '16'], ['日志', 'Connection refused because there are too many open connections']], ['connections.rejected'])),
    step("available 怎么来的:默认 current = 6、available = 209709,current + available = 209715;--maxConns 1000 时 current = 6、available = 994,合计恰好 1000。", t=tl(S(4)), mark=lidx(S(4), '默认:', '--maxConns 1000:'), done=lidx(S(4), '默认:'), kv=KV([['默认 current + available', '209,715'], ['--maxConns 1000', '1,000']], ['--maxConns 1000'])),
    step("新建连接的代价:1,000 次 find 复用一个连接共 42 ms(每次 42 μs);每次都新建 TCP 连接 + hello + find 共 309 ms(每次 309 μs),是复用的 7.4 倍。", t=tl(S(5)), mark=lidx(S(5), '复用一个连接', '新建连接方式'), done=lidx(S(5), '复用一个连接'), b=bars([['复用连接', 42, '42 μs'], ['每次新建连接', 309, '309 μs']], 309, mark=[1], done=[0]), kv=KV([['复用', '42 μs/次'], ['每次新建', '309 μs/次'], ['倍数', '7.4']], ['倍数'])),
    step("connections 里的计数:200 个空闲原始连接 + 8 个已 ping 的客户端,current = 228、threaded = 228(每个连接一个线程)、active = 10;8 个 sleep 的慢查询在跑时 active = 18(多出的 8 个就是它们);查询结束后回到 10。current 全程不变。", t=tl(S(6)), mark=lidx(S(6), '什么都没跑', '正在跑', '慢查询结束后'), done=lidx(S(6), '什么都没跑'), b=bars([['空闲', 10, 'active 10'], ['8 个慢查询', 18, 'active 18'], ['结束后', 10, 'active 10']], 18, mark=[1], done=[0]), kv=KV([['current / threaded', '228 / 228'], ['active:空闲 → 慢查询中 → 结束后', '10 → 18 → 10']], ['active:空闲 → 慢查询中 → 结束后'])),
]
A = mkartm('m78', 78, 'MongoDB,连接,线程,maxConns,connections,真实验证,动画演示',
    '实测 mongod 的连接与线程模型:连接数从 4 加到 1003,线程数 73 → 1072(一个连接一个线程),RSS 约 73 KB/连接,关闭后线程回落但 RSS 不回落;--maxConns 50 时 44 成功 16 被拒(connections.rejected、日志 Connection refused…);available 与 --maxConns 的关系;新建连接比复用慢 7.4 倍。',
    '连接数多了会怎样?mongod 是一个连接一个线程吗?maxConns 到了会发生什么、客户端看到什么?这篇用真实的 mongod 数线程、数内存。',
    [('1072', '1000 个连接时 mongod 的线程数(基线 73)'), ('16', '--maxConns 50 时被拒绝的连接数'), ('7.4×', '每次新建连接相对复用连接的耗时')],
    [('一个连接一个线程', '<p>连接从 4 加到 1003,线程数从 73 加到 1072,RSS 每个连接增加约 73 KB。</p>'),
     ('关闭之后', '<p>连接关闭后线程数很快回落,RSS 却停在 142 MB 左右没有还给系统。</p>'),
     ('maxConns', '<p><code>--maxConns 50</code> 时第 45 个起的连接被拒,客户端看到连接被关闭或重置,服务端 <code>connections.rejected</code> 增加并打日志。</p>'),
     ('available', '<p><code>current + available</code> 等于 <code>--maxConns</code>;默认是 209,715。</p>'),
     ('新建连接的代价', '<p>每次新建连接的 find 是复用连接的 7.4 倍(309 μs 对 42 μs)。</p>'),
     ('current / active / threaded', '<p><code>threaded</code> 等于 <code>current</code>;<code>active</code> 随正在执行的操作增减。</p>')],
    steps,
    [ENV_M + '。单机 mongod,原始 TCP 连接加手写 OP_MSG hello;线程数用 ps -M,RSS 用 ps -o rss',
     '没有验证:Linux 上线程栈大小与 ulimit -u 对连接上限的影响;maxConns 之外的 ulimit -n(文件描述符)限制;连接风暴下的 establishmentRateLimit;有 TLS 时每个连接的开销;mongos 的连接模型(connPoolMaxShardedConnsPerHost 等);默认 209,715 这个值的来源(没有查源码);RSS 不回落是否因分配器缓存,没有进一步验证'],
    '连接数与线程模型')
