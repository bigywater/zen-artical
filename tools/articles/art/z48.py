from lib import *
R = J('z48'); mw = R['majority_write']
def S(k): return [l for l in out('z48').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"5 个节点分成 {{含旧 leader 的 2 个}} 和 {{3 个}} 两半(悄悄丢包)。每 100 ms 采样每个节点的 Mode,共 198 次:任一时刻同时报告「leader」的节点数最大是 {R['max_leaders']},出现 ≥2 个 leader 的采样 {len(R['two_samples'])} 次。旧 leader 在失去多数派之后退位(变成不服务),这之后多数派一侧才选出新 leader——这次采样里没有出现两个 leader 同时存在。", t=tl(S(1)[:2]), done=[0], kv=KV([['同时的 leader 数', f"最大 {R['max_leaders']}"]], ['同时的 leader 数'])),
    step(f"多数派一侧的客户端(带重试)写 /from-majority:{mw['ok']},分区后 {mw['ms']:.0f} ms(含故障检测与重新选举);少数派一侧(旧 leader)的客户端写 /from-minority:{R['minority_write']}。没有多数派就不能提交。", t=tl(S(1)[2:]), done=[0], mark=[1], kv=KV([['3 个节点一侧', '能写'], ['2 个节点一侧', '不能写']], ['3 个节点一侧'])),
    step(f"恢复后:/from-majority 存在({R['final']['maj']}),/from-minority 不存在({R['final']['mino']});5 个节点的 Zxid 全部相同({list(R['zxids'].values())[0]}),/from-majority 的数据在每个节点上都是 y。没有脑裂:少数派一侧没有产生任何被保留的写入。", t=tl(S(2)), done=[0, 1, 2, 3], kv=KV([['数据', '5 个节点一致'], ['脑裂', '没有出现']], ['脑裂'])),
]
A = dict(
    n=48, series='zookeeper', tags='ZooKeeper,脑裂,Quorum,网络分区,真实验证,动画演示',
    desc=f'ZooKeeper 脑裂问题实测(5 节点分成 2 | 3,悄悄丢包):198 次采样里同时报告 leader 的节点数最大为 {R["max_leaders"]};多数派一侧写入成功({mw["ms"]:.0f} ms),少数派一侧的写 {R["minority_write"]};恢复后 5 个节点 zxid 相同,少数派的写不保留。',
    lead='「脑裂」指集群分成两半、各自选出 leader、各自接受写入。ZooKeeper 靠多数派规则避免它。这篇把 5 节点集群切成 2 | 3,持续采样所有节点的角色,看会不会同时出现两个 leader。',
    facts=[(f'最大 {R["max_leaders"]}', '分区期间任一时刻同时是 leader 的节点数(198 次采样)'), ('2 | 3', '少数派一侧不能写,多数派一侧能写'), ('恢复后一致', '5 个节点 zxid 相同,少数派一侧的写入不会保留')],
    body=[
        sec('采样角色', '', term('', blk('z48', 1)), '<p>采样用 srvr 的 Mode,间隔 100 ms,所以很短(&lt;100 ms)的重叠可能看不到;这是实验方法的局限。理论上旧 leader 在发现失去多数派之前,确实仍认为自己是 leader,但它的任何写都因凑不齐多数派的 ack 而不能提交。</p>'),
        sec('分区后的数据', '', term('', blk('z48', 2))),
        sec('分步演示', '', demo('脑裂', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。5 节点伪集群,tickTime=500、syncLimit=2;分区用 zkl.NetEnsemble 的悄悄丢包模式;采样间隔 100 ms;一次实验', '没有验证:更长的分区时间、多次重复(只做了一次)、非对称分区、客户端同时连着两侧(多地址连接串)时的行为、observer 的影响'],
)
