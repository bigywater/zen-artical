from lib import *
S = SS('f83')
R = J('f83'); lk = R['lock']; two = R['two']
steps = [
    step(f"默认的边界:视图里 db.session.add 之后不 commit(/no-commit),请求结束库里没有这一行(只有 seed 与之前的 x-1、x-2);视图里 commit 两次(/two-commits),两次之后的 txid_current() 分别是 {two['t1']} 与 {two['t2']}——两个独立的事务。", t=tl(S(1)), done=lidx(S(1), 'two-commits'), mark=lidx(S(1), 'no-commit'), kv=KV([['没 commit', '请求结束时丢弃'], ['每次 commit', '一个独立事务']], ['没 commit'])),
    step("出错时:/commit-then-fail 先 commit 了 y-a,再 add y-b 然后抛异常(HTTP 500),库里留下 y-a、没有 y-b——commit 之前的丢,commit 之后的留。", t=tl(S(2)), done=lidx(S(2), 'commit-then-fail'), kv=KV([['y-a', 'commit 过,保留'], ['y-b', '没 commit,丢失']], ['y-a'])),
    step("原子性:/atomic 在同一个事务里加 z-a 和一个与 seed 重名(违反唯一约束)的行,commit 时失败(HTTP 500),z-a 也没有留下——整个事务一起回滚。", t=tl(S(3)), done=lidx(S(3), 'atomic'), kv=KV([['同一个事务', '要么都成功要么都不留']], ['同一个事务'])),
    step("出错之后继续用同一个 session:flush 出错(IntegrityError)之后事务失效,接着执行查询抛 PendingRollbackError,要先 rollback() 才能继续(之后 after_rollback 为 True)。已经执行过查询、事务已自动开始,再调 db.session.begin() 抛 InvalidRequestError「A transaction is already begun on this Session.」。begin_nested() 开的保存点里违反唯一约束,只回滚保存点,外层事务里的 sp-keep 仍被提交。", t=tl(S(4)), mark=lidx(S(4), 'PendingRollbackError', 'begin()'), done=lidx(S(4), 'begin_nested'), kv=KV([['flush 出错后', '必须 rollback()'], ['begin() 重复', 'InvalidRequestError'], ['begin_nested', '保存点,局部回滚']], ['flush 出错后'])),
    step(f"事务边界与锁:A 请求更新 seed 行之后睡 1.5 秒才 commit(总共 {lk[1]:.0f} ms),B 请求更新同一行被阻塞了 {lk[0]:.0f} ms,等到 A commit;只读查询后睡 1.5 秒但没 commit 的请求(连接 idle in transaction),B 更新只用了 {R['ro']:.0f} ms——只读事务不挡写,写事务持有的行锁要等到 commit 才释放。", b=bars([['B 等待写锁', lk[0], f'{lk[0]:.0f} ms'], ['B 遇到只读长事务', R['ro'], f"{R['ro']:.0f} ms"]], lk[0], mark=[0], done=[1]), t=tl(S(5)), mark=lidx(S(5), 'B 更新同一行'), done=lidx(S(5), '只读'), kv=KV([['写事务', '行锁持有到 commit'], ['长事务 + 写', 'B 被阻塞约 1.4 秒']], ['写事务'])),
    step("统一边界:在 after_request 里「状态码 < 400 就 commit,否则 rollback」:/auto-ok(200)留下了数据,/auto-400(abort 400)与 /auto-500(未处理异常,500)都没有留下。这样视图里就不用到处写 commit;代价是响应已经生成,commit 失败时要自己处理,这一点本篇没有验证。", t=tl(S(6)), done=lidx(S(6), 'auto-ok'), mark=lidx(S(6), 'auto-400', 'auto-500'), kv=KV([['< 400', 'commit'], ['≥ 400', 'rollback']], ['< 400'])),
]
A = mkartf('f83', 83, 'Flask,SQLAlchemy,事务,commit,rollback,真实验证,动画演示',
    f'用真实的 PostgreSQL 与 gunicorn 实测 Flask 请求与数据库事务的边界:不 commit 就丢、每次 commit 一个独立事务、commit 前后出错的差别、原子回滚、flush 出错后 PendingRollbackError、保存点、写事务阻塞同一行 {lk[0]:.0f} ms 而只读长事务不挡写、after_request 统一提交。',
    '一个请求到底是不是一个事务?视图里出错时哪些写入会留下?事务拖得久会怎样?这篇用真实的 PostgreSQL 与多线程的 gunicorn,把事务边界的每个情形跑一遍。',
    [(f'{lk[0]:.0f} ms', '另一个请求更新同一行时被未提交的写事务阻塞的时间'), ('2 个', '一个请求里两次 commit 得到的独立事务数(txid 不同)'), ('< 400', 'after_request 里统一提交的状态码条件(本篇的做法)')],
    [('默认的边界', '<p>上一篇:<a href="flask-sqlalchemy-session-lifecycle.html">SQLAlchemy Session 生命周期</a>;下一篇:<a href="flask-model-table-mapping.html">Model 与 Table 映射</a>。</p>'), ('出错时哪些留下', None), ('原子性', None), ('出错之后继续用 session', None), ('长事务与锁', '<p>并发用的是 gunicorn 的 gthread worker,B 请求在 A 之后 0.3 秒发出。</p>'), ('统一提交', None)],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口)', '没有验证:after_request 里 commit 失败时的响应处理、teardown 里的 rollback 与 Flask-SQLAlchemy 的实现细节的对应关系、隔离级别(READ COMMITTED 以外)、死锁检测、其它数据库(MySQL)的行为'], 'Flask 请求与事务边界', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')])
