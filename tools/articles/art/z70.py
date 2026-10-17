from lib import *
R = J('z70'); z57 = J('z57'); z58 = J('z58')
def S(k): return [l for l in out('z70').split('== ')[k].splitlines()[1:] if l.strip()]
t = S(1)
steps = [
    step("A. 集群没有多数派(3 个节点只起了 1 个):客户端 KazooTimeoutError;第一条命令 srvr → 「This ZooKeeper instance is not currently serving requests」;日志里反复出现「Cannot open channel to 3 at election address /127.0.0.1:7502」(连不上其它成员的选举端口)。→ 先确认其它节点是否起来、选举端口是否可达(第 30、47 篇)。", t=tl(t[:6]), done=[2], mark=[1], kv=KV([['症状', '客户端连接超时'], ['日志关键字', 'Cannot open channel']], ['日志关键字'])),
    step("B. 单个 IP 连接数超限(maxClientCnxns=3):客户端连接超时,四字命令本身也被拒绝;服务端日志「Error accepting new connection: Too many connections from /127.0.0.1 - max is 3」。→ 看日志而不是客户端报错(第 19 篇)。", t=tl(t[6:11]), mark=[0], done=[3], kv=KV([['日志关键字', 'Too many connections']], ['日志关键字'])),
    step("C. 写变慢:先看 mntr 的 zk_avg_fsynctime / zk_max_fsynctime(本例 2.4 / 9 ms);日志里的告警「fsync-ing the write ahead log in SyncThread:0 took 3ms which will adversely effect operation latency. File size is 67108880 bytes.」(这里为了触发把阈值调到 1 ms)。→ 写慢先查磁盘 fsync(第 55、56 篇)。", t=tl(t[11:17]), done=[2, 3, 4], kv=KV([['指标', 'zk_avg_fsynctime'], ['日志关键字', 'fsync-ing the write ahead log']], ['日志关键字'])),
    step("D. 会话过期(服务端被暂停 7 秒、会话超时 4 秒):客户端状态 SUSPENDED → LOST → CONNECTED,临时节点被删除;服务端日志「Invalid session 0x… for client /127.0.0.1:…, probably expired」(客户端带着旧会话重连时被拒绝)。→ 查 GC 停顿、网络抖动、会话超时设置(第 13、62 篇)。", t=tl(t[17:23]), done=[0, 2], mark=[1], kv=KV([['日志关键字', 'Invalid session … probably expired']], ['日志关键字'])),
    step("E. 请求超过 jute.maxbuffer(写 2 MiB 的 znode):客户端只有 ConnectionLoss;服务端日志「java.io.IOException: Len error. A message from /127.0.0.1:… with advertised length of 2097203 is either a malformed message or too large to process」。→ 看服务端日志(第 24 篇)。", t=tl(t[23:]), mark=[0], done=[2], kv=KV([['日志关键字', 'Len error']], ['日志关键字'])),
    step(f"F. 磁盘满(第 57 篇):客户端 ConnectionLoss,服务端日志「Severe unrecoverable error, from thread : SyncThread:0」「java.io.IOException: No space left on device」,进程退出(退出码 {z57['exit']});重启还要有比数据更大的可用空间。G. 启动失败(第 58 篇):「No snapshot found, but there are log entries. Something is broken!」(无快照)、「java.io.IOException: CRC check failed」(日志损坏)。", t=tl(['磁盘满:' + z57['log'][0], '磁盘满:' + z57['log'][1], '启动失败:' + z58['nosnap']['log'][-2], '启动失败:' + z58['logmid']['log'][-2]]), mark=[0, 1, 2, 3], kv=KV([['日志关键字', 'Severe unrecoverable error / CRC check failed']], ['日志关键字'])),
]
A = dict(
    n=70, series='zookeeper', tags='ZooKeeper,故障排查,运维,日志,真实验证,动画演示',
    desc='ZooKeeper 生产故障排查速查:真实造出的 5 类故障(没有多数派、连接数超限、写变慢、会话过期、请求超过 jute.maxbuffer),每类都给出客户端症状、第一条命令和服务端日志里的关键行,并链接到磁盘满、启动失败两篇的日志关键字。',
    lead='生产上出问题时,客户端往往只有一个 ConnectionLoss 或超时,真正的原因在服务端日志里。这篇把前面实验里造出来的几类故障整理成一张速查表:症状 → 第一条命令 → 日志关键字。每一行日志都是真实造出来的。',
    facts=[('只看客户端不够', 'ConnectionLoss / 超时的真正原因几乎都在服务端日志'), ('5 类现造 + 2 类引用', '没有多数派、连接超限、写慢、会话过期、请求过大;磁盘满、启动失败引自第 57、58 篇'), ('日志关键字', 'Cannot open channel / Too many connections / fsync-ing / Invalid session / Len error')],
    body=[
        sec('速查表', '', term('', blk('z70', 1)), '<p>这张表不替代前面各篇的细节,是把「现象 → 去哪里看」放在一起。排查时的通用顺序:(1)<code>srvr</code> 看节点是否在服务及角色;(2)<code>mntr</code> 看延迟 / 积压 / 连接数;(3)服务端日志按关键字搜;(4)对照客户端的状态变化(SUSPENDED / LOST)。</p>'),
        sec('引用前面的故障', '', '<p>磁盘满与启动失败的日志关键字直接取自第 57、58 篇保存的实验输出,没有重新造一遍。</p>'),
        sec('分步演示', '', demo('故障排查', [('t', 'term', '日志'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。每类故障用一个新节点造出;会话过期用 SIGSTOP 暂停服务端;fsync 告警用 -Dzookeeper.fsync.warningthresholdms=1 触发', '没有验证:真实生产环境的复杂场景(多个故障叠加)、日志级别调到 DEBUG 之后的排查信息、Kubernetes / 云环境特有的问题(DNS、Pod IP 变化)'],
)
