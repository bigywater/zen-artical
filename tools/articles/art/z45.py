from lib import *
R = J('z45'); catch = R['catch']
def S(k): return [l for l in out('z45').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("一个 follower 离线后:3 节点集群仍有多数派(2/3),写入继续成功;leader 的 zk_synced_followers 从 2 变成 1。", t=tl(S(1)), done=[1], kv=KV([['follower 离线', '集群仍可写,synced_followers = 1']], ['follower 离线'])),
    step("离线期间错过 100、3000、30000 个写入后重启:追上用时 " + '、'.join(f"{n} 个 → {ms:.0f} ms" for n, ms, k in catch) + ";leader 日志里每次都是 DIFF(把缺的事务补发过去)。错过的越多追得越久,但从 100 到 30000 只从 570 ms 到 810 ms 左右——追赶很快。", t=tl(S(2)), b=bars([[f'错过 {n} 个', ms, f'{ms:.0f} ms'] for n, ms, k in catch], max(ms for n, ms, k in catch) * 1.2, done=[0, 1, 2]), kv=KV([['同步方式', '都是 DIFF'], ['追上用时', '570–810 ms']], ['同步方式'])),
    step(f"追上之后读到的数据与 leader 一致:根下子节点数 follower {R['same'][0]} / leader {R['same'][1]},Zxid 也相同。恢复完成后这个 follower 就能正常服务读请求。", t=tl(S(3)), done=[0], kv=KV([['恢复后', '数据与 zxid 与 leader 一致']], ['恢复后'])),
]
A = dict(
    n=45, series='zookeeper', tags='ZooKeeper,Follower,故障恢复,DIFF,真实验证,动画演示',
    desc=f'Follower 掉线后的恢复实测:离线期间集群仍可写;错过 100 / 3000 / 30000 个写入后重启,leader 都用 DIFF 同步,追上用时 {catch[0][1]:.0f} / {catch[1][1]:.0f} / {catch[2][1]:.0f} ms;恢复后数据与 zxid 与 leader 一致。',
    lead='follower 挂了一阵子再回来,要多久才能追上?用什么方式?这篇让一个 follower 离线,期间连续写入不同数量的数据,再看它重启后的追赶。',
    facts=[('DIFF', '100 到 30000 个事务的落后都用 DIFF 补发'), (f'{catch[0][1]:.0f}–{catch[2][1]:.0f} ms', '重启后追上 leader 的用时范围'), ('synced_followers 2 → 1', '离线期间 leader 的指标')],
    body=[
        sec('follower 离线', '', term('', blk('z45', 1))),
        sec('重启追赶', '', term('', blk('z45', 2)), '<p>这里的数据很小(每个 znode 50 字节),所以 3 万个事务也只需要不到一秒。大数据量下的追赶时间没有测。</p>'),
        sec('追上之后', '', term('', blk('z45', 3))),
        sec('分步演示', '', demo('follower 恢复', [('t', 'term', '输出'), ('b', 'bars', '追上用时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;离线用 kill -9;每次重启后等 zxid 与 leader 相同;写入是 kazoo 异步 create', '没有验证:落后超过事务日志保留范围时的 SNAP(第 42 篇用清空数据的方式触发了 SNAP)、大 value 的追赶耗时、多个 follower 同时落后时对 leader 的压力'],
)
