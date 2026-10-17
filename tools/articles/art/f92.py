from lib import *
S = SS('f92')
R = J('f92'); sl = R['slow']; st = R['stream']; lk = R['leak']
h, r_ = sl['hold'], sl['release']
steps = [
    step("一个请求里连接借出与归还(pool.checkedout()):请求开始时 0;第一次执行 select 1 后 1(autobegin 借出连接并开始事务);commit() 之后 0(连接归还);再执行 select 1 又是 1;session.close() 之后 0;请求结束前再查询是 1,请求结束后(teardown 清理 session)回到 0。池事件日志是 checkout、checkin、checkout、checkin。所以连接是「用到才借、事务结束就还」,不是整个请求都占着。", t=tl(S(1)), done=lidx(S(1), '开始', 'commit()', 'session.close()', '请求结束之后', '池事件'), mark=lidx(S(1), '执行 select 1'), kv=KV([['借出', '第一次执行 SQL(autobegin)'], ['归还', 'commit / rollback / close / 请求结束']], ['归还'])),
    step(f"泄漏:视图里 db.engine.connect() 之后不关闭(pool_size=2、max_overflow=0、pool_timeout=1):连续 4 次请求 /leak 的状态码是 {lk[0]},借出的连接数停在 {lk[1]},第 3 次起拿不到连接,等 1 秒后 500(TimeoutError);用 with db.engine.connect() as c 管理的 /noleak 连续 6 次都是 200,借出 0。池不会替你回收没关的连接。", t=tl(S(2)), mark=lidx(S(2), '/leak'), done=lidx(S(2), '/noleak'), kv=KV([['不关闭的 connect()', '请求结束后连接仍被占着'], ['with 管理', '用完就还']], ['不关闭的 connect()'])),
    step(f"请求里做慢操作时还抓着连接:3 个并发请求、pool_size=2,每个请求查一次然后睡 1 秒。/hold(睡的时候事务没结束,连接还在手上):各自耗时 {h[0]} ms,第三个请求等了前面的请求释放连接,总耗时 {h[1]:.0f} ms;/release(commit 之后再睡):各自耗时 {r_[0]} ms,总耗时 {r_[1]:.0f} ms。慢的外部调用(HTTP、邮件)之前先 commit 或 close,别占着连接。", b=bars([['/hold 总耗时', h[1], f'{h[1]:.0f} ms'], ['/release 总耗时', r_[1], f'{r_[1]:.0f} ms']], h[1], mark=[0], done=[1]), t=tl(S(3)), mark=lidx(S(3), '/hold'), done=lidx(S(3), '/release'), kv=KV([['睡之前不 commit', '占着连接,并发被池限制'], ['睡之前 commit', '连接立刻归还']], ['睡之前不 commit'])),
    step(f"流式响应(stream_with_context):视图里先查询、再返回生成器时,流式过程中另一个请求看到借出的连接数是 {st['视图里先查询,再返回生成器'][0]}(视图返回后请求结束,session 已被清理);而在生成器里(流式过程中)才查询,流式过程中借出的连接数是 {st['生成器里(流式过程中)才查询'][0]},直到流结束才回到 {st['生成器里(流式过程中)才查询'][1]}。生成器里碰数据库会在整个流式期间占着连接。", t=tl(S(4)), done=lidx(S(4), '视图里先查询'), mark=lidx(S(4), '生成器里'), kv=KV([['视图里查询', '视图返回后就释放'], ['生成器里查询', '占到流结束']], ['生成器里查询'])),
]
A = mkartf('f92', 92, 'Flask,SQLAlchemy,连接池,checkout,连接泄漏,真实验证,动画演示',
    f'在真实的 PostgreSQL 与 gunicorn 上实测连接什么时候借出、什么时候归还:autobegin 借出、commit 或 close 归还;不关闭的 connect() 泄漏后第 3 个请求起 500;慢操作前不 commit 时 3 个并发请求总耗时 {h[1]:.0f} ms,commit 后 {r_[1]:.0f} ms;流式响应里查询会一直占着连接。',
    '一个请求到底占着数据库连接多久?什么写法会让连接泄漏?为什么请求里的慢调用会拖垮连接池?这篇用 pool.checkedout() 和池事件,把连接的借出与归还一步步量出来。',
    [(f'{h[1]:.0f} → {r_[1]:.0f} ms', '慢操作之前不 commit 与 commit 之后,3 个并发请求(pool_size=2)的总耗时'), ('2 个', '不关闭 connect() 的请求之后,借出的连接数(pool_size=2)'), ('0 → 1', '视图里查询与生成器里查询时,流式响应期间借出的连接数')],
    [('借出与归还', '<p>上一篇:<a href="flask-connection-pool.html">数据库连接池</a>;下一篇:<a href="flask-expire-on-commit.html">expire_on_commit</a>。</p>'), ('连接泄漏', None), ('慢操作与连接', '<p>每个请求一个线程(gthread);池是 2 个连接,超时 3 秒。</p>'), ('流式响应', None)],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口)、gunicorn gthread', '没有验证:异步视图与 asyncio 引擎下的连接占用、Celery 任务里的连接管理、泄漏的连接被垃圾回收时的行为(本篇只观察到请求结束后借出数停在 2,没有查原因)、连接泄漏的监控手段'], 'Pool Checkout 与连接释放', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')])
