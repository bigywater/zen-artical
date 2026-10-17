from lib import *
S = SS('m53')
steps = [
    step("写 primary(w:1)后立刻读 secondary,连续 3000 轮:不带会话的读有 2052 次读到旧值(约 68%);带因果一致性会话(把每次写入的 operationTime 传给会话)的读 0 次读到旧值。", t=tl(S(1)), mark=lidx(S(1), '0 / 3000 次'), done=lidx(S(1), '不带会话'), b=bars([['不带会话', 2052, '2052 / 3000 次读到旧值'], ['因果一致性会话', 0, '0 / 3000 次']], 2052, mark=[1], done=[0]), kv=KV([['不带会话', '68% 的读落后一步'], ['因果会话', '0%,读会等 secondary 追上']], ['因果会话'])),
    step("确定性地制造落后:用 failpoint stopReplProducer 让一个 secondary 停止拉取 oplog,再写 primary。这个 secondary 上不带会话的读返回旧值(i = 5999);带因果一致性会话(operationTime 是那次写入的时间)的读等了 3,008 ms(failpoint 2 秒后关闭,secondary 再追上)才返回新值 'FRESH'——因果一致性读会等到 secondary 追上你写入的时间点。", t=tl(S(2)), mark=lidx(S(2), '等了 3008 ms'), done=lidx(S(2), 'i = 5999'), kv=KV([['不带会话', '立刻返回旧值'], ['带因果会话', '阻塞到 secondary 追上,3 秒后返回新值']], ['带因果会话'])),
    step("机制:带因果会话的 find 命令里多了 readConcern: {'afterClusterTime': Timestamp(1791775788, 1)},表示“至少要读到这个时间点之后的状态”;不带会话的 find 命令 readConcern 是 None。", t=tl(S(3)), mark=lidx(S(3), 'afterClusterTime'), done=lidx(S(3), 'None'), kv=KV([['afterClusterTime', '读命令带上的最低时间点'], ['没有会话', '没有这个参数']], ['afterClusterTime'])),
    step("会话怎么知道要等到哪里:每次响应里的 operationTime 被会话记下。s1 写入后 operation_time = Timestamp(1791775791, 1);新会话 s2 一开始 operation_time 是 None;把 s1 的 operationTime 传给 s2(advance_operation_time)后 s2 在 secondary 上读到 'A',也就是 s1 写入的值——时间戳可以手工在客户端之间传递。", t=tl(S(4)), mark=lidx(S(4), '传给 s2 之后', 's1.operation_time'), done=lidx(S(4), 's2 一开始 operation_time = None'), kv=KV([['operationTime', '每次响应带回,会话保存'], ['跨会话', '要手工传递']], ['跨会话'])),
    step("因果一致性只保证同一条因果链:让 secondary 再次落后,写入 'B' 后,一个没有传递 operationTime 的新会话在这个 secondary 上读到 'A'(旧值)——会话自己没写过,也没被告知要等谁。", t=tl(S(5)), mark=lidx(S(5), "i = 'A'"), done=lidx(S(5), '新会话没有传递'), kv=KV([['没有传递时间戳的会话', '没有保证'], ['保证范围', '同一条因果链(同一会话或手工传递)']], ['保证范围'])),
    step("afterClusterTime 是 readConcern 的一个参数,可以和 local / majority / snapshot 任意搭配:db.runCommand({find: ..., readConcern: {level: 'local', afterClusterTime: Timestamp(0, 1)}}) 返回 ok: 1。w:1 的写入在 primary 回滚时仍会被撤销(后面 rollback 一篇),要完整保证需要配合 majority 读写关注。", t=tl(S(6)), mark=lidx(S(6), 'afterClusterTime'), done=lidx(S(6), '  1'), kv=KV([['afterClusterTime', '可与任何读关注搭配'], ['w:1', '回滚时可能被撤销'], ['完整保证', 'majority 读写 + 因果会话']], ['完整保证'])),
]
A = mkartm('m53', 53, 'MongoDB,因果一致性,causal consistency,afterClusterTime,读写后一致,副本集,真实验证,动画演示',
    '实测因果一致性会话:写 primary 后立刻读 secondary,不带会话 3000 次里有 2052 次读到旧值,带会话 0 次;用 stopReplProducer 让 secondary 落后,因果读阻塞约 3 秒直到追上;读命令里带 afterClusterTime;operationTime 可以手工在会话间传递,没有传递就没有保证。',
    '写完马上从 secondary 读,能不能读到自己刚写的数据?因果一致性会话是怎么做到的?这篇用 3000 轮写后读统计旧读比例,用 failpoint 让 secondary 落后,看读命令里多出来的 afterClusterTime。',
    [('2052 对 0', '3000 次写后立刻读 secondary:不带会话与带因果会话读到旧值的次数'), ('3,008 ms', 'secondary 落后时,因果会话的读等待 secondary 追上所花的时间(不带会话的读立刻返回旧值)'), ('afterClusterTime', '因果会话的读命令里额外携带的读关注参数')],
    [('旧读的比例', '<p>写 primary 后立刻读 secondary,3000 次里有 2052 次读到旧值;因果一致性会话把写入的 operationTime 传给读,0 次旧读。</p>'),
     ('确定性地落后', '<p>用 failpoint <code>stopReplProducer</code> 让 secondary 停止拉取 oplog:无会话的读立刻返回旧值,因果会话的读会阻塞到 secondary 追上才返回新值(这里等了约 3 秒)。</p>'),
     ('机制', '<p>会话的读命令里多了 <code>readConcern: {afterClusterTime: ...}</code>,服务端等到本节点应用到该时间点之后才执行读。</p>'),
     ('时间戳的来源', '<p>每次响应都带 <code>operationTime</code>,会话把它记下;可以手工传给另一个会话(<code>advance_operation_time</code>)。</p>'),
     ('边界', '<p>只保证同一条因果链:没有传递时间戳的新会话没有任何保证。</p>'),
     ('和其它关注搭配', '<p><code>afterClusterTime</code> 可以和各种读关注搭配;要避免被回滚撤销,还需要 majority 读写关注。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 副本集,启用 enableTestCommands 以使用 failpoint(stopReplProducer);旧读次数每次运行都不同(这次 2052)',
     '没有验证:单调读(从不同 secondary 读时是否会“回到过去”);因果一致性与 majority 读写关注的完整组合下的保证(读自己的写、单调写、写后写);分片集群里的 clusterTime 传播(gossip);其它驱动里 causalConsistency 的默认值;secondary 落后很久时 afterClusterTime 的超时(maxTimeMS)'],
    '因果一致性')
