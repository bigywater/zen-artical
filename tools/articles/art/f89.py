from lib import *
S = SS('f89')
R = J('f89'); co = R['cost']
f1, f2, f3 = co['每个对象都 flush'], co['每个对象都 commit'], co['全部 add 后一次 commit']
steps = [
    step("flush 把待写入的改动作为 SQL 发给数据库,但仍在事务里:add 之前和 flush 之前 a.id 都是 None;flush 之后 a.id = 1(INSERT ... RETURNING author.id, author.created);此时另一个连接查询 author 表,看不到 f1(0 行);commit 之后另一个连接才能看到(1 行)。", t=tl(S(1)), done=lidx(S(1), 'flush 之后 a.id', 'commit 之后'), mark=lidx(S(1), '此时另一个连接'), kv=KV([['flush', '发 SQL,事务未结束,别人看不到'], ['commit', '事务结束,别人才可见'], ['主键', 'flush 之后才有']], ['flush'])),
    step("autoflush:session.add 之后直接查询 count,得到 1——查询之前先自动发了 INSERT(日志里 INSERT 在 SELECT 之前);用 with db.session.no_autoflush: 包住查询,count 是 0,只发了 SELECT,INSERT 还没发。这就是「没 commit 却查得到」的原因。", t=tl(S(2)), done=lidx(S(2), 'add 之后直接查询'), mark=lidx(S(2), 'no_autoflush'), kv=KV([['autoflush', '查询前自动 flush'], ['no_autoflush', '查询不触发 flush']], ['autoflush'])),
    step("flush 之后 server_default 的值要不要再读一次(PostgreSQL 上):不用——INSERT 带 RETURNING author.id, author.created,created 属性 flush 之后已经加载,访问它再发 0 条 SELECT,值是 datetime。(没有 RETURNING 的数据库上会不会再多一条 SELECT,本篇没有验证。)", t=tl(S(3)), done=lidx(S(3), 'a.created'), kv=KV([['PostgreSQL', 'INSERT ... RETURNING 带回默认值']], ['PostgreSQL'])),
    step(f"flush 的顺序与批量:把 3 本书反序加进 session 后 flush,SQL 顺序是先 author 后 book(按外键依赖排序);100 个 Author 一次 flush 只发 {R['batch']} 条 INSERT(insertmanyvalues 批量)。", t=tl(S(4)), done=lidx(S(4), '3 本书', '100 个'), kv=KV([['顺序', '按外键依赖排序'], ['批量', '100 行 1 条 INSERT']], ['批量'])),
    step("flush 之后 rollback 能撤销已经发出的 INSERT:库里 gone 的行数是 0。", t=tl(S(5)), done=lidx(S(5), 'gone'), kv=KV([['flush 后 rollback', '撤销']], ['flush 后 rollback'])),
    step(f"代价(PostgreSQL 本机、fsync 关闭,1000 个 Author,5 次取中位数):每个对象都 flush 再最后 commit {f1:.1f} ms;每个对象都 commit {f2:.1f} ms;全部 add 后一次 commit {f3:.1f} ms。一次性提交比逐个 flush 快约 {f1 / f3:.0f} 倍,比逐个 commit 快约 {f2 / f3:.0f} 倍。", b=bars([['逐个 commit', f2, f'{f2:.0f} ms'], ['逐个 flush', f1, f'{f1:.0f} ms'], ['一次 commit', f3, f'{f3:.1f} ms']], f2, mark=[0, 1], done=[2]), t=tl(S(6)), done=lidx(S(6), '全部 add'), mark=lidx(S(6), '每个对象都'), kv=KV([['逐个 commit', f'{f2:.0f} ms'], ['逐个 flush', f'{f1:.0f} ms'], ['一次 commit', f'{f3:.1f} ms']], ['一次 commit'])),
]
A = mkartf('f89', 89, 'Flask,SQLAlchemy,flush,commit,autoflush,真实验证,动画演示',
    f'在真实的 PostgreSQL 上实测 flush 与 commit:flush 发 SQL 但别的连接看不到、commit 才可见、autoflush 与 no_autoflush、INSERT ... RETURNING 带回 server_default、按外键依赖排序与批量插入、1000 个对象逐个 flush {f1:.0f} ms 与逐个 commit {f2:.0f} ms 对一次 commit {f3:.1f} ms。',
    'flush 和 commit 到底差在哪?为什么没 commit 查询却看得到?批量写入应该怎么提交?这篇用第二个数据库连接当「别人」,把 flush 与 commit 的可见性和代价逐个量出来。',
    [('0 → 1', 'flush 之后与 commit 之后,另一个连接能看到的行数'), (f'{f3:.1f} ms', '1000 个对象全部 add 后一次 commit 的耗时'), ('RETURNING', 'PostgreSQL 上 INSERT 带回主键与 server_default')],
    [('flush 与可见性', '<p>上一篇:<a href="flask-identity-map.html">SQLAlchemy Identity Map</a>;下一篇:<a href="flask-rollback-behavior.html">Rollback 的实际行为</a>。</p>'), ('autoflush', None), ('server_default', None), ('顺序与批量', None), ('flush 后 rollback', None), ('逐个与一次提交的代价', '<p>数据库在本机、fsync 关闭,逐个 commit 的真实代价在生产环境里会大得多。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口,fsync 关闭)', '没有验证:没有 RETURNING 的数据库(MySQL)上 server_default 的读取、eager_defaults 选项、bulk_insert_mappings 与 insert() 的 core 批量写入的耗时对比、flush 过程中的触发器与外键约束延迟'], 'Flush 与 Commit', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')])
