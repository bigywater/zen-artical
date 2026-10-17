from lib import *
R = J('z37')
def S(k): return [l for l in out('z37').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("zxid 是 64 位数:高 32 位是 epoch(第几任 leader),低 32 位是 counter(这一任里的第几个事务)。第一任 leader 选出后三个节点的 zxid 都是 0x100000001 = epoch 1 + counter 1;写 3 个 znode 后是 0x100000004(counter 4);这三个 znode 的 czxid 依次是 0x100000002、0x100000003、0x100000004。", t=tl(S(1)), done=[0, 1, 2], kv=KV([['zxid', 'epoch(高 32 位)+ counter(低 32 位)']], ['zxid'])),
    step("杀掉 leader 选出第二任之后:zxid 变成 0x200000001(epoch 2、counter 重新从 1 开始);再写 2 个,0x200000003。第一任最后创建的 /c 的 czxid 是 0x100000004,第二任创建的 /d 是 0x200000002——后一任的 zxid 一定更大,即使 counter 更小。所以 zxid 在全局上严格单调。", t=tl(S(2)), done=[0, 1, 2], kv=KV([['换 leader', 'epoch +1,counter 重新计'], ['单调', '后一任的 zxid 一定更大']], ['单调'])),
    step(f"数据目录里:version-2 下有 acceptedEpoch 与 currentEpoch 两个文件(本例都是 {R['epochs'][0]}),记录节点接受过 / 当前所属的 epoch;事务日志文件名 {', '.join(R['files'])} 是该文件第一条事务的 zxid(所以 log.100000001 的第一个事务属于 epoch 1)。这两个纪元文件是节点重启后知道「我属于哪一任」的依据。", t=tl(S(3)), kv=KV([['acceptedEpoch / currentEpoch', '节点持久化的纪元']], ['acceptedEpoch / currentEpoch'])),
]
A = dict(
    n=37, series='zookeeper', tags='ZooKeeper,zxid,epoch,真实验证,动画演示',
    desc='zxid 设计实测:64 位 = epoch(高 32 位)+ counter(低 32 位);写 3 个 znode counter +3;换 leader 后 epoch +1、counter 重新开始(0x100000004 → 0x200000001),后一任的 zxid 一定更大;数据目录里的 acceptedEpoch / currentEpoch 文件记录纪元。',
    lead='zxid 是 ZooKeeper 里最重要的数字:每个事务一个,全局递增。这篇把它拆开看:高 32 位是什么、低 32 位是什么、换 leader 时怎么变、数据目录里和它相关的文件有哪些。',
    facts=[('epoch + counter', 'zxid = 高 32 位 epoch + 低 32 位 counter'), ('0x100000004 → 0x200000001', '换 leader 前后的 zxid(epoch 1 → 2,counter 重来)'), ('acceptedEpoch / currentEpoch', '数据目录里保存纪元的两个文件')],
    body=[
        sec('拆开一个 zxid', '', term('', blk('z37', 1))),
        sec('换 leader 之后', '', term('', blk('z37', 2))),
        sec('磁盘上的痕迹', '', term('', blk('z37', 3))),
        sec('分步演示', '', demo('zxid', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;zxid 来自 srvr 的 Zxid 与 stat 的 czxid', '没有验证:counter 达到 2^32 时的行为(没有测)、纪元文件的更新时机(第 38 篇看 epoch 增加的条件)、旧 leader 带着旧 epoch 的请求被拒绝的细节'],
)
