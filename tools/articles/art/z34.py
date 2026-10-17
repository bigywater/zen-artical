from lib import *
R = J('z34'); runs = R['runs']; md = R['med']
def S(k): return [l for l in out('z34').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"杀掉 leader 后重复 5 次(每次把被杀的节点启动回来):新 leader 出现的时间 {', '.join(str(round(x['appear'])) for x in runs)} ms,第一次写入成功 {', '.join(str(round(x['write'])) for x in runs)} ms;日志里的「LEADER ELECTION TOOK」(选举本身)是 {', '.join(str(x['took']) for x in runs)} ms。中位数:新 leader 出现 {md['appear']:.0f} ms、第一次写成功 {md['write']:.0f} ms。", t=tl(S(1)), b=bars([[f'第 {i + 1} 次写成功', x['write'], f"{x['write']:.0f} ms"] for i, x in enumerate(runs)], max(x['write'] for x in runs) * 1.1, done=list(range(len(runs)))), kv=KV([['中位数', f"新 leader {md['appear']:.0f} ms / 写成功 {md['write']:.0f} ms"], ['波动', f"{md['mn']:.0f}–{md['mx']:.0f} ms"]], ['中位数'])),
    step("选举过程里的选票交换(follower 日志里的 Notification):每个 LOOKING 的节点广播自己的选票(sid、它推荐谁当 leader、round 选举轮次、peerEpoch、zxid)。第一批通知里每个节点都先投自己(n.leader 等于 n.sid);收到别人更优的选票后改投,最终所有节点的选票指向同一个 sid——已经是 FOLLOWING / LEADING 的节点收到 LOOKING 节点的通知时,会把已有的 leader 告诉它。", t=tl(S(2)), kv=KV([['选票', 'sid / leader / round / peerEpoch / zxid'], ['先投自己', '再按比较规则改投']], ['选票'])),
]
A = dict(
    n=34, series='zookeeper', tags='ZooKeeper,Leader选举,真实验证,动画演示',
    desc=f'Leader 选举过程实测(3 节点,杀 leader 5 次):新 leader 出现中位 {md["appear"]:.0f} ms,第一次写入成功中位 {md["write"]:.0f} ms(范围 {md["mn"]:.0f}–{md["mx"]:.0f} ms);日志里的 Notification 展示选票交换:先投自己,再按比较规则改投。',
    lead='leader 挂了之后,多久能恢复?选举里节点之间到底发了什么?这篇重复杀 leader 5 次,量新 leader 出现和写入恢复的时间,再把一次选举里的选票交换从日志里摘出来。',
    facts=[(f'{md["write"]:.0f} ms', '杀 leader 到第一次写入成功的中位时间(3 节点,本机)'), (f'{md["mn"]:.0f}–{md["mx"]:.0f} ms', '5 次的范围,有一次明显更慢'), ('Notification', '日志里每条选票的字段:sid、leader、round、peerEpoch、zxid')],
    body=[
        sec('恢复时间', '', term('', blk('z34', 1)), '<p>5 次里有一次明显更慢(选举耗时 641 ms 对其它的 211–225 ms),说明选举的耗时有波动,不要把中位数当作上限。</p>'),
        sec('选票交换', '', term('', blk('z34', 2)), '<p>选票比较的规则(先 epoch、再 zxid、最后 sid)在第 35 篇单独验证。</p>'),
        sec('分步演示', '', demo('Leader 选举', [('t', 'term', '输出'), ('b', 'bars', '写成功时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群,tickTime=2000;「新 leader 出现」用 srvr 轮询,「写成功」用临时节点创建 / 删除;5 次重复', '没有验证:跨机器网络下的选举时间、tickTime 与 initLimit 对选举的影响、大数据量时的同步耗时(同步阶段在第 42 篇)、选举过程里的消息细节(第 35 篇)'],
)
