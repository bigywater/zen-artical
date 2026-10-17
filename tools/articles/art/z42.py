from lib import *
R = J('z42')
def S(k): return [l for l in out('z42').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"follower 只落后一点点(10 个事务)重启:leader 日志是「Synchronizing with Learner sid: 1 maxCommittedLog=0x10000000c minCommittedLog=0x100000001 …」然后「Sending DIFF zxid=0x10000000c for peer sid: 1」,follower 一侧是「following - synchronization - diff」,追上用时 {R['diff']['ms']:.0f} ms。DIFF = 只把缺的事务发过去。", t=tl(S(1)), done=[1, 2], kv=KV([['DIFF', '补发缺的事务']], ['DIFF'])),
    step(f"follower 的数据被清空(换了新盘)再加入:leader 日志里 peerLastZxid=0x0,发送的是「Sending snapshot last zxid of peer is 0x0, zxid of leader is …」,follower 一侧是「synchronization - snap」,追上用时 {R['snap']['ms']:.0f} ms。SNAP = 把整份快照发过去(新节点、数据全丢的节点都用它)。", t=tl(S(2)), done=[1, 2], kv=KV([['SNAP', '整份快照']], ['SNAP'])),
    step("旧 leader 被网络隔离(代理丢包),隔离期间有一个写(create /extra)被它收下,但多数派一侧选出了新 leader 并继续写 /after;网络恢复后旧 leader 重新加入,新 leader 日志是「Cannot send TRUNC to peer sid: … peer zxid is from different epoch」「Unhandled scenario for peer sid: … fall back to use snapshot」「Sending snapshot last zxid of peer is 0x100000003, zxid of leader is 0x200000002」。我原以为会看到 TRUNC(截断旧 leader 多出来的事务),实测是因为旧 leader 的 zxid 来自旧 epoch,新 leader 不能发 TRUNC,退回到发整份快照。", t=tl(S(3)), mark=[2, 3, 4], done=[5], kv=KV([['TRUNC', '没有观察到(zxid 来自不同 epoch)'], ['实际', '回退成 SNAP']], ['实际'])),
    step("结果正确:旧 leader 重新加入后,读 /extra 是 None(那个从未被多数派确认的写不存在),读 /after 得到 2;当初发给旧 leader 的那次 create 调用,客户端得到的是 ConnectionLoss。", t=tl(S(3)[-2:]), done=[0, 1], kv=KV([['未被多数派确认的写', '消失,客户端得到 ConnectionLoss']], ['未被多数派确认的写'])),
]
A = dict(
    n=42, series='zookeeper', tags='ZooKeeper,ZAB,DIFF,SNAP,TRUNC,真实验证,动画演示',
    desc='ZAB 日志同步实测:follower 略微落后 → DIFF;数据被清空 → SNAP(整份快照);旧 leader 带着从未被确认的写重新加入时,新 leader 日志里「Cannot send TRUNC … peer zxid is from different epoch」并回退为 SNAP,那条未确认的写消失。',
    lead='follower 落后或者数据不一致时,leader 怎么让它追上?文档说有 DIFF、TRUNC、SNAP 三种。这篇逐一制造:略落后、数据丢光、旧 leader 带着未提交的写回来,看 leader 日志里实际选了哪种。',
    facts=[('DIFF', 'follower 略落后:只补缺的事务'), ('SNAP', '数据被清空:发整份快照'), ('没看到 TRUNC', '旧 leader 的 zxid 来自旧 epoch → 回退成 SNAP')],
    body=[
        sec('DIFF', '', term('', blk('z42', 1))),
        sec('SNAP', '', term('', blk('z42', 2))),
        sec('旧 leader 带着未确认的写回来', '', term('', blk('z42', 3)), '<p>隔离是用我写的 TCP 代理实现的(节点间通信悄悄丢包)。旧 leader 收下 /extra 之后,因为没有多数派 ack,这条事务从未提交;新 leader 的 epoch 更高,旧 leader 日志里的多余事务在重新加入时被快照覆盖。</p>'),
        sec('分步演示', '', demo('DIFF / SNAP / TRUNC', [('t', 'term', '日志'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;隔离用 zkl.NetEnsemble(每对节点之间 quorum / 选举连接各经过一个 TCP 代理,丢包不断连);tickTime=500、syncLimit=2', '没有验证:同一 epoch 内 follower 多出事务时 TRUNC 的触发条件(没有构造出来)、leader 内存里 committedLog 窗口大小的影响(我早先单独试过落后 3000 个事务,仍是 DIFF,但那次运行的输出没有保留在本文里)、snapshotSizeFactor 对选择 DIFF / SNAP 的影响'],
)
