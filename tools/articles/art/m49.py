from lib import *
S = SS('m49')
steps = [
    step("一个事务里做 3 个操作(insert、update、delete),提交后 oplog 里只新增 1 条:顶层字段是 lsid、ns、o、op、prevOpTime、t、ts、txnNumber、v、wall,op='c'、ns='admin.$cmd',o 里只有 applyOps,3 个操作全装在 applyOps 里(i 到 test.a、u、d);lsid 的键是 id 与 uid,txnNumber 为 2,prevOpTime.ts 是 Timestamp(0, 0)(事务的第一条没有前驱)。", t=tl(S(1)), mark=lidx(S(1), "op='c'", 'applyOps 里有 3 个操作', 'prevOpTime.ts = Timestamp(0, 0)'), done=lidx(S(1), '新增了 1 条', 'op=i ns=test.a', 'op=d ns=test.a'), kv=KV([['事务提交', '1 条 applyOps 条目'], ['ns', 'admin.$cmd'], ['3 个操作', '在 o.applyOps 数组里'], ['lsid + txnNumber', '标识哪个会话的哪个事务']], ['事务提交'])),
    step("对照:同样的 3 个操作不放进事务(retryWrites=False 的客户端),oplog 新增 3 条,各自一条 op=i / u / d,没有 lsid。事务把 N 个操作合成了 1 条 oplog。", t=tl(S(2)), mark=lidx(S(2), 'op=i ns=test.a', 'op=u ns=test.a', 'op=d ns=test.a'), done=lidx(S(2), '新增了 3 条'), b=bars([['事务里的 3 个操作', 1, '1 条 oplog'], ['事务外的 3 个操作', 3, '3 条 oplog']], 3, mark=[1], done=[0]), kv=KV([['事务内', '1 条 applyOps 打包'], ['事务外', '每个操作一条']], ['事务内'])),
    step("applyOps 里的 update 存的不是整个新文档,而是 diff:{'$v': 2, 'diff': {'u': {'v': 100}}}——$set 的字段在 u 里;insert 的 o 是整个文档,delete 的 o 只有 _id。(diff 格式在后面一篇单独展开。)", t=tl(S(3)), mark=lidx(S(3), "'diff': {'u': {'v': 100}}"), done=lidx(S(3), 'update 的 o'), kv=KV([['update', '{$v: 2, diff: {u: {v: 100}}}'], ['insert', '整个文档'], ['delete', '只有 _id']], ['update'])),
    step("提交的标记在 config.transactions 里:该会话的记录是 txnNum 2、lastWriteOpTime(指向上面那条 applyOps 的 ts)、lastWriteDate,以及 state: 'committed';与 oplog 条目的 ts 相同(True)。", t=tl(S(4)), mark=lidx(S(4), "'state': 'committed'", '与 applyOps 条目的 ts 相同'), done=lidx(S(4), 'config.transactions 记录'), kv=KV([['config.transactions', '每个会话一条:txnNum、lastWriteOpTime、state'], ['state', 'committed'], ['lastWriteOpTime', '= applyOps 条目的 ts']], ['state'])),
    step("中止的事务:insert + update 之后 abortTransaction,oplog 里新增了 0 条与业务相关的条目,文档 _id 30 也不存在——中止不留痕迹。", t=tl(S(5)), mark=lidx(S(5), '新增了 0 条'), done=lidx(S(5), '_id 30 存在: False'), kv=KV([['abortTransaction', 'oplog 里什么都不写'], ['提交前', '操作都在内存,不进 oplog']], ['abortTransaction'])),
    step("大事务会拆成多条 applyOps:一个事务里插入 20 个 1 MiB 的文档,oplog 里是 2 条 applyOps——条目 1 有 16 个操作、partialTxn=True、prevOpTime 是 (0,0);条目 2 有 5 个操作、partialTxn 不存在、count=21(20 个插入加隐式创建集合共 21 个操作)、prevOpTime 指向条目 1。", t=tl(S(6)), mark=lidx(S(6), 'partialTxn=True', 'count=21'), done=lidx(S(6), '新增 2 条 applyOps 条目'), b=bars([['条目 1', 16, '16 个操作 partialTxn'], ['条目 2', 5, '5 个操作 count=21']], 16, mark=[1], done=[0]), kv=KV([['单条 applyOps', '有大小上限(约 16 MB)'], ['partialTxn', '前面的条目都带它'], ['最后一条', '带 count = 操作总数']], ['partialTxn'])),
]
A = mkartm('m49', 49, 'MongoDB,事务,oplog,applyOps,partialTxn,config.transactions,真实验证,动画演示',
    '实测事务在 oplog 里的样子:提交的事务只写 1 条 applyOps 条目(op=c,ns=admin.$cmd),3 个操作装在里面,用 lsid + txnNumber + prevOpTime 链起来;不放进事务则每个操作一条;update 存 diff;提交标记在 config.transactions 的 state: committed;中止的事务不留痕迹;大事务拆成 partialTxn 加一条带 count 的最后条目。',
    '事务的修改是怎么写进 oplog、再复制到 secondary 的?这篇提交一个事务,直接读 local.oplog.rs,看 applyOps 条目的结构、config.transactions 的记录,再对比中止和大事务的情形。',
    [('1 条对 3 条', '事务里 3 个操作写进 oplog 的条数,对不放进事务时的 3 条'), ('applyOps', '事务提交时 oplog 里的命令:op=c、ns=admin.$cmd'), ('2 条', '20 个 1 MiB 的插入事务拆成的 applyOps 条数(第一条 partialTxn=True)')],
    [('一条 applyOps', '<p>事务提交时,所有操作被打包成一条 <code>applyOps</code>(<code>op: "c"</code>、<code>ns: "admin.$cmd"</code>)写进 oplog,secondary 按这条原子地应用。</p>'),
     ('对比不放进事务', '<p>同样三个操作不放进事务,各写一条 oplog;事务把它们合成了一条。</p>'),
     ('update 存 diff', '<p>applyOps 里的 update 条目是 diff(<code>{$v: 2, diff: {u: {v: 100}}}</code>),不是整个新文档。</p>'),
     ('提交标记', '<p>config.transactions 里该会话的记录 <code>state: "committed"</code>,<code>lastWriteOpTime</code> 指向 applyOps 条目。</p>'),
     ('中止', '<p>中止的事务在 oplog 里不留任何条目。</p>'),
     ('大事务', '<p>事务的修改太大时拆成多条 applyOps:前面的带 <code>partialTxn: true</code>,最后一条带总操作数 <code>count</code>,用 <code>prevOpTime</code> 链接。</p>')],
    steps,
    [ENV_M + '。单节点副本集;直接用 pymongo 读 local.oplog.rs;事务外的对照用 retryWrites=False 的连接(默认的 retryable writes 会给事务外的写也加 lsid 与 txnNumber)',
     '没有验证:分片事务的 prepare / commit 条目;大事务的 applyOps 拆分阈值的精确值;change stream 里如何呈现事务内的多个操作(下面 change stream 一篇);事务在 secondary 上的应用方式与延迟;oplog 条目 v、t、wall 字段的含义'],
    '事务的 oplog')
