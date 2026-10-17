from lib import *
S = SS('f98')
R = J('f98'); hf = R['half']
steps = [
    step("downgrade 之后数据没了:加 score 列并写入 ('ann', 42);downgrade(drop_column)之后列只剩 id、name;再 upgrade 把 score 列加回来,但 ann 的 score 是 None——42 回不来。所以回滚一个删列的迁移,代价是那一列的数据;要先备份,或者不要把「删列」放进能随手回滚的迁移里。", t=tl(S(1)), done=lidx(S(1), 'upgrade 后'), mark=lidx(S(1), '丢了'), kv=KV([['downgrade 删列', '列里的数据一起没了'], ['再 upgrade', '只加回空列']], ['downgrade 删列'])),
    step(f"迁移到一半失败:同一个迁移里先加可空的 a_col(成功)、再加 NOT NULL 的 b_col(表里已有一行,必然失败)。PostgreSQL 上整个迁移回滚:失败后列还是 id、name,alembic_version 仍是 r001;错误是 NotNullViolation: column \"b_col\" of relation \"user\" contains null values。SQLite 上第二步报「Cannot add a NOT NULL column with default value NULL」,但第一步已经生效:失败后列是 id、name、a_col,alembic_version 仍是 r001;不修问题直接再 upgrade,错误变成「duplicate column name: a_col」——数据库已经处在半应用状态,需要手工清理。", t=tl(S(2)), done=lidx(S(2), '[pg] 失败之后'), mark=lidx(S(2), '[sqlite] 失败之后', 'duplicate column'), kv=KV([['PostgreSQL', 'DDL 在事务里,失败整体回滚'], ['SQLite', '失败时已执行的部分保留']], ['SQLite'])),
    step("不可逆的迁移:downgrade 里主动 raise NotImplementedError('这个迁移不可逆:原来的大小写已经丢了'),downgrade 退出码 1、给出这条错误,版本记录仍停在 r002,没有悄悄做一个不对的回滚。比起 pass 掉 downgrade,明确报错更诚实。", t=tl(S(3)), mark=lidx(S(3), 'downgrade →'), done=lidx(S(3), '版本记录'), kv=KV([['不可逆', 'downgrade 里主动报错'], ['版本记录', '保持在原位']], ['不可逆'])),
    step("downgrade 的目标:从 r003 开始,flask db downgrade -- -1 回退一步到 r002(列 id、name、c2);downgrade r001 回到 r001(列 id、name);downgrade base 回到最初,alembic_version 表里没有版本行,业务表都没了(只剩 alembic_version 这张表)。直接写 flask db downgrade -1 时版本没有变化(仍是 r003),要写成 downgrade -- -1。", t=tl(S(4)), done=lidx(S(4), 'downgrade -- -1', 'downgrade r001', 'downgrade base'), kv=KV([['-- -1', '回退一步'], ['r001', '回到指定版本'], ['base', '回到没有任何迁移']], ['-- -1'])),
]
A = mkartf('f98', 98, 'Flask,Flask-Migrate,downgrade,回滚,事务性DDL,真实验证,动画演示',
    '实测迁移回滚:downgrade 删列后数据不会回来;同一个迁移里第二步失败时,PostgreSQL 整体回滚而 SQLite 留下半应用状态(再 upgrade 报 duplicate column);不可逆迁移在 downgrade 里主动报错;downgrade 到 -1、指定版本与 base。',
    '迁移失败了会怎样?回滚能把数据找回来吗?为什么不同数据库上失败后的状态不一样?这篇用真实的 PostgreSQL 与 SQLite 把几种失败与回滚的结局放在一起对照。',
    [('NotNullViolation / 半应用', '同一个迁移失败时,PostgreSQL 整体回滚,SQLite 留下 a_col'), ('数据回不来', 'downgrade 删掉的列再 upgrade 回来之后值是 None'), ('-- -1', 'flask db downgrade 回退一步的写法')],
    [('回滚丢数据', '<p>上一篇:<a href="flask-migration-files.html">Flask-Migrate Migration 文件</a>;下一篇:<a href="flask-sqlite-vs-postgresql.html">SQLite 与 PostgreSQL 行为差异</a>。</p>'), ('迁移到一半失败', None), ('不可逆迁移', None), ('downgrade 的目标', None)],
    steps, [ENV_F + '。Flask-Migrate 4.1.0(Alembic)、自己起的 PostgreSQL(非默认端口)、SQLite', '没有验证:MySQL(DDL 会隐式提交)上的半应用状态、transaction_per_migration 配置、PostgreSQL 上 CREATE INDEX CONCURRENTLY 这类不能在事务里执行的语句、多步迁移分成多个文件的做法、大表上回滚的耗时与锁'], '数据迁移回滚')
