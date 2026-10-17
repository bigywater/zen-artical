from lib import *
R = J('z4'); f = R['first']; s = R['second']; iu = R['inuse']
def S(k): return [l for l in out('z4').split('== ')[k].splitlines()[1:] if l.strip()]
import re
LOADED = next(re.search(r'loaded in (\d+) ms', m).group(1) for t, d, m in s['ms'] if 'Snapshot loaded' in m)
steps = [
    step("第一次启动(空数据目录)的日志里程碑,时间是相对第一行日志的毫秒:+0 读配置;+4 ms 提示「Either no config or no quorum defined in config, running in standalone mode」并转交给 ZooKeeperServerMain(没有 server.N 就是单机);+32 ms 创建服务实例,日志里带着 tickTime 与会话超时范围;+41 ms 绑定客户端端口;+50 ms 快照加载(空)并马上写一份新快照;+58 ms 请求处理链的第一环 PrepRequestProcessor 启动。整个过程不到 100 ms。", t=tl(S(1)[:9]), done=[0, 1, 2, 3, 4, 5, 6, 7, 8], b=bars([[d[:12], t, f'+{t} ms'] for t, d, m in f['ms']], 100, done=list(range(len(f['ms'])))), kv=KV([['单机分支', 'QuorumPeerMain → ZooKeeperServerMain'], ['耗时', '约 90 ms(日志内部)']], ['单机分支'])),
    step(f"写入 6000 个 znode 后重启:多了一步「Reading snapshot」,然后 Snapshot loaded in {LOADED} ms,最大 zxid 是 {s['zxid']};重启后 znode 数 6005,与停机前一致。启动流程是「读配置 → 创建服务 → 绑定端口 → 载入快照(+事务日志回放)→ 启动请求处理链」。", t=tl(S(2)[:11]), done=[5, 6, 7], kv=KV([['有数据时', '多一步读快照 / 回放日志']], ['有数据时'])),
    step(f"数据目录 version-2 里的文件:{', '.join(R['files'][:6])} 等——log.* 是事务日志、snapshot.* 是快照,名字里的十六进制是 zxid(第 5 篇展开)。", t=tl([S(2)[-1]]), kv=KV([['version-2', 'log.* + snapshot.*']], ['version-2'])),
    step(f"端口被占用时:另一个进程已监听 7301,再启动 ZooKeeper,日志是「ERROR … Unexpected exception, exiting abnormally」「java.net.BindException: Address already in use」「Exiting JVM with code 1」,进程退出码 {iu['code']}。启动失败时进程会退出,不会半死不活地留着。", t=tl(S(3)), mark=[0, 1, 2], kv=KV([['绑定失败', '进程退出,退出码 1']], ['绑定失败'])),
]
A = dict(
    n=4, series='zookeeper', tags='ZooKeeper,启动流程,日志,真实验证,动画演示',
    desc='用启动日志还原 ZooKeeper 的启动流程:读配置 → 无 server.N 走单机分支 → 创建服务(带会话超时范围)→ 绑定端口 → 载入快照 → 启动请求处理链,整个日志内部约 90 ms;有数据重启多一步读快照;端口被占用时进程以退出码 1 退出。',
    lead='ZooKeeper 启动时到底做了哪些事?与其读源码,不如把它的日志按时间戳排出来。这篇用同一个节点,看空数据目录首次启动、有数据重启、端口被占用三种情形的日志里程碑。',
    facts=[('约 90 ms', '空数据目录首次启动,日志里从读配置到容器清理线程启动的总时间'), ('快照 + 日志', '有数据时多一步「Reading snapshot / Snapshot loaded」'), ('退出码 1', '端口被占用时,JVM 记录 BindException 后退出')],
    body=[
        sec('首次启动的日志里程碑', '', term('', blk('z4', 1)), '<p>单机模式其实走的也是 <code>QuorumPeerMain</code>:它发现配置里没有 <code>server.N</code>,就转交给 <code>ZooKeeperServerMain</code>。(日志里「读配置」出现了两次,就是这次转交。)</p>'),
        sec('有数据时的重启', '', term('', blk('z4', 2)), '<p>文件名里的 zxid、事务日志与快照的关系在第 5 篇看。「启动到能响应」的耗时我没有放进结论:两次测出来是同一个数字,里面包含了 JVM 启动和我轮询的间隔,没有区分度。</p>'),
        sec('端口被占用', '', term('', blk('z4', 3))),
        sec('分步演示', '', demo('启动流程', [('t', 'term', '日志'), ('b', 'bars', '相对时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。日志取自自己配置的 logback 文件输出(INFO),只摘录与启动相关的行', '没有验证:集群模式的启动流程(选举、同步,见第 34、35、42 篇)、JVM 参数对启动时间的影响、数据量很大(GB 级)时的加载耗时(第 10 篇量了 20 万 znode)、zkServer.sh 脚本做了什么'],
)
