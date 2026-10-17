from lib import *
R = J('z108'); lt = R['lat']; tp = R['tp']; w = R['watch']; dt = R['detect']; ot = R['outage']
def S(k): return [x for x in out('z108').split('== ')[k].splitlines()[1:] if x.strip()]
mz = lambda L: f"{min(L)}–{max(L)}"
steps = [
    step(f"写延迟(3 节点集群、都 fsync、客户端连 follower、顺序写 500 次 100 字节):ZooKeeper 中位 {lt['zk'][0]:.1f} ms、p99 {lt['zk'][1]:.1f} ms;etcd 中位 {lt['etcd'][0]:.1f} ms、p99 {lt['etcd'][1]:.1f} ms。两者的中位数都被一次 fsync 主导,差别不大;etcd 的客户端是我写的 HTTP/JSON 网关调用,ZooKeeper 用 kazoo,协议开销不同。", t=tl(S(1)), done=[0], b=bars([['ZooKeeper 中位', lt['zk'][0], f"{lt['zk'][0]:.1f} ms"], ['etcd 中位', lt['etcd'][0], f"{lt['etcd'][0]:.1f} ms"], ['ZooKeeper p99', lt['zk'][1], f"{lt['zk'][1]:.1f} ms"], ['etcd p99', lt['etcd'][1], f"{lt['etcd'][1]:.1f} ms"]], 20, done=[0, 1, 2, 3]), kv=KV([['中位写延迟', f"ZK {lt['zk'][0]:.1f} / etcd {lt['etcd'][0]:.1f} ms"]], ['中位写延迟'])),
    step(f"32 个线程各自独立连接并发写:ZooKeeper {tp['zk']:.0f} 次/s,etcd {tp['etcd']:.0f} 次/s。这个数字不能当作两者服务端的能力对比:etcd 这一侧走的是 Python 的 HTTP/JSON 网关,开销比 kazoo 的二进制协议大。我还试过 etcdctl 自带的 check perf 压测,结果在我的环境里 3 个 etcd 3.7.2 节点都在保存快照时 panic(failed to save snapshot … no such file or directory,原因没有查),所以吞吐只有这一对粗略数字。", t=tl(S(2)), mark=[0], b=bars([['ZooKeeper', tp['zk'], f"{tp['zk']:.0f}/s"], ['etcd(HTTP 网关)', tp['etcd'], f"{tp['etcd']:.0f}/s"]], 3500, done=[0, 1]), kv=KV([['并发写', f"ZK {tp['zk']:.0f} / etcd {tp['etcd']:.0f} 次/s(客户端协议不同)"]], ['并发写'])),
    step(f"watch:快速连续写时,ZooKeeper 的 DataWatch(用 set_async 一次发出 200 次写)只收到 {w['zk']} 次回调,最终值正确;etcd 的 watch 流(16 个线程并发共写 208 次)收到 {w['etcd']} 个事件 —— 每个 revision 一个。ZooKeeper 的 watch 一次性,收到通知到重新注册之间的更新被合并;etcd 的 watch 是持续的流,每个变更都有自己的 revision。", t=tl(S(3)), done=[0], b=bars([['ZooKeeper 回调', w['zk'], str(w['zk'])], ['etcd 事件', w['etcd'], str(w['etcd'])]], 220, mark=[0], done=[1]), kv=KV([['快速更新', f"ZK {w['zk']} 次回调 / etcd {w['etcd']} 个事件"]], ['快速更新'])),
    step(f"发现客户端崩溃:客户端(独立子进程)持有 ZooKeeper 会话(3 s)或 etcd 租约(TTL 3 s)和绑定它的 key,kill -9 后 key 消失的时间:ZooKeeper {dt['zk']} s,etcd {dt['etcd']} s。都接近 TTL;两者的失效检测模型相同:靠超时。", t=tl(S(4)), done=[0], kv=KV([['kill -9 后 key 消失', f"ZK {mz(dt['zk'])} s / etcd {mz(dt['etcd'])} s"]], ['kill -9 后 key 消失'])),
    step(f"杀掉 leader 后写入的不可用窗口(一个线程每 10 ms 写一次,连着一个 follower):ZooKeeper(tickTime=1000){ot['zk']} ms;etcd(默认 heartbeat 100 ms / election 1000 ms){ot['etcd']} ms。两者都是 1 秒左右的量级;etcd 的选举超时默认值更保守,ZooKeeper 这里是 4 次测量的范围,没有重复更多次。", t=tl(S(5)), b=bars([[f'ZK 第 {i+1} 次', x, f'{x} ms'] for i, x in enumerate(ot['zk'])] + [[f'etcd 第 {i+1} 次', x, f'{x} ms'] for i, x in enumerate(ot['etcd'])], 2000, done=list(range(8))), kv=KV([['leader 切换窗口', f"ZK {mz(ot['zk'])} / etcd {mz(ot['etcd'])} ms"]], ['leader 切换窗口'])),
    step("单个值的大小:etcd 写 1.0 MiB、1.4 MiB 成功;2.0 MiB 被拒绝(gRPC 报 received message larger than max 2097163 vs 2097152 —— 在更严格的 etcd 请求大小检查之前就被 gRPC 层挡住)。ZooKeeper 默认 jute.maxbuffer 约 1 MiB(第 1、24 篇)。两者都不适合存大对象。", t=tl(S(6)), done=[0], kv=KV([['etcd', '1.4 MiB 可,2.0 MiB 拒绝'], ['ZooKeeper', '默认约 1 MiB']], ['etcd'])),
]
A = dict(
    n=108, series='zookeeper', tags='ZooKeeper,etcd,对比,真实验证,动画演示',
    desc=f'3 节点 ZooKeeper 与 3 节点 etcd 3.7.2 同机对比:写延迟中位 {lt["zk"][0]:.1f} vs {lt["etcd"][0]:.1f} ms;快速更新时 watch 收到 {w["zk"]} 次回调 vs {w["etcd"]} 个事件;崩溃发现 {mz(dt["zk"])} vs {mz(dt["etcd"])} s;杀 leader 窗口 {mz(ot["zk"])} vs {mz(ot["etcd"])} ms;etcd 值上限 1.4 MiB 可、2 MiB 拒绝。',
    lead='ZooKeeper 和 etcd 都是「小而强一致的协调存储」,最常被拿来比较。这篇不列特性对照表,而是在同一台机器上各起 3 个节点,在同样的 fsync 条件下量写延迟、并发写、watch 在快速更新下的语义、崩溃发现、杀 leader 的窗口和单值大小。注意客户端协议不同带来的偏差,吞吐只作粗略参考。',
    facts=[(f'{w["zk"]} vs {w["etcd"]}', '快速更新时 ZooKeeper 回调数 vs etcd 事件数(etcd 每个 revision 一个事件)'), (f'{lt["zk"][0]:.1f} vs {lt["etcd"][0]:.1f} ms', '写延迟中位(都由一次 fsync 主导)'), (f'{mz(ot["zk"])} vs {mz(ot["etcd"])} ms', '杀 leader 后写入不可用的窗口')],
    body=[
        sec('写延迟', '', term('', blk('z108', 1))),
        sec('并发写', '', term('', blk('z108', 2)), '<p>ZooKeeper 的写吞吐受 leader 的单线程提交与 fsync 限制(见<a href="zookeeper-latency.html">延迟与吞吐</a>)。这里 etcd 的数字被 HTTP 网关拉低,不要据此判断服务端。</p>'),
        sec('watch 语义', '', term('', blk('z108', 3)), '<p>ZooKeeper 的 <a href="zookeeper-watcher-once.html">watch 是一次性的</a>,etcd 的 watch 是带 revision 的持续流。需要「不漏任何变更」的场景(例如 Kubernetes 的 controller),etcd 的模型更合适;只关心最终状态的配置推送,两者都够用。</p>'),
        sec('崩溃发现', '', term('', blk('z108', 4))),
        sec('leader 切换', '', term('', blk('z108', 5)), '<p>ZooKeeper 的数字对照<a href="zookeeper-leader-reelection.html">Leader 重选举</a>那篇(那里连的不是 follower,窗口更短)。</p>'),
        sec('值的大小', '', term('', blk('z108', 6))),
        sec('分步演示', '', demo('ZooKeeper vs etcd', [('t', 'term', '输出'), ('b', 'bars', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。ZooKeeper 3.9.6 三节点(forceSync=yes,tickTime=1000)与 etcd 3.7.2 三节点(默认配置,HTTP/JSON gRPC 网关),同一台机器、同一块磁盘、6 个服务端进程;ZooKeeper 客户端 kazoo,etcd 客户端是 Python http.client(keep-alive);每项只测了一轮', '没有验证:跨机房延迟、etcd 的 gRPC 原生客户端下的吞吐、etcd 的压缩与 defrag、大数据量(百万 key)下的内存与恢复时间、etcdctl check perf 导致 panic 的原因、ZooKeeper 与 etcd 在网络分区下的行为差异(见第 47 篇只验证了 ZooKeeper)'],
)
