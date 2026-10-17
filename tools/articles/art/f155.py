from lib import *
S = SS('f155')
R = J('f155'); co = R['cost']; k = list(co); a, b, c_ = co[k[0]], co[k[1]], co[k[2]]
steps = [
    step("两个测试(先 POST 一条并 commit,再检查表是空的),在真实的 PostgreSQL 上比较几种隔离策略:不清理 → 1 failed, 1 passed(后一个测试看到前一个留下的数据);每个测试 drop_all 加 create_all → 2 passed;每个测试之后 TRUNCATE → 2 passed;外层事务加保存点,测试结束回滚 → 2 passed。", t=tl(S(1)), mark=lidx(S(1), '不清理'), done=lidx(S(1), 'drop_all', 'TRUNCATE', '保存点'), kv=KV([['不清理', '互相污染'], ['drop/create、TRUNCATE、回滚', '都能隔离']], ['不清理'])),
    step(f"100 个测试(每个都 POST 一条并 commit)的总耗时(含启动 pytest,PostgreSQL 本机):每个测试 drop_all + create_all {a[1] / 1000:.2f} 秒;每个测试之后 TRUNCATE {b[1] / 1000:.2f} 秒;外层事务加保存点回滚 {c_[1] / 1000:.2f} 秒。回滚方案最快,因为不用改动表;表更多、数据库更慢(比如不是本机)时差距会更大(这里没有验证)。", b=bars([['drop + create', a[1] / 1000, f'{a[1] / 1000:.2f} s'], ['TRUNCATE', b[1] / 1000, f'{b[1] / 1000:.2f} s'], ['保存点回滚', c_[1] / 1000, f'{c_[1] / 1000:.2f} s']], a[1] / 1000, mark=[0], done=[2, 1]), t=tl(S(2)), done=lidx(S(2), 'TRUNCATE', '保存点'), mark=lidx(S(2), 'drop_all'), kv=KV([['drop + create', f'{a[1] / 1000:.2f} 秒'], ['TRUNCATE', f'{b[1] / 1000:.2f} 秒'], ['保存点回滚', f'{c_[1] / 1000:.2f} 秒']], ['保存点回滚'])),
    step("保存点方案的做法:fixture 里取一个连接并开外层事务,创建 Session(bind=conn, join_transaction_mode=\"create_savepoint\"),再把 db.session 换成指向它的 scoped_session;应用代码里的 commit() 只提交到保存点,测试结束时回滚外层事务。测试里应用代码 commit 过之后,数据库里实际留下的行数是 0。(我第一次直接把 db.session 赋成 Session 对象,Flask-SQLAlchemy 里的 Model.query 会调用 db.session(),报「'Session' object is not callable」,要包一层 scoped_session。)", t=tl(S(3)), done=lidx(S(3), '留下的行数'), kv=KV([['join_transaction_mode', 'create_savepoint:commit 只提交到保存点'], ['结束时', '回滚外层事务,数据库不留任何数据']], ['join_transaction_mode'])),
]
A = mkartf('f155', 155, 'Flask,测试,数据库事务,回滚,SQLAlchemy,真实验证,动画演示',
    f'在真实的 PostgreSQL 上用 pytest 比较测试数据库隔离策略:不清理会互相污染;drop_all 加 create_all {a[1] / 1000:.2f} 秒、TRUNCATE {b[1] / 1000:.2f} 秒、外层事务加保存点回滚 {c_[1] / 1000:.2f} 秒(100 个测试);保存点方案里应用代码的 commit 不会留下数据。',
    '测试里怎么让数据库每个用例都是干净的?drop_all、TRUNCATE、事务回滚各有多快?应用代码里的 commit 会不会破坏回滚?这篇用真实的 PostgreSQL 与 pytest 把三种做法的隔离与耗时量出来。',
    [('2 passed', '三种清理策略下两个有依赖关系的测试的结果(不清理时是 1 failed)'), (f'{a[1] / 1000:.2f} → {c_[1] / 1000:.2f} 秒', '100 个测试:drop_all 加 create_all 与保存点回滚的总耗时'), ('0 行', '保存点方案下,应用代码 commit 之后数据库里实际留下的行数')],
    [('四种策略的隔离', '<p>上一篇:<a href="flask-fixtures-app-factory.html">Fixture 与测试应用工厂</a>;下一篇:<a href="flask-test-session.html">测试 Session</a>。</p>'), ('耗时对比', None), ('保存点方案', '<p>数据库是自己起的 PostgreSQL(非默认端口)。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、SQLAlchemy 2.1.1、psycopg 3.3.6、pytest 9.1.1', '没有验证:数据库不在本机时的耗时差别、多线程或多进程访问同一个数据库的测试(回滚方案只对同一个连接可见)、pytest-xdist 并行、迁移(Alembic)在测试库上的创建方式、测试里用到真实 commit 的场景(如测试 after-commit 钩子)'], '测试数据库事务')
