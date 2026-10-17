from lib import *
S = SS('m47')
steps = [
    step("快照隔离:事务 T1 开始后读 A.bal = 100;事务外把 A.bal 改成 150 并提交,事务外读到 150,T1 里再读仍是 100(快照里的值);T1 提交后新的读看到 150。", t=tl(S(1)), mark=lidx(S(1), '仍是快照里的值'), done=lidx(S(1), 'T1 开始后读 A.bal = 100', 'T1 提交后'), kv=KV([['事务内', '读到开始那一刻的快照'], ['事务外', '读到最新提交的值']], ['事务内'])),
    step("写冲突:T1 修改了 A 还没提交,另一个事务 T2 也想修改 A,4 ms 后立刻报错 code=112(WriteConflict),errorLabels 为 ['TransientTransactionError']——事务之间的写冲突不会等待,直接失败,可以整个重试。", t=tl(S(2)), mark=lidx(S(2), 'code=112'), done=lidx(S(2), 'T2 的更新'), kv=KV([['事务对事务', 'WriteConflict(code 112)'], ['标签', 'TransientTransactionError,可重试'], ['速度', '4 ms 就报错,不等待']], ['标签'])),
    step("事务外的写入遇到事务里未提交的修改:不报错而是等待——T1 未提交 1.5 秒后事务外的 update 仍未完成;T1 提交后它才完成,总共等了 1,526 ms,最终 A.bal = 201(100 + 1 + 100)。", t=tl(S(3)), mark=lidx(S(3), '总共等了 1526 ms'), done=lidx(S(3), '仍未提交 1.5 秒后'), kv=KV([['事务外的写', '等待事务结束'], ['事务内的写', '遇到冲突立即失败'], ['等待时间', '1,526 ms(等到 T1 提交)']], ['事务外的写'])),
    step("with_transaction 回调写法冲突时自动重试整个回调:16 个线程各给同一个账户加 1,每线程 100 轮,最终 A.bal = 1600(应为 1600),耗时 2.12 s,因 WriteConflict 额外重试了 1,492 次(平均每次提交 0.93 次重试)。", t=tl(S(4)), mark=lidx(S(4), '额外重试了 1492 次'), done=lidx(S(4), 'A.bal = 1600'), kv=KV([['with_transaction', '遇到 TransientTransactionError 自动重试'], ['结果', '1600,一个不丢'], ['代价', '热点文档上平均 0.93 次重试 / 提交']], ['with_transaction'])),
    step("快照隔离的写偏斜:“至少要有一人在岗”,两个事务各自读到在岗人数 [2, 2],各自让不同的医生下班(更新的是不同的文档,没有写冲突),都提交成功,最终在岗人数 0——规则被破坏。快照隔离不等于可串行化。", t=tl(S(5)), mark=lidx(S(5), '在岗人数 = 0'), done=lidx(S(5), '[2, 2]'), kv=KV([['读相同、写不同的文档', '没有写冲突'], ['结果', '在岗 0 人'], ['避免', '让两个事务都写同一个文档(例如一个计数器)']], ['结果'])),
    step("事务里的限制:count 命令报 code=263 Cannot run 'count' in a multi-document transaction.(要用 countDocuments);新开事务后 countDocuments = 2、find_one 正常返回 {'_id': 'B', 'bal': 100}。", t=tl(S(6)), mark=lidx(S(6), 'code=263'), done=lidx(S(6), 'countDocuments = 2'), kv=KV([['count 命令', 'code 263,事务里不允许'], ['countDocuments', '可以']], ['count 命令'])),
]
A = mkartm('m47', 47, 'MongoDB,事务,快照隔离,WriteConflict,写偏斜,with_transaction,真实验证,动画演示',
    '实测多文档事务:事务内读到开始时的快照,事务外的提交看不到;事务之间的写冲突 4 ms 内报 WriteConflict(code 112,带 TransientTransactionError),事务外的写入则等待事务结束(等了 1,526 ms);16 线程 with_transaction 计数 1600 次一个不丢(重试 1,492 次);快照隔离下的写偏斜让在岗人数变成 0。',
    '多文档事务到底是什么隔离级别?写冲突怎么表现?并发下怎么重试?快照隔离能不能保证业务规则?这篇在副本集上逐个实验。',
    [('code 112', '两个事务写同一个文档时后者的 WriteConflict 错误码,4 ms 就返回'), ('1,492 次', '16 线程在一个热点文档上做 1600 次事务加一,因冲突额外重试的次数'), ('在岗 0 人', '写偏斜:两个事务各让一个医生下班后实际的在岗人数')],
    [('快照', '<p>事务开始后读到的是那一刻的快照,别人之后提交的修改在事务结束前看不到。</p>'),
     ('写冲突', '<p>两个事务修改同一个文档,后来的直接失败:code 112 WriteConflict,带 <code>TransientTransactionError</code> 标签,表示可以整个重试。</p>'),
     ('事务外的写', '<p>事务外的写入遇到事务里未提交的修改会等待,不会报错,直到事务提交或中止。</p>'),
     ('重试', '<p><code>with_transaction</code> 遇到临时性错误会重试整个回调;热点文档上平均每次提交约一次重试,结果仍然正确。</p>'),
     ('写偏斜', '<p>快照隔离只检测对同一文档的写冲突,检查一个条件后更新另一个文档,会出现写偏斜,业务不变式可能被破坏。</p>'),
     ('限制', '<p>事务里不能用 <code>count</code> 命令,要用 <code>countDocuments</code>。</p>')],
    steps,
    [ENV_M + '。副本集只有 1 个节点(足够用事务);并发线程数与重试次数每次运行都不同',
     '没有验证:readConcern local / majority 的事务;事务的 writeConcern 在 commit 时的作用;分片集群上的分布式事务;长事务对 WiredTiger 缓存(history store)的影响;事务内创建集合与索引的限制;"读已提交"在事务外的表现(见读关注一篇)'],
    '多文档事务')
