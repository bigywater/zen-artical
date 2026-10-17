from lib import *
S = SS('m10')
steps = [
    step("方法:写线程用 insert_one 连续单条写入(每条约 130 字节),记下客户端收到确认的最大序号;1.5 秒后对 mongod 发 SIGKILL(kill -9);重启,看数据库里还剩到哪个序号。丢失条数 = 客户端确认过的最大序号 - 恢复后的最大序号。", t=tl(S(1)), mark=lidx(S(1), '丢失条数'), done=lidx(S(1), '正数'), kv=KV([['写入', '单线程 insert_one 连续写 1.5 秒'], ['故障', 'kill -9(SIGKILL)'], ['度量', '确认过的最大序号 - 恢复后最大序号']], ['度量'])),
    step("写关注 w:1(默认,不等 journal 落盘),5 次试验:确认到 17,586 / 15,432 / 17,238 / 16,495 / 16,989,恢复后最大 _id 17,264 / 15,025 / 16,818 / 16,092 / 16,797,丢失 322 / 407 / 420 / 403 / 192 条——客户端收到过确认的写入,kill -9 之后没了。", t=tl(S(2)), mark=lidx(S(2), '丢失  322', '丢失  407', '丢失  420', '丢失  403', '丢失  192'), done=lidx(S(2), '试验 1'), b=bars([['试验 1', 322, '丢 322'], ['试验 2', 407, '丢 407'], ['试验 3', 420, '丢 420'], ['试验 4', 403, '丢 403'], ['试验 5', 192, '丢 192']], 420, mark=[0, 1, 2, 3, 4], done=[]), kv=KV([['w:1', '确认 ≠ 已落盘'], ['丢失量', '每次 192~420 条'], ['原因', 'journal 每 100 ms 才刷一次盘']], ['w:1'])),
    step("写关注 j:true(等 journal 落盘才确认),5 次试验:确认到 484 / 482 / 480 / 472 / 429,恢复后最大 _id 484 / 483 / 481 / 472 / 430,丢失全是 0(最大 _id 偶尔比确认值大 1:那一条已经落盘但客户端没来得及收到确认)。代价是吞吐:1.5 秒只写了约 480 条,w:1 是约 17,000 条。", t=tl(S(3)), mark=lidx(S(3), '丢失    0'), done=lidx(S(3), '试验 1'), b=bars([['w:1 (1.5 s 内)', 17000, '约 17,000 条'], ['j:true (1.5 s 内)', 480, '约 480 条']], 17000, mark=[1], done=[0]), kv=KV([['j:true', '丢失 0'], ['代价', '吞吐降到约 1/35'], ['偶尔 +1', '已落盘但没来得及确认']], ['j:true'])),
    step("journal 刷盘间隔 --journalCommitInterval(毫秒,默认 100)取 10、100、500,w:1 的丢失条数各 8 次试验的中位数:10 ms 是 96(最大 160),100 ms 是 198(最大 502),500 ms 是 306(最大 665)。间隔越大丢得越多,但波动很大(同样的设置多次运行差别明显)。getCmdLineOpts 显示配置已生效。", t=tl(S(4)), mark=lidx(S(4), 'commitIntervalMs=500'), done=lidx(S(4), 'commitIntervalMs=10 ', 'commitIntervalMs=100'), b=bars([['10 ms', 96, '中位数 96'], ['100 ms', 198, '中位数 198'], ['500 ms', 306, '中位数 306']], 306, mark=[2], done=[0, 1]), kv=KV([['间隔 10 ms', '中位数丢 96 条'], ['间隔 100 ms', '198 条'], ['间隔 500 ms', '306 条'], ['注意', '8 次试验,波动大']], ['注意'])),
    step("重启时的日志:没有做过 checkpoint(刚启动不到 60 秒),恢复靠 journal 重放。mongod 日志里含 recover 的行有 47 条,msg 里有 \"Recovering data from the last clean checkpoint.\"、\"WiredTiger recoveryTimestamp\";WiredTiger 自己的 recovery 日志有 18 条不同的消息,前几条是 starting WiredTiger recovery、scanning metadata to remove all incomplete tables、scanning metadata to find the largest file ID。", t=tl(S(5)), mark=lidx(S(5), 'starting WiredTiger recovery', 'scanning metadata'), done=lidx(S(5), '47 条', 'Recovering data'), kv=KV([['mongod 日志', '\"Recovering data from the last clean checkpoint.\"'], ['WiredTiger 日志', 'starting WiredTiger recovery …'], ['重放', '没有 checkpoint 时数据来自 journal']], ['WiredTiger 日志'])),
    step("先 w:1 写 1.5 秒,最后补一次 j:true 的写入,再 kill -9,4 次试验丢失全是 0:确认到 17,807 / 16,382 / 16,504 / 18,576,恢复后最大 _id 与确认值完全相同,文档数都是最大 _id + 2(_id 从 0 开始多 1 个,再加上 _id=-1 的那条 j:true 写入),一条也没少。j:true 落盘时,它之前的所有写入也一起落了盘。", t=tl(S(6)), mark=lidx(S(6), '丢失 0'), done=lidx(S(6), '试验 1'), kv=KV([['j:true 写入', '之前的 w:1 写入也一起落盘'], ['丢失', '0(4 次)']], ['j:true 写入'])),
]
A = mkartm('m10', 10, 'MongoDB,journal,kill -9,写关注,持久性,WiredTiger,真实验证,动画演示',
    '实测 kill -9 之后哪些写入还在:w:1 下每次丢 192~420 条已确认的写入,j:true 零丢失但吞吐降到约 1/35;journalCommitInterval 越大丢得越多(中位数 96、198、306 条);没有 checkpoint 时恢复靠 journal 重放;末尾补一次 j:true 能把之前的写入一起落盘。',
    'MongoDB 说写入成功了,进程被 kill -9 之后还在吗?这篇用一个单线程写入的客户端,在 w:1 和 j:true 下各 kill -9 多次,数丢了多少条,再改 journal 刷盘间隔、看恢复日志。',
    [('192~420 条', 'w:1 下 kill -9 后丢失的已确认写入(5 次试验,每次写入约 17,000 条)'), ('0 条', 'j:true 下 5 次试验丢失的已确认写入,吞吐降到约 480 条 / 1.5 秒'), ('96 / 198 / 306', 'journalCommitInterval 取 10、100、500 ms 时 w:1 丢失条数的中位数')],
    [('方法', '<p>单线程不停地 <code>insert_one</code>,记录客户端收到确认的最大序号;1.5 秒后 SIGKILL,重启后看最大序号,差值就是“确认过但丢了”的条数。</p>'),
     ('w:1', '<p>默认的 <code>w:1</code> 在写入进入内存与 journal 缓冲后就确认,不等 journal 落盘;kill -9 后每次丢 192~420 条。</p>'),
     ('j:true', '<p><code>j:true</code> 等 journal 落盘才确认,丢失为 0,代价是吞吐大幅下降(这里 1.5 秒约 480 条,对 w:1 的约 17,000 条)。</p>'),
     ('刷盘间隔', '<p>journal 默认每 100 ms 刷一次盘。间隔调到 10 ms,中位数丢失降到 96 条;调到 500 ms 升到 306 条,但单次试验的波动很大。</p>'),
     ('恢复过程', '<p>重启时没有 checkpoint 可用(刚启动不到 60 秒),WiredTiger 的 recovery 日志记录了扫描元数据、重放 journal 的过程。</p>'),
     ('j:true 的连带效果', '<p>一次 <code>j:true</code> 的写入落盘时,journal 里它之前的所有写入也一起落盘,所以末尾补一次就能保住前面的 w:1 写入。</p>')],
    steps,
    [ENV_M + '。写线程每次 insert_one 约 130 字节,kill 用 SIGKILL(Python 的 Popen.kill);每次试验都是全新的 mongod',
     '没有验证:副本集 w:majority 的持久性(见后面的文章);断电与操作系统崩溃(只测了进程被杀,操作系统缓存里的数据不会丢);磁盘写缓存;不同硬盘的 fsync 耗时;journalCommitInterval 的效果在多次运行间波动很大,另一次运行里 500 ms 的中位数并没有高于 100 ms,原因没有查明;批量写入下的丢失量'],
    'kill -9 后的数据')
