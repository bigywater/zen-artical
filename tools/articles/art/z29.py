from lib import *
R = J('z29')
def S(k): return [l for l in out('z29').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"observer 可以专门用来扩展读:连在 observer 上读 2000 次,leader 只多收到 {R['read']} 个包——读完全在 observer 本地完成,对 leader 没有压力。", t=tl(S(1)), done=[0], kv=KV([['读扩展', 'observer 分担读,不增加 leader 负担']], ['读扩展'])),
    step("同时停掉 2 个 observer:写入完全不受影响(通过投票节点写入成功,38 ms 内完成),因为它们不在多数派里。observer 的故障不会降低集群的可写性。", t=tl(S(2)), done=[0], kv=KV([['observer 故障', '不影响写入']], ['observer 故障'])),
    step(f"observer 离线期间集群写了 2000 个 znode,重启后 {R['catchup']:.0f} ms 内追上 leader 的 Zxid;leader 日志里是「Sending DIFF zxid=0x1000007d8 for peer sid: 4」——只发缺的部分。(日志里另一行 Sending DIFF zxid=0x0 for peer sid: 1 是集群最初启动时给 1 号节点的同步。)", t=tl(S(3)), b=bars([['追上用时', R['catchup'], f"{R['catchup']:.0f} ms"]], R['catchup'] * 1.3, done=[0]), kv=KV([['离线后重启', 'DIFF 追上缺的事务']], ['离线后重启'])),
]
A = dict(
    n=29, series='zookeeper', tags='ZooKeeper,Observer,读扩展,真实验证,动画演示',
    desc=f'Observer 节点实战:连在 observer 上读 2000 次 leader 只多收 {R["read"]} 个包;停掉 2 个 observer 写入不受影响;observer 离线期间错过 2000 个事务,重启 {R["catchup"]:.0f} ms 内以 DIFF 追上。',
    lead='observer 的价值在于「读扩展」和「不拖累写」:它们不投票,所以增加 observer 不会改变多数派。这篇验证几个实战里最关心的点:读是否真的不进 leader、observer 故障对写的影响、离线后怎么追上。',
    facts=[(f'+{R["read"]} 个包', '连在 observer 读 2000 次,leader 多收到的包数'), ('写入不受影响', '2 个 observer 同时停掉,投票节点仍能写'), (f'{R["catchup"]:.0f} ms', '离线期间错过 2000 个事务的 observer 重启后追上的时间(DIFF)')],
    body=[
        sec('读扩展', '', term('', blk('z29', 1))),
        sec('observer 故障', '', term('', blk('z29', 2))),
        sec('离线后重启', '', term('', blk('z29', 3))),
        sec('分步演示', '', demo('Observer 实战', [('t', 'term', '输出'), ('b', 'bars', '追上用时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 个投票节点 + 2 个 observer;读次数 2000;只测了一次', '没有验证:跨机房部署的实际收益、observer 数量很多时对 leader 发送开销的影响(第 28 篇看到有少量写延迟增加)、observer 读到的数据滞后程度'],
)
