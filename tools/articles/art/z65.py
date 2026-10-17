from lib import *
R = J('z65'); sc = R['scen']
def S(k): return [l for l in out('z65').split('== ')[k].splitlines()[1:] if l.strip()]
names = list(sc.keys())
steps = [
    step("同一个节点在四种状态下的 mntr 指标(每种状态前先 srst 清零统计):空闲时 avg_latency 0、outstanding 0、2 个连接(含查询用的 1 个)、fd 68;稳定写入(串行同步写)avg_latency 约 3 ms、avg_fsynctime 约 2 ms、max_latency 9 ms;突发(30000 个异步写)洪峰中途 outstanding_requests 采样到 22、max_latency 11 ms、packets_received 30002;300 个连接 + 6000 个 watch 时 num_alive_connections 302、watch_count 6000、open_file_descriptor_count 367(连接都占文件描述符)、读大目录后 max_client_response_size 约 315 KB。", t=tl(S(1)), done=list(range(0, 14)), kv=KV([['写入慢', 'avg_latency / avg_fsynctime'], ['积压', 'outstanding_requests'], ['规模', 'watch_count / num_alive_connections / znode_count']], ['写入慢'])),
    step("读数时要注意(都来自上面的数字):zk_max_latency 是自上次 srst 以来的最大值,要告警必须定期 srst 或看差值;zk_outstanding_requests 是瞬时值,洪峰过去就回到 0,要高频采样;watch_count、num_alive_connections 是状态量,不会随时间自己恢复;open_file_descriptor_count 要和 max_file_descriptor_count 对照(连接 + 日志 / 快照文件都占 fd)。", t=tl(S(2)), mark=[0, 1], kv=KV([['max 类指标', '会一直保留最大值,要定期重置']], ['max 类指标'])),
]
A = dict(
    n=65, series='zookeeper', tags='ZooKeeper,监控,mntr,运行时指标,真实验证,动画演示',
    desc='ZooKeeper 运行时指标监控:同一节点在空闲 / 稳定写入 / 异步突发 / 300 连接 + 6000 watch 四种状态下的 mntr 指标对比(avg_latency、outstanding_requests、num_alive_connections、watch_count、open_file_descriptor_count、avg_fsynctime…),以及 max 类指标需要定期 srst 的读数提醒。',
    lead='mntr 有四百多个指标,该盯哪几个?这篇不罗列,而是让同一个节点依次处于四种典型状态,把最常用的十几个指标并排打印,看每种状态下哪些数字会变。',
    facts=[('avg_latency / avg_fsynctime', '写入变慢时先变的指标'), ('outstanding_requests', '请求积压(瞬时值,需要高频采样)'), ('open_file_descriptor_count', '300 个连接时从 68 涨到 367')],
    body=[
        sec('四种状态下的指标', '', term('', blk('z65', 1))),
        sec('怎么读这些数', '', term('', blk('z65', 2)), '<p>如何设阈值取决于你的负载与硬件(本文没有给出推荐阈值)。监控的通用做法是:延迟看 p99 而不是平均数(mntr 只给平均 / 最大,需要 Prometheus 的分位数,第 63 篇),连接与 watch 数看趋势,积压看是否持续不降。</p>'),
        sec('分步演示', '', demo('运行时指标', [('t', 'term', '指标表'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,JVM 堆 256 MiB;每种状态前 srst 重置统计;洪峰中途的 outstanding 是在异步写进行时采样的一次', '没有验证:集群里 leader 独有的指标(synced_followers 等,第 33 篇)、告警阈值的设定、不同负载形态(读多写少)下的指标、慢磁盘下的指标变化'],
)
