from lib import *
S = SS('m61')
steps = [
    step("PSA 结构:9901 是 PRIMARY,9902 是 SECONDARY,9903 是 ARBITER;getDefaultRWConcern 里 defaultWriteConcern 为空、defaultWriteConcernSource 是 'implicit';直接向 arbiter 读数据报 NotPrimaryError: node is not in primary or recovering state——它没有数据,只投票。", t=tl(S(1)), mark=lidx(S(1), 'ARBITER', 'NotPrimaryError'), done=lidx(S(1), "defaultWriteConcernSource: 'implicit'"), kv=KV([['arbiter', '投票,不存数据'], ['多数', '3 个投票成员里的 2 个'], ['默认写关注', 'implicit']], ['arbiter'])),
    step("三个节点都在时 w:1 0.2 ms,w:majority 5.0 ms(要等 secondary 确认并落盘)。", t=tl(S(2)), mark=lidx(S(2), 'w:majority 5.0 ms'), done=lidx(S(2), 'w:1 0.2 ms'), b=bars([['w:1', 0.2, '0.2 ms'], ['w:majority', 5, '5.0 ms']], 5, mark=[1], done=[0]), kv=KV([['w:1', '0.2 ms'], ['w:majority', '5.0 ms']], ['w:majority'])),
    step("kill -9 掉 secondary:primary + arbiter 仍是多数,primary 保持 primary(isWritablePrimary = True);w:1 的 insert 0.6 ms 成功;不指定写关注的 insert 0.3 ms 也成功——有 arbiter 时隐式默认是 w:1;w:majority(wtimeout=2000)等了 2,012 ms 后 WTimeoutError(code 64)——arbiter 不存数据,不能确认写入。", t=tl(S(3)), mark=lidx(S(3), 'WTimeoutError', '不指定写关注'), done=lidx(S(3), 'primary 还是 primary', 'w:1 的 insert'), kv=KV([['primary', '仍然是 primary'], ['w:1 / 默认', '成功'], ['w:majority', '超时,code 64']], ['w:majority'])),
    step("majority 的提交点停住了:刚用 w:1 写入的 {k: \"w1\"},readConcern local 读得到(True),readConcern majority 读不到(False)——majority 读看到的是提交点之前的快照。", t=tl(S(4)), mark=lidx(S(4), 'readConcern majority → False'), done=lidx(S(4), 'readConcern local → True'), kv=KV([['local', '读得到'], ['majority', '读不到,提交点没前进']], ['majority'])),
    step("继续每秒多写 2000 个文档:appliedOpTime 一秒一秒前进(…439.4 → …443.4),而 lastCommittedOpTime.ts 一直停在 1791777434.122,落后从 5 秒拉大到 9 秒。提交点停住意味着 majority 读看不到新数据,也意味着存储引擎要一直保留这段时间以来的历史版本(缓存压力随之增大,这里没有量化)。", t=tl(S(5)), mark=lidx(S(5), '落后 9 秒', '落后 8 秒'), done=lidx(S(5), '落后 5 秒', '落后 6 秒'), b=bars([['多写 2000 个后', 5, '落后 5 秒'], ['多写 6000 个后', 7, '落后 7 秒'], ['多写 10000 个后', 9, '落后 9 秒']], 9, mark=[2], done=[0, 1]), kv=KV([['appliedOpTime', '随写入前进'], ['lastCommittedOpTime', '停在原地'], ['差距', '5 → 9 秒,持续变大']], ['差距'])),
    step("把 secondary 开回来:appliedOpTime 与 lastCommittedOpTime 又都是 1791777443.4,w:majority 又能成功(5.8 ms)。对照 PSS(primary + 2 个 secondary)停掉一个 secondary:w:majority 仍然成功(28.1 ms)——两个数据节点就能确认多数。", t=tl(S(6)), mark=lidx(S(6), 'PSS'), done=lidx(S(6), 'secondary 回来后', 'w:majority 又能成功了'), kv=KV([['PSA 停一个数据节点', 'w:majority 超时'], ['PSS 停一个数据节点', 'w:majority 成功'], ['恢复后', '提交点追平']], ['PSS 停一个数据节点'])),
]
A = mkartm('m61', 61, 'MongoDB,arbiter,仲裁节点,w:majority,PSA,副本集,真实验证,动画演示',
    '实测 arbiter 与 w:majority 的陷阱:PSA 结构里停掉唯一的 secondary 后 primary 仍是 primary,w:1 与默认写关注(隐式 w:1)成功,w:majority 超时(code 64);majority 读看不到新写入,多数提交点停住且落后越拉越大(5 到 9 秒);恢复后追平;PSS 停一个 secondary 则 w:majority 不受影响。',
    '为什么副本集里放 arbiter 会让 w:majority 出问题?这篇搭一个 PSA,停掉唯一的 secondary,看 primary、写关注、majority 读和提交点的表现,并和 PSS 对比。',
    [('code 64', 'PSA 停掉 secondary 后 w:majority 的超时错误'), ('5 到 9 秒', '继续写入时 appliedOpTime 与 lastCommittedOpTime 的差距的增长'), ('w:1', '有 arbiter 时隐式默认写关注(不是 w:majority)')],
    [('PSA', '<p>primary + secondary + arbiter:arbiter 参与投票但不存数据,所以只有 2 个数据节点。</p>'),
     ('停掉 secondary', '<p>primary + arbiter 仍是多数,primary 不降级,但 <code>w:majority</code> 需要的是“多数节点持久化了这次写入”,arbiter 无法确认,于是超时。</p>'),
     ('隐式默认', '<p>有 arbiter 时隐式的默认写关注是 <code>w:1</code>,所以不显式指定写关注的写入看起来一切正常——它们并没有被多数确认。</p>'),
     ('majority 读', '<p>提交点停住,<code>readConcern: majority</code> 读不到新数据;local 读得到。</p>'),
     ('提交点落后', '<p>写入继续,但多数提交点不前进,差距越来越大,存储引擎要保留更多历史版本。</p>'),
     ('PSS 对比', '<p>三个数据节点停掉一个,另外两个就能确认多数,w:majority 不受影响。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 副本集(第三个为 arbiterOnly),secondary 用 kill -9 停掉',
     '没有验证:提交点停住对 WiredTiger 缓存与 history store 的具体影响(只观察到差距在变大);长时间(小时级)后的磁盘与缓存压力;在 PSA 上把 secondary 降为 hidden 或延迟的变体;5.0 之后添加 arbiter 要求显式设置默认写关注的校验;MongoDB 对 arbiter 的官方建议'],
    'arbiter 与 w:majority')
