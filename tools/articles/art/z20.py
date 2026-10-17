from lib import *
R = J('z20')
def S(k): return [l for l in out('z20').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("构造「请求已经被服务端执行、响应在回来的路上丢了」的情形:客户端连到我写的 TCP 代理,请求照常转给服务端,服务端的响应被丢弃,随后代理断开连接。客户端收到的是 ConnectionLoss——它无法知道请求到底有没有执行。创建普通节点 /job:第一次调用 ConnectionLoss,但服务端实际已经有 /job;客户端重试 create → NodeExistsError。", t=tl(S(1)), mark=[0], done=[1], kv=KV([['ConnectionLoss', '结果未知:可能已经成功'], ['重试 create', 'NodeExists(其实已成功)']], ['ConnectionLoss'])),
    step("顺序节点最危险:创建 /seq/task- 的响应丢了,服务端已经创建了 task-0000000000;客户端重试,又创建出 task-0000000001——同一个任务被创建了两次。顺序节点不是幂等的,重试之前必须先确认第一次是否成功(比如在节点名里带一个唯一的请求 id,重试前先 get_children 查找)。", t=tl(S(2)), mark=[1], kv=KV([['顺序节点重试', '会产生重复节点']], ['顺序节点重试'])),
    step("带版本的 set(set -v):第一次已经把 version 推进到 1,重试用同一个旧 version → BadVersionError。delete:重试 → NoNodeError。这些「失败」恰恰说明第一次已经成功,处理时要把 BadVersion / NoNode 当成「可能已成功」而不是「别人抢先了」。", t=tl(S(3) + S(4)), mark=[2, 5], kv=KV([['set(version)', '重试 BadVersion'], ['delete', '重试 NoNode']], ['set(version)'])),
    step("不带版本的覆盖写 set:响应丢失后重试是安全的,最终数据一样(z);代价是节点的 version 被推进了两次(从 0 到 2)——数据幂等,版本号不幂等,依赖版本号做判断的逻辑要小心。", t=tl(S(5)), done=[1, 2], kv=KV([['覆盖写', '数据幂等'], ['version', '被推进两次']], ['覆盖写'])),
]
A = dict(
    n=20, series='zookeeper', tags='ZooKeeper,幂等,重试,ConnectionLoss,真实验证,动画演示',
    desc='请求幂等与重试语义实测(用 TCP 代理构造响应丢失):ConnectionLoss 后服务端其实已执行;重试 create 得 NodeExists,重试带版本的 set 得 BadVersion,重试 delete 得 NoNode,重试顺序节点会创建出第二个节点;覆盖写重试数据一致但 version 被多推一次。',
    lead='客户端收到 ConnectionLoss 时,请求到底成功了没有?这是 ZooKeeper 使用中最容易出错的地方。这篇用一个会丢弃响应的 TCP 代理构造「服务端执行了、客户端不知道」的情形,看每种操作重试时会发生什么。',
    facts=[('ConnectionLoss', '结果未知:请求可能已经被服务端执行'), ('重试顺序节点', '会创建出第二个节点,没有幂等性'), ('BadVersion / NoNode', '重试带版本的写或 delete 得到的错误,可能意味着「第一次其实成功了」')],
    body=[
        sec('构造响应丢失', '', term('', blk('z20', 1)), '<p>真实环境里的网络抖动、服务端切换都会造成这种情形。这里的代理是我用 Python 写的:转发客户端请求、丢弃服务端响应、随后断开连接,让客户端必然看到 ConnectionLoss。</p>'),
        sec('顺序节点', '', term('', blk('z20', 2))),
        sec('版本号与删除', '', term('', blk('z20', 3) + '\n' + blk('z20', 4))),
        sec('覆盖写', '', term('', blk('z20', 5))),
        sec('怎么办', '', '<p>总结实测出来的规律:操作能不能安全重试,取决于它是不是「重放结果不变」。覆盖写数据是,顺序节点创建不是,带版本的写需要把 BadVersion 当作「可能已成功」处理。通用做法是让每个请求带一个唯一标识(写进节点数据或节点名),重试前先查询是否已经落地。这是设计建议,本文只验证了上面的现象,没有验证具体的去重方案。</p>'),
        sec('分步演示', '', demo('重试语义', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。代理是 zkl.Proxy(drop_resp 丢弃服务端响应后 close_all),客户端 kazoo;每个场景只构造一次丢失', '没有验证:kazoo / Curator 内置重试策略的实际行为(第 97 篇)、会话过期后重试、集群里切换 leader 时的重复提交、multi 操作的重试(第 21 篇)'],
)
