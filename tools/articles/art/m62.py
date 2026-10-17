from lib import *
S = SS('m62')
steps = [
    step("四个成员:9901 P(priority 2)、9902 S(普通 secondary)、9903 H(hidden、priority 0)、9904 D(hidden、priority 0、secondaryDelaySecs=8)。replSetGetStatus 里能看到全部四个;primary 的 hello.hosts 只列出 9901 和 9902,看不到 9903 与 9904;配置里 H 与 D 都是 votes=1、hidden=True;hidden 成员自己的 hello 里 hidden 为 True。", t=tl(S(1)), mark=lidx(S(1), 'hello.hosts', 'hidden = True'), done=lidx(S(1), '全部成员', '配置里的每个成员'), kv=KV([['hidden', '不出现在 hello.hosts'], ['priority 0', '不能成为 primary'], ['votes', '仍然是 1,参与投票']], ['hidden'])),
    step("客户端用 secondary 读偏好读 100 次,全部落在普通 secondary 9902 上({'9902': 100}),hidden 的 9903 和 9904 一次也没被选中——驱动根本看不到它们。", t=tl(S(2)), mark=lidx(S(2), "{'9902': 100}"), done=lidx(S(2), '100 次 secondary 读'), b=bars([['9902(S)', 100, '100 次'], ['9903(H)', 0, '0 次'], ['9904(D)', 0, '0 次']], 100, mark=[1, 2], done=[0]), kv=KV([['secondary 读偏好', '只会选可见的 secondary'], ['hidden', '读不到,适合备份、报表']], ['hidden'])),
    step("hidden 节点照常复制数据,可以直连读:向 primary 写 {_id: 1}(w:3)后直连 H 读到(True)。", t=tl(S(3)), mark=lidx(S(3), 'True'), done=lidx(S(3), '直连 H 读'), kv=KV([['hidden', '照常复制'], ['直连读', '拿到最新数据']], ['hidden'])),
    step("delayed 成员落后 8 秒:在 primary 上写 {_id: 2},普通 secondary S 上 0.00 s 就能读到;延迟成员 D 上 8.1 s 才出现(secondaryDelaySecs = 8)。", t=tl(S(4)), mark=lidx(S(4), '8.1 s'), done=lidx(S(4), '0.00 s'), b=bars([['普通 secondary S', 0, '0.00 s'], ['延迟成员 D', 8.1, '8.1 s']], 8.1, mark=[1], done=[0]), kv=KV([['S', '几乎实时'], ['D', '落后 secondaryDelaySecs 秒']], ['D'])),
    step("用 delayed 成员救回误删的数据:primary 上 drop 了 precious(100 个文档)后,primary 与 S 上都是 0 个,而还在延迟窗口里的 D 上还有 100 个;把它们读出来写回 primary,primary 上又有 100 个。", t=tl(S(5)), mark=lidx(S(5), '写回 primary'), done=lidx(S(5), 'D 上(延迟窗口内)100 个', 'drop 了 precious'), kv=KV([['误 drop', 'primary 与 S 立刻丢失'], ['D', '延迟窗口内还有数据'], ['救回', '读出再写回']], ['救回'])),
    step("延迟成员有投票权会拖慢 w:majority:停掉 S 后,4 个投票成员的多数是 3 个,除了 P 和 H 还要等 D 应用这次写入,w:majority 的 insert 耗时 8.0 s(≈ 延迟 8 s)。所以延迟成员通常应设 votes: 0。", t=tl(S(6)), mark=lidx(S(6), '8.0 s'), done=lidx(S(6), '停掉 S 后'), kv=KV([['延迟成员 votes: 1', 'w:majority 要等它,慢 8 秒'], ['建议', 'votes: 0 + priority 0 + hidden']], ['建议'])),
]
A = mkartm('m62', 62, 'MongoDB,hidden成员,delayed成员,secondaryDelaySecs,副本集,真实验证,动画演示',
    '实测 hidden 与 delayed 成员:hidden 成员不出现在 hello.hosts,secondary 读偏好 100 次一次也选不到,但照常复制可直连读;延迟 8 秒的成员 8.1 秒后才有新写入,drop 之后窗口内仍有数据可救回;延迟成员有投票权会让 w:majority 慢约 8 秒。',
    'hidden 和 delayed 成员有什么用?客户端看不看得到?delayed 能不能当误删的后悔药?这篇配了一个 P + S + hidden + hidden delayed 的副本集,逐个验证,并发现延迟成员有投票权时的代价。',
    [('100 / 0 / 0 次', 'secondary 读偏好下 100 次读落在普通 secondary / hidden / delayed 成员上的次数'), ('8.1 s', '延迟成员 D 上看到新写入所需时间(普通 secondary 0.00 s)'), ('8.0 s', '延迟成员有投票权时,停掉普通 secondary 后 w:majority 的耗时')],
    [('hidden', '<p>hidden 成员不出现在 <code>hello.hosts</code>,驱动看不到它,读偏好永远选不到;它照常复制数据、可直连读,常用于备份和报表。priority 必须为 0,但仍可投票。</p>'),
     ('不会被选中', '<p>secondary 读偏好下 100 次读全部落在普通 secondary 上。</p>'),
     ('delayed', '<p>配置 <code>secondaryDelaySecs: 8</code> 后,延迟成员比主节点晚 8 秒应用写入。</p>'),
     ('后悔药', '<p>误 drop 集合后,延迟窗口内延迟成员上的数据还在,读出来写回 primary 即可。</p>'),
     ('投票权的代价', '<p>延迟成员若有投票权,会参与多数计算:停掉普通 secondary 后 <code>w:majority</code> 要等延迟成员,慢了整整一个延迟时长;延迟成员通常配 <code>votes: 0</code>。</p>'),
     ('oplog 窗口', '<p>延迟成员需要比延迟时长更大的 oplog 窗口(这里没有量化)。</p>')],
    steps,
    [ENV_M + '。4 个 mongod 副本集(oplog 128 MB),延迟 8 秒(实际使用常设几小时);所有节点在本机',
     '没有验证:延迟成员 votes: 0 时 w:majority 不受影响(只验证了有投票权时的拖慢);延迟成员的 oplog 窗口需求;hidden 成员在选举中的行为(priority 0 不能当选);hidden 成员对 mongos 与驱动拓扑发现的影响;延迟成员上的 rollback;误删后用 delayed 节点做时间点恢复的完整流程'],
    'hidden 与 delayed 成员')
