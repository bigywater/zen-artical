from lib import *
R = J('z38')
def S(k): return [l for l in out('z38').split('== ')[k].splitlines()[1:] if l.strip()]
ops = dict(R['ops'])
steps = [
    step("counter 每个写事务 +1:create +1、set +1、delete +1;读(get、exists)+0;一个 multi 里 5 个 create 合在一起 +1;新建并立刻关闭一个会话 +2(createSession 和 closeSession 各一个事务);同一会话里再 create 一个临时节点 +1。所以 counter 数的是「事务」,不是请求。", t=tl(S(1)), done=[0, 1, 2, 5, 6, 7], mark=[3, 4], kv=KV([['写事务', '每个 +1(multi 只算 1 个)'], ['读', '+0']], ['写事务'])),
    step(f"连续杀 3 次 leader(每次把它启动回来):新 leader 的 zxid epoch 依次是 {', '.join(str(x) for x in R['epochs'])},counter 都从 0 开始——每选出一任 leader,epoch 加 1。", t=tl(S(2)), done=[0, 1, 2], kv=KV([['每任 leader', 'epoch +1']], ['每任 leader'])),
    step(f"没有多数派的 8 秒里(杀掉 2 个节点)节点反复 LOOKING;恢复后 epoch 从 {R['no_quorum'][0]} 到 {R['no_quorum'][1]},只增加了 1——选举的轮次(日志里的 n.round,本次最大 {R['rounds']})和 epoch 是两个计数,epoch 只在有 leader 成功当选时增加。", t=tl(S(3)), kv=KV([['round', '选举轮次,每次重选都增'], ['epoch', '只在成功当选后 +1']], ['epoch'])),
]
A = dict(
    n=38, series='zookeeper', tags='ZooKeeper,zxid,epoch,counter,真实验证,动画演示',
    desc=f'ZXID 的 epoch 与 counter 实测:counter 数事务(create/set/delete 各 +1,multi 整体 +1,新建 + 关闭会话 +2,读 +0);每选出一任 leader epoch +1({", ".join(str(x) for x in R["epochs"])}),counter 从 0 开始;没有多数派期间反复选举不增加 epoch,只有成功当选才 +1。',
    lead='zxid 的两半各自怎么变化?哪些操作会让 counter 增加?epoch 什么时候增加?这篇把这三个问题逐个量出来,并顺手区分 epoch 与选举轮次 round。',
    facts=[('事务才计数', 'create / set / delete 各 +1;multi 整体 +1;读 +0'), ('会话也是事务', '新建 + 关闭会话共 +2'), ('epoch 只在当选后 +1', '没有多数派时反复选举也不涨')],
    body=[
        sec('counter 数什么', '', term('', blk('z38', 1))),
        sec('epoch 什么时候增加', '', term('', blk('z38', 2) + '\n' + blk('z38', 3)), '<p>第三节里 epoch 只增加了 1,说明失败的选举轮次没有消耗 epoch(这是这一次运行的现象)。</p>'),
        sec('分步演示', '', demo('epoch 与 counter', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;counter 取自 srvr 的 Zxid 低 32 位(每步等 0.2 s 再读)', '没有验证:counter 溢出(2^32)时 leader 主动退位的行为、epoch 在极端并发选举下的取值、observer 对 zxid 的影响'],
)
