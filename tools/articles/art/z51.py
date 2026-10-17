from lib import *
R = J('z51'); su = R['scale_up']
def S(k): return [l for l in out('z51').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"3 节点集群里有 20000 个 znode;一条 reconfig -add 同时加入 4、5 号节点(返回 {su['members']} 个成员),再启动它们:{su['ms']:.0f} ms 后两个新节点都追上,5 个节点的 znode 数都是 20005;leader 日志里给新节点的是 {', '.join(su['kinds'])}——空数据的新节点用快照同步。", t=tl(S(1)), done=[0, 1], kv=KV([['3 → 5', f"{su['ms']:.0f} ms,快照同步"], ['数据', '20005 个 znode 全部一致']], ['3 → 5'])),
    step(f"扩容之后容错能力提高:同时杀掉 leader 和另一个节点(5 个里挂 2 个),存活 3 个仍能写({R['tol5']})。3 节点时杀 2 个就不能写了(第 30 篇)。", t=tl(S(2)), done=[0], kv=KV([['5 节点', '挂 2 个仍可写']], ['5 节点'])),
    step(f"缩容回 3 节点:reconfig -remove 4,5 返回成员 {', '.join(su and R['scale_down'])};停掉 4、5 号进程后,再杀 3 个节点里的 2 个:{'还能写' if R['tol3'] else '不能写'}——容错能力随成员数回到容忍 1 个故障。扩缩容不需要重启 1~3 号节点。", t=tl(S(3)), done=[0, 1], kv=KV([['5 → 3', '成员数变,容错能力跟着变'], ['不重启', '原有节点无需重启']], ['5 → 3'])),
]
A = dict(
    n=51, series='zookeeper', tags='ZooKeeper,扩容,缩容,reconfig,真实验证,动画演示',
    desc=f'集群扩容与缩容实测(动态配置):3 → 5 节点一条 reconfig 加入 2 个节点,20000 个 znode 用 {", ".join(su["kinds"])} 同步,{su["ms"]:.0f} ms 追上;5 节点挂 2 个仍可写;reconfig -remove 4,5 缩回 3 节点后又只能容忍 1 个故障。',
    lead='要把集群从 3 个节点扩到 5 个,不用重启现有节点。这篇用动态配置做一次完整的 3 → 5 → 3,看新节点怎么同步数据、容错能力怎么变化。',
    facts=[(f'{su["ms"]:.0f} ms', '两个空节点同步 20000 个 znode 并成为 follower 的时间'), ('SNAP', '空节点加入时 leader 发整份快照'), ('容错 1 → 2 → 1', '3 → 5 → 3 节点时能容忍的故障数')],
    body=[
        sec('3 → 5', '', term('', blk('z51', 1))),
        sec('5 节点的容错', '', term('', blk('z51', 2))),
        sec('5 → 3', '', term('', blk('z51', 3))),
        sec('分步演示', '', demo('扩容与缩容', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。动态配置伪集群,JVM 堆 256 MiB;20000 个 znode(100 字节);reconfig 用官方 CLI', '没有验证:生产环境逐个增加节点的推荐做法、同时增加过多节点时对 leader 的压力、从 5 缩到 3 时选 leader 的情形、客户端连接串的同步更新'],
)
