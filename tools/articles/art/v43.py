from lib import *
S = SS('v43')
steps = [
    step("互斥与开销。20 个线程各抢同一把锁 15 次(共 300 次),拿到锁后工作 5 ms 再释放。(a) 单 key CAS 锁(Txn:create_revision == 0 才写入,没抢到就随机退避 10 到 20 ms 重试):同一时刻最多 1 个持有者,总用时 4.4 s,发给 etcd 的请求 3807 个,等待 p50 157 ms、p99 936 ms。(b) 排队锁(每个竞争者在前缀下写自己的 key,只监听前一个 key 的删除):最多 1 个持有者,总用时 3.5 s,请求 1798 个,等待 p50 210 ms、p99 263 ms,相邻两次获取锁按 create_revision 递增的比例 100%(先到先得)。两种锁都互斥;CAS 锁的请求数是排队锁的两倍多,最坏等待也长得多。", t=tl(S(1)), mark=lidx(S(1), '(a)'), done=lidx(S(1), '(b)'), b=bars([['(a) CAS:etcd 请求数', 3807, '3807'], ['(b) 排队:etcd 请求数', 1798, '1798'], ['(a) CAS:等待 p99 ms', 936, '936'], ['(b) 排队:等待 p99 ms', 263, '263']], 3900, mark=[0, 2], done=[1, 3]), kv=KV([['CAS 锁', '3807 个请求,p99 936 ms'], ['排队锁', '1798 个请求,p99 263 ms,100% FIFO'], ['互斥', '两种都是最多 1 个持有者']], ['排队锁'])),
    step("持有者崩溃与暂停。lease TTL 2 s。(a) 持有者崩溃(不再续约、也不释放):等待者拿到锁用了 2.51 s、2.54 s、2.42 s。(b) 持有者没崩溃,只是被暂停 3 秒,lease 过期、锁被 B 拿走;A 恢复后以为自己还持有锁:共享资源上依次是 A(token 1214)写入、B(token 1216)写入、A(token 1214)又写入——两个持有者写了同一个资源。(c) 共享资源检查 fencing token(拿锁时的 create_revision):A(token 1218)写入、B(token 1220)写入、A(token 1218)被拒绝。锁服务无法阻止暂停的旧持有者醒来后继续写,要靠共享资源一侧用单调递增的 token 拒绝过期的写入。", t=tl(S(2)), mark=lidx(S(2), '(b)'), done=lidx(S(2), '(a)', '(c)'), b=bars([['(a) 崩溃后等待者拿到锁 s', 2.5, '2.42~2.54'], ['(b) 旧持有者醒来后的写入', 1, '写入成功(冲突)'], ['(c) 旧持有者醒来后的写入', 0, '被拒绝(token 1218 < 1220)']], 2.6, done=[0, 2], mark=[1]), kv=KV([['持有者崩溃', '约 TTL + 0.5 s 后别人拿到锁'], ['暂停后醒来(无 fencing)', '旧持有者的写入成功'], ['fencing token', '旧 token 的写入被拒绝']], ['暂停后醒来(无 fencing)'])),
    step("Leader 选举。5 个候选者在 /election/ 下写带 lease 的 key,create_revision 最小的是 leader。TTL 2 s:leader 崩溃后新 leader 出现用了 1.92 s、2.13 s、2.20 s;leader 主动 resign 只要 0.01 s 左右。TTL 5 s:崩溃 5.09 s、5.16 s、5.21 s;resign 0.00 到 0.01 s。每次新 leader 都是 c1(create_revision 次小的候选者)。崩溃的故障转移时间与 TTL 相当,主动 resign 几乎立刻;TTL 越短故障转移越快,但网络抖动时被误判失效的概率越高。", t=tl(S(3)), mark=lidx(S(3), '(a) 崩溃'), done=lidx(S(3), '(b) resign'), b=bars([['TTL 2 s 崩溃:故障转移 s', 2.13, '1.92~2.20'], ['TTL 5 s 崩溃:故障转移 s', 5.16, '5.09~5.21'], ['TTL 2 s resign:故障转移 s', 0.01, '0.01'], ['TTL 5 s resign:故障转移 s', 0.01, '0.00~0.01']], 5.3, mark=[0, 1], done=[2, 3]), kv=KV([['崩溃', '故障转移 ≈ TTL'], ['resign', '约 0.01 s'], ['新 leader', '总是 create_revision 次小的候选者']], ['崩溃'])),
]
A = mkartv('v43', 43, '微服务,注册中心,etcd,分布式锁,Leader选举,fencing,真实验证,动画演示',
    '实测 etcd 的 Txn 锁与选举:排队锁(监听前一个 key)比单 key CAS 锁请求数少一半多(1798 对 3807)、p99 等待 263 ms 对 936 ms 且严格先到先得;持有者暂停后醒来会和新持有者同时写,共享资源按 fencing token 才能拒绝;leader 崩溃的故障转移约等于 TTL,主动 resign 约 0.01 s。',
    '用 etcd 做分布式锁和 Leader 选举,CAS 锁和排队锁差多少?持有者崩溃或被暂停会怎样?fencing token 怎么救场?选举的故障转移时间由什么决定?这篇用 etcd 3.7.2 的 Txn 和 lease 逐项量出来。',
    [('1798 对 3807', '20 个线程抢 300 次锁时,排队锁与单 key CAS 锁发给 etcd 的请求数'), ('A(1218)被拒绝', '锁持有者被暂停 3 秒后醒来继续写:没有 fencing 时写入成功,共享资源检查 fencing token 后被拒绝'), ('1.92 到 2.20 s 对 0.01 s', 'TTL 2 s 的选举里,leader 崩溃与主动 resign 时新 leader 出现用的时间')],
    [('CAS 锁与排队锁', '<p>排队锁每个竞争者只监听前一个,请求数少、先到先得;CAS 锁请求多、等待波动大。</p>'),
     ('崩溃与暂停', '<p>崩溃靠 lease 过期释放锁;暂停后醒来的旧持有者要靠 fencing token 在资源一侧拒绝。</p>'),
     ('选举的故障转移', '<p>崩溃时约等于 TTL,主动 resign 几乎立刻。</p>')],
    steps,
    [ENV_V + '。etcd 3.7.2(Homebrew,单节点自己起的进程,每次运行前清空数据目录),通过 HTTP/JSON 网关操作 Txn / lease / watch;锁和选举是我按 etcd concurrency 包的做法手写的 Python 实现,不是 clientv3 的 concurrency 包本身;fencing token 用的是拿锁时的 create_revision(第一节 CAS 锁用的是 Txn 的 revision);崩溃与暂停是让续约线程停止来模拟的,没有真的 kill 进程;每个场景的次数见各节',
     '没有验证:clientv3 concurrency.Session / Mutex / Election 的真实实现和它们的 keepalive 重试;etcd 集群 leader 切换期间锁的行为;lease TTL 更长时的故障转移;大量竞争者(几百个)时排队锁的开销;锁的可重入;读写锁'],
    'etcd 事务与选举')
