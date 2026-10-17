from lib import *
S = SS('f99')
R = J('f99'); cc = R['concurrent']
steps = [
    step("类型严格程度:往 INTEGER 列写字符串 'abc',SQLite 成功(库里 n 就是 'abc'),PostgreSQL 抛 DataError「invalid input syntax for type integer」;往 String(5) 列写 10 个字符,SQLite 成功(完整存下 'abcdefghij'),PostgreSQL 抛 DataError「value too long for type character varying(5)」。SQLite 的列类型只是「亲和性」,不是约束;在 SQLite 上开发能跑通的代码,换到 PostgreSQL 才暴露数据问题。", t=tl(S(1)), mark=lidx(S(1), 'sqlite'), done=lidx(S(1), 'postgresql'), kv=KV([['SQLite', '类型与长度不强制'], ['PostgreSQL', '类型与长度强制,报 DataError']], ['SQLite'])),
    step("Numeric 与时区:Numeric(8,2) 存 Decimal('0.30'),两个库读回的都是 Decimal('0.30');DateTime(timezone=True) 存 12:00+08:00,PostgreSQL 读回带时区的 datetime(在会话时区里,这台机器是 Asia/Shanghai),SQLite 读回的是没有时区的 datetime(2026, 1, 1, 12, 0),时区信息丢了。", t=tl(S(2)), done=lidx(S(2), 'Decimal'), mark=lidx(S(2), '存入 12:00+08:00'), kv=KV([['Numeric', '两个库读回都是 Decimal'], ['时区', 'SQLite 读回没有时区']], ['时区'])),
    step("约束:外键指向不存在的父行,SQLite 成功写入(外键默认不强制),PostgreSQL 抛 IntegrityError「violates foreign key constraint」;LIKE 'hel%' 匹配数据 'Hello',SQLite 匹配 1 行(ASCII 不区分大小写),PostgreSQL 匹配 0 行(区分大小写)。同样的查询,结果不同。", t=tl(S(3)), mark=lidx(S(3), 'sqlite'), done=lidx(S(3), 'postgresql'), kv=KV([['外键', 'SQLite 默认不强制'], ['LIKE', 'SQLite 不区分大小写,PG 区分']], ['外键'])),
    step("自增主键:先插入得到 id 1、2,删掉 id=2 再插入,SQLite 得到 2(复用了刚删掉的最大 id),PostgreSQL 得到 3(序列只增不减)。依赖「id 不会重复出现」的代码(例如用 id 当外部引用)在 SQLite 上会出问题。", t=tl(S(4)), mark=lidx(S(4), 'sqlite'), done=lidx(S(4), 'postgresql'), kv=KV([['SQLite', '删最大 id 后会复用'], ['PostgreSQL', '序列不回退']], ['SQLite'])),
    step(f"并发写:第一个连接持有未提交的写事务 1 秒,第二个连接这时写入。SQLite(timeout 设 0.5 秒)等了约 {cc['sqlite'].split('等了 ')[1]} 后抛 OperationalError: database is locked(整个数据库同一时刻只允许一个写者);PostgreSQL 只锁行,第二个连接写不同的行没有等待({cc['postgresql'].split('等了 ')[1]})。", t=tl(S(5)), mark=lidx(S(5), 'sqlite'), done=lidx(S(5), 'postgresql'), kv=KV([['SQLite', '库级写锁,冲突时 database is locked'], ['PostgreSQL', '行级锁,不同行互不等待']], ['SQLite'])),
]
A = mkartf('f99', 99, 'Flask,SQLite,PostgreSQL,SQLAlchemy,真实验证,动画演示',
    '同一份 SQLAlchemy 代码在 SQLite 与 PostgreSQL 上的行为差异实测:类型与长度是否强制、时区是否丢失、外键是否生效、LIKE 是否区分大小写、删除最大 id 后主键是否复用、两个写者并发时 SQLite 报 database is locked 而 PostgreSQL 不等待。',
    '开发用 SQLite、线上用 PostgreSQL,会踩哪些坑?这篇用同一份代码在两个数据库上并排运行,把五类常见差异逐项打印出来。',
    [('5 类', '实测的差异:类型、时区、约束与匹配、自增、并发写'), ('database is locked', 'SQLite 上第二个写者在 0.5 秒超时后的报错'), ('0 行 vs 1 行', "LIKE 'hel%' 匹配 'Hello' 时 PostgreSQL 与 SQLite 的结果")],
    [('类型与长度', '<p>上一篇:<a href="flask-migration-rollback.html">数据迁移回滚</a>;下一篇:<a href="flask-db-reconnect.html">数据库连接断开后的恢复</a>。</p>'), ('Numeric 与时区', None), ('外键与 LIKE', '<p>SQLite 的外键默认不强制;是否能用 PRAGMA foreign_keys=ON 打开,本篇没有验证。</p>'), ('自增主键', None), ('并发写', None)],
    steps, [ENV_F + '。SQLite(Python 内置 sqlite3)、自己起的 PostgreSQL(非默认端口,会话时区 Asia/Shanghai)', '没有验证:PRAGMA foreign_keys=ON 的效果、SQLite 的 WAL 模式对并发写的改善、MySQL 的行为、JSON 与数组类型、全文搜索、事务隔离级别的差异、SQLite 在多进程 gunicorn 下的表现'], 'SQLite 与 PostgreSQL')
