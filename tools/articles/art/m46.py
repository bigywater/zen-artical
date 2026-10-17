from lib import *
S = SS('m46')
steps = [
    step("三节点副本集 rsm46:9901 是 PRIMARY,9902 与 9903 是 SECONDARY;getDefaultRWConcern 的默认写关注是 { w: 'majority', wtimeout: 0 };hello 显示 3 个成员,多数是 2。", t=tl(S(1)), mark=lidx(S(1), "w: 'majority'", 'majority: 2'), done=lidx(S(1), '9901=PRIMARY'), kv=KV([['成员', '1 个 primary + 2 个 secondary'], ['多数', '2'], ['默认写关注', 'w: majority']], ['默认写关注'])),
    step("单条 insert_one 延迟(各 300 次,中位数 / p99):w:0 0.0 / 0.2 ms;w:1 0.2 / 0.7 ms;w:1 加 j:true 4.0 / 9.0 ms;w:2 0.6 / 1.5 ms;w:majority 4.0 / 8.1 ms;w:3 0.6 / 1.3 ms;w:majority 加 j:true 4.0 / 8.4 ms。w:majority 与 j:true 都要等 journal 落盘(4.0 ms),w:2 / w:3 只等副本应用(0.6 ms)。", t=tl(S(2)), mark=lidx(S(2), 'w:majority  ', 'j:true'), done=lidx(S(2), 'w:0 ', 'w:1 ', 'w:2', 'w:3'), b=bars([['w:0', 0, '0.0 ms'], ['w:1', 0.2, '0.2 ms'], ['w:2', 0.6, '0.6 ms'], ['w:3', 0.6, '0.6 ms'], ['w:1 + j:true', 4, '4.0 ms'], ['w:majority', 4, '4.0 ms']], 4, mark=[4, 5], done=[0, 1, 2, 3]), kv=KV([['w:1', '0.2 ms'], ['w:2 / w:3', '0.6 ms'], ['j:true / w:majority', '约 4 ms,要等 journal 落盘']], ['j:true / w:majority'])),
    step("kill -9 掉一个 secondary:w:majority 仍然成功(23.5 ms,2/3 满足);w:3 要等不存在的第三个确认,wtimeout=1000 在 1016 ms 后返回 WriteConcernError code=64 waiting for replication timed out;但那条 w:3 的文档已经写进了 primary,count 是 1。", t=tl(S(3)), mark=lidx(S(3), 'code=64', '写进了 primary'), done=lidx(S(3), 'w:majority(只剩 2 个节点在线)'), kv=KV([['w:majority', '一个 secondary 挂了仍然成功'], ['w:3 超时', 'code 64,但写入已经生效'], ['含义', '写关注错误 ≠ 写入失败']], ['含义'])),
    step("再 kill 掉另一个 secondary,只剩 1 个节点:它看不到多数,isWritablePrimary 变成 False(secondary 为 True);向它写入报 NotPrimaryError: not primary。", t=tl(S(4)), mark=lidx(S(4), 'NotPrimaryError'), done=lidx(S(4), 'isWritablePrimary = False'), kv=KV([['看不到多数', 'primary 自己降级'], ['写入', 'NotPrimaryError']], ['看不到多数'])),
    step("w:0 不要求确认:第二次插入重复的 _id: 1 没有抛异常——服务端的错误没有告诉客户端;w:1 重复插入抛 DuplicateKeyError;t5 里实际只有 1 个文档。", t=tl(S(5)), mark=lidx(S(5), 'w:0 重复插入', 'DuplicateKeyError'), done=lidx(S(5), '实际文档数 1'), kv=KV([['w:0', '错误不会报告'], ['w:1', '会抛 DuplicateKeyError']], ['w:0'])),
    step("写关注可以设在连接串(w=2 → client.write_concern 是 {'w': 2})、集合(with_options 设成 {'w': 1})或单次操作(mongosh 里 writeConcern: {w: \"majority\", wtimeout: 5000}),单次操作优先级最高;集群默认是 w: majority。", t=tl(S(6)), mark=lidx(S(6), 'writeConcern'), done=lidx(S(6), "{'w': 2}", "{'w': 1}"), kv=KV([['连接串', 'w=2'], ['集合', 'with_options'], ['单次操作', 'writeConcern 选项'], ['优先级', '单次 > 集合 > 连接串 > 集群默认']], ['优先级'])),
]
A = mkartm('m46', 46, 'MongoDB,写关注,writeConcern,w:majority,journal,副本集,真实验证,动画演示',
    '实测写关注的延迟:3 节点副本集上 w:1 0.2 ms,w:2 / w:3 0.6 ms,j:true 与 w:majority 约 4 ms(要等 journal 落盘);secondary 挂掉后 w:majority 仍成功、w:3 超时报 code 64 但写入已生效;只剩 1 个节点 primary 降级;w:0 不报错;写关注的设置位置与优先级。',
    'w:1、w:majority、j:true 的延迟差多少?副本不够时 w:majority 会怎样?wtimeout 的错误意味着写入失败了吗?这篇在真实的 3 节点副本集上逐个验证。',
    [('0.2 对 4.0 ms', 'w:1 与 w:majority 的单条 insert 中位延迟'), ('code 64', 'w:3 在只剩 2 个节点时的 wtimeout 错误,但文档已经写进了 primary'), ('w: majority', '3 节点副本集上没有显式设置时的默认写关注')],
    [('副本集', '<p>一个 primary、两个 secondary,默认写关注是 <code>w: majority</code>。</p>'),
     ('延迟', '<p>单条 insert:w:1 0.2 ms;w:2 / w:3 0.6 ms;<code>j:true</code> 与 <code>w:majority</code> 约 4 ms,因为要等 journal 落盘。</p>'),
     ('secondary 挂掉', '<p>剩 2 个节点时 w:majority 仍成功;<code>w:3</code> 等到 wtimeout 返回 code 64 的 WriteConcernError,但文档已经在 primary 上了——写关注错误不等于写入失败。</p>'),
     ('只剩一个节点', '<p>primary 看不到多数就降级成 secondary,继续写会得到 NotPrimaryError。</p>'),
     ('w:0', '<p>不要求确认,重复键等错误不会报告给客户端。</p>'),
     ('设置位置', '<p>连接串、集合、单次操作都可以指定写关注,单次操作的优先级最高。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 进程组成副本集(oplog 128 MB),全部在本机,没有网络延迟;延迟数字是本机回环上的结果',
     '没有验证:跨机器、跨机房的网络延迟下 w:majority 的耗时;writeConcernMajorityJournalDefault 设为 false 时的行为;带仲裁节点的副本集(后面单独一篇);w:majority 的写入在 primary 切换后是否会回滚(后面 rollback 一篇);分片集群里的 w:majority'],
    '写关注的耗时')
