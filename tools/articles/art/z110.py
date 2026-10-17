from lib import *
R = J('z110'); lt = R['lat']; lk = R['lock']; li = R['lock_inv']; hl = R['health']; ot = R['outage']; wt = R['watch']
def S(k): return [x for x in out('z110').split('== ')[k].splitlines()[1:] if x.strip()]
rng = lambda L: f"{min(L):.0f}–{max(L):.0f}"
steps = [
    step(f"Consul 2.0.4 三个 server,写 KV(客户端连 follower,顺序写 500 次 100 字节):中位 {lt[0]:.1f} ms、p99 {lt[1]:.1f} ms。和第 108 篇里 ZooKeeper、etcd 的数字(都在 6–7 ms)同一量级 —— 一次 fsync 主导。", t=tl(S(1)), done=[0], kv=KV([['KV 写延迟(中位)', f'{lt[0]:.1f} ms']], ['KV 写延迟(中位)'])),
    step(f"watch:Consul 用阻塞查询(GET …?index=N&wait=5s,有变化才返回,返回的是当前最新状态):16 线程并发共写 208 次,watcher 只被唤醒 {wt} 次,最后值正确。这和 ZooKeeper 的 watch 一样会合并中间的更新(第 108 篇里 etcd 的 watch 流则是每个 revision 一个事件)。", t=tl(S(2)), done=[0], kv=KV([['快速更新 208 次', f'唤醒 {wt} 次']], ['快速更新 208 次'])),
    step(f"session 与锁:持有者创建 session(TTL 10 s,Consul 允许的最小值)并用 ?acquire= 持有锁,定期续约;kill -9 后锁 key 上的 Session 在 {li['default 15s'][0]:.1f} s 才被清掉(session 失效);B 在 lock-delay=0 时 {lk['0'][0]:.1f} s 拿到锁,在默认 lock-delay(15 s)时 {lk['default 15s'][0]:.1f} s 才拿到 —— 失效后还要再等一个 15 s 的 lock-delay。对照 ZooKeeper(第 79 篇):同样 kill -9 持有者,下一个等待者约 3 s 就拿到锁。", t=tl(S(3)), mark=[0], b=bars([['ZooKeeper(会话 3 s,第 79 篇)', 2.9, '2.9 s'], ['Consul lock-delay=0', lk['0'][0], f"{lk['0'][0]:.1f} s"], ['Consul 默认 lock-delay', lk['default 15s'][0], f"{lk['default 15s'][0]:.1f} s"]], 36, mark=[2], done=[0, 1]), kv=KV([['kill -9 后别人拿到锁', f"ZK 2.9 s / Consul {lk['0'][0]:.1f}–{lk['default 15s'][0]:.1f} s"]], ['kill -9 后别人拿到锁'])),
    step(f"服务 + TTL 检查(TTL 3 s,客户端每秒续一次):kill -9 之后 /v1/health/service/svc?passing 在 {', '.join(str(x) for x in hl)} s 后不再返回该实例。和 ZooKeeper 临时节点(第 88 篇,约 3 s)在同一量级;这里是 TTL 检查超时而不是会话超时。", t=tl(S(4)), done=[0], kv=KV([['kill -9 后实例变 critical', f"{min(hl)}–{max(hl)} s"]], ['kill -9 后实例变 critical'])),
    step(f"杀掉 leader 后写入不可用的窗口(连 follower,10 ms 一次写):默认 raft 参数 {ot['default']} ms(约 {rng([x / 1000 for x in ot['default']])} s);performance.raft_multiplier=1 时 {ot['fast']} ms(约 {rng([x / 1000 for x in ot['fast']])} s)。默认参数下比 ZooKeeper(第 108 篇,约 0.3–1.1 s)与 etcd(约 1.0–1.4 s)慢得多,调小 raft_multiplier 后缩到 2 s 左右 —— 代价是更容易误判(我没有测误判)。", t=tl(S(5)), b=bars([[f'默认 第 {i+1} 次', x, f'{x/1000:.1f} s'] for i, x in enumerate(ot['default'])] + [[f'multiplier=1 第 {i+1} 次', x, f'{x/1000:.1f} s'] for i, x in enumerate(ot['fast'])], 14000, done=list(range(6))), kv=KV([['leader 切换窗口', f"默认 {rng([x / 1000 for x in ot['default']])} s / multiplier=1 {rng([x / 1000 for x in ot['fast']])} s"]], ['leader 切换窗口'])),
    step("KV 值大小:写 524288 字节(512 KiB)成功;524289 字节返回 HTTP 413「Request body too large, max size: 524288 bytes」。比 etcd(1.4 MiB 可写)与 ZooKeeper(默认约 1 MiB)都更小。", t=tl(S(6)), done=[0], kv=KV([['Consul KV 上限', '512 KiB']], ['Consul KV 上限'])),
]
A = dict(
    n=110, series='zookeeper', tags='ZooKeeper,Consul,对比,真实验证,动画演示',
    desc=f'3 节点 Consul 2.0.4 与 ZooKeeper / etcd 对比:KV 写延迟 {lt[0]:.1f} ms;阻塞查询 watch 合并更新(208 次写唤醒 {wt} 次);kill -9 锁持有者后 session {li["default 15s"][0]:.0f} s 才失效、默认 lock-delay 下 {lk["default 15s"][0]:.0f} s 才能拿锁;TTL 健康检查 {min(hl)} s;默认 leader 切换 {rng([x / 1000 for x in ot["default"]])} s;KV 上限 512 KiB。',
    lead='Consul 常被拿来和 ZooKeeper 比较:它既是 KV 又是服务发现。这篇不比功能清单,而是在同一台机器上起 3 个 Consul server,用与前面 ZooKeeper、etcd 同样的方法量写延迟、watch、session 与锁、健康检查、leader 切换和 KV 大小限制 —— 尤其是 session 与锁的实际耗时,和我原先的印象差别很大。',
    facts=[(f'{lk["default 15s"][0]:.0f} s', f'kill -9 锁持有者后,Consul 默认配置下别人拿到锁的时间(ZooKeeper 约 3 s)'), (f'{rng([x / 1000 for x in ot["default"]])} s', '杀掉 leader 后默认参数下写入不可用的窗口'), ('512 KiB', 'Consul KV 单个值的大小上限')],
    body=[
        sec('写延迟与 watch', '', term('', blk('z110', 1)), term('', blk('z110', 2)), '<p>阻塞查询与<a href="zookeeper-watcher-once.html">ZooKeeper 的一次性 watch</a>在语义上相近:都不保证每次变更都通知。</p>'),
        sec('session 与锁', '', term('', blk('z110', 3)), '<p>Consul 的 session 有最小 TTL(10 s),实测 kill -9 之后约 19 s 才失效(约为 TTL 的 2 倍,这是我观察到的数字,没有查文档),再叠加 lock-delay(默认 15 s,防止刚失效的锁被立即抢走)。<a href="zookeeper-distributed-lock.html">ZooKeeper 的锁</a>是靠会话超时(这里 3 s)释放临时节点,没有 lock-delay。这些数值都可以调(session TTL、lock-delay),我只测了默认值与 lock-delay=0。</p>'),
        sec('服务健康检查', '', term('', blk('z110', 4)), '<p>和<a href="zookeeper-service-discovery.html">用 ZooKeeper 做服务发现</a>相比,Consul 的健康是显式的「检查」概念(TTL、HTTP、脚本等),不是连接是否存活。</p>'),
        sec('leader 切换', '', term('', blk('z110', 5)), '<p>Consul 的 raft 默认参数偏保守(<code>performance.raft_multiplier</code> 默认 5),适合跨机房与不稳定网络;本机上调成 1 就快得多。</p>'),
        sec('值的大小', '', term('', blk('z110', 6))),
        sec('分步演示', '', demo('ZooKeeper vs Consul', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Consul 2.0.4(releases.hashicorp.com 的 darwin_arm64 二进制)三个 server,端口 7701+,只开 HTTP;客户端是 Python http.client;lock 与 TTL 检查的持有者是独立子进程;raft_multiplier 对比各 3 次;ZooKeeper 数字引用第 79、88、108 篇(同一台机器,方法略有不同)', '没有验证:Consul 的 DNS 接口、多数据中心(WAN)、ACL、Connect、Consul 1.x 的行为是否与 2.0 不同、session TTL 与 lock-delay 的其它取值、网络分区下的表现、大数据量的内存占用、Consul 的许可证对使用的影响(我没有核对)'],
)
