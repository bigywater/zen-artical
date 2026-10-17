from lib import *
R = J('z44'); zs, es, eo = R['zk_stale'], R['etcd_stale'], R['etcd_outage']
def S(k): return [l for l in out('z44').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"ZooKeeper 的读默认在本地完成,理论上可能读到旧值。实测:客户端 A 在一个 follower 上写,B 在另一个 follower 上读,写返回后马上读,3000 次里读到旧值 {zs['nosync']} 次;每次读前先 sync() 也是 {zs['sync']} 次。这个测法下没有观察到旧读——我不能据此说旧读不会发生(我的循环有 Python 往返的间隔,给了 follower 时间应用提交),只能说没有复现。", t=tl(S(1)), mark=[0], kv=KV([['旧读', '3000 次 0 次(没复现,不代表不会发生)']], ['旧读'])),
    step(f"etcd(Raft)的对照:默认读是线性一致的,3000 次旧读 {es['lin']} 次;serializable 读(在 follower 本地完成,类似 ZooKeeper 的本地读)旧读 {es['ser']} 次(约 {es['ser'] / 30:.0f}%)。所以「读是否经过多数派确认」是两者在读语义上的核心差别:ZooKeeper 默认本地读(要线性一致需 sync + 读),etcd 默认线性一致读。", t=tl(S(2)), b=bars([['etcd 线性一致', es['lin'], str(es['lin'])], ['etcd serializable', es['ser'], str(es['ser'])], ['ZooKeeper 本地读', zs['nosync'], str(zs['nosync'])]], max(es['ser'], 10) * 1.1, mark=[1], done=[0, 2]), kv=KV([['etcd 默认', '线性一致读'], ['etcd serializable', f"{es['ser']} / 3000 旧读"]], ['etcd serializable'])),
    step(f"leader 被杀后恢复写入:etcd 3 节点(默认 election-timeout 1000 ms)写不可用中位 {eo['med']:.0f} ms(范围 {eo['mn']:.0f}–{eo['mx']:.0f} ms),每次 raftTerm +1;ZooKeeper 3 节点(tickTime 默认 2000 ms)第 36 篇测得中位约 445 ms。两者的选举机制不同:Raft 靠随机化的选举超时触发选举,ZooKeeper 靠连接断开 / 心跳超时发现 leader 丢失后用 zxid + sid 选票选举。这些数字是各自默认配置下的结果,不是公平的性能比较。", t=tl(S(3)), b=bars([['etcd(默认配置)', eo['med'], f"{eo['med']:.0f} ms"], ['ZooKeeper(默认配置)', 445, '≈ 445 ms']], eo['med'] * 1.1, mark=[0], done=[1]), kv=KV([['etcd', f"写中断中位 {eo['med']:.0f} ms"], ['ZooKeeper', '写中断中位约 445 ms(第 36 篇)']], ['etcd'])),
]
A = dict(
    n=44, series='zookeeper', tags='ZooKeeper,ZAB,Raft,etcd,真实验证,动画演示',
    desc=f'ZAB 与 Raft 的区别(ZooKeeper 3.9.6 与 etcd 3.7.2 实测):ZooKeeper 本地读没有复现旧读(0/3000);etcd 线性一致读 0/3000、serializable 读 {es["ser"]}/3000 旧读;杀 leader 后写中断 etcd 中位 {eo["med"]:.0f} ms vs ZooKeeper 约 445 ms(默认配置)。',
    lead='ZAB 和 Raft 都是「leader + 多数派」的协议,有什么区别?这篇不比较论文,而是各起一个真实集群:ZooKeeper 3 节点和 etcd 3 节点,测读语义和 leader 故障后的写中断,看实际表现的差异。',
    facts=[(f'{es["ser"]} / 3000', 'etcd serializable 读(follower 本地)读到旧值的次数;线性一致读为 0'), ('0 / 3000', 'ZooKeeper 本地读我没有复现出旧读(不代表不会发生)'), (f'{eo["med"]:.0f} ms vs 445 ms', 'leader 被杀后写中断:etcd vs ZooKeeper(各自默认配置)')],
    body=[
        sec('ZooKeeper 的本地读', '', term('', blk('z44', 1)), '<p>ZooKeeper 文档说 follower 上的读可能落后于最新写(顺序一致而不是线性一致),<code>sync()</code> 用来补救。我在单机多进程环境下没能复现旧读,所以这里只能报告「没观察到」。</p>'),
        sec('etcd 的读', '', term('', blk('z44', 2)), '<p>etcd 通过 JSON HTTP 网关访问(<code>serializable: true</code> 选择本地读)。</p>'),
        sec('leader 故障后的写中断', '', term('', blk('z44', 3)), '<p>两个系统的默认超时不同(etcd 选举超时 1000 ms、心跳 100 ms;ZooKeeper tickTime 2000 ms),调小之后差距会变。更完整的 etcd 对比见第 108 篇。</p>'),
        sec('分步演示', '', demo('ZAB 与 Raft', [('t', 'term', '输出'), ('b', 'bars', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。etcd 3.7.2(brew 安装)3 节点集群,端口 7600+,默认选举配置,通过 HTTP JSON 网关读写;测试都是同一台机器上的 3 个进程', '没有验证:两个协议在日志复制、成员变更、快照上的差异(只比较了读语义与故障恢复)、更大的集群、网络分区下的表现、etcd 调小选举超时后的结果'],
)
