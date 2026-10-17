from lib import *
S = SS('f74')
R = J('f74'); r1 = R['rev1'] if isinstance(R['rev1'], str) else str(R['rev1'])
steps = [
    step("flask db init 创建 migrations/ 目录(退出码 0):README、alembic.ini、env.py、script.py.mako 和空的 versions/。此时数据库文件都还没创建——init 只生成项目骨架。", t=tl(S(1)), done=lidx(S(1), '生成的文件'), mark=lidx(S(1), '此时数据库里的表'), kv=KV([['init', '只建 migrations/ 目录'], ['数据库', '还没动']], ['init'])),
    step("flask db migrate 对比模型与数据库,生成迁移脚本(日志:Detected added table 'user'):upgrade() 是 op.create_table('user', …),downgrade() 是 op.drop_table('user'),revision 是随机的 12 位十六进制、down_revision 是 None。执行完数据库里只有 alembic_version 一张表——migrate 只生成脚本,不改数据库。", t=tl(S(2)), done=lidx(S(2), 'upgrade', 'revision'), mark=lidx(S(2), '只生成脚本'), kv=KV([['migrate', '生成脚本,不改库'], ['revision', '随机 id,链式 down_revision']], ['migrate'])),
    step("flask db upgrade 执行迁移:Running upgrade  -> 第一个 revision,建出 user 表(id、name),alembic_version 表里存着当前 revision,flask db current 显示它是 head。", t=tl(S(3)), done=lidx(S(3), 'upgrade', 'alembic_version', 'current'), kv=KV([['upgrade', '执行脚本'], ['alembic_version', '记录当前 revision']], ['alembic_version'])),
    step("模型加了 email 列和 Post 表,再 migrate:检测到 added table 'post' 与 added column 'user.email';第二个脚本 upgrade() 里是 create_table、batch_alter_table、add_column,downgrade() 里是 batch_alter_table、drop_column、drop_table;它的 down_revision 指向第一个迁移;upgrade 之后表是 alembic_version、post、user,user 的列是 id、name、email。", t=tl(S(4)), done=lidx(S(4), 'upgrade() 里', 'upgrade 后表', 'down_revision'), kv=KV([['SQLite 加列', '用 batch_alter_table'], ['downgrade', '自动生成反向操作']], ['SQLite 加列'])),
    step("flask db downgrade 回退一步:表回到 alembic_version、user,user 的列回到 id、name。flask db history 显示版本链:base → 第一个迁移 → 第二个迁移(head)。", t=tl(S(5)), done=lidx(S(5), 'downgrade 之后', 'history'), kv=KV([['downgrade', '回退一个 revision'], ['history', '链式版本']], ['downgrade'])),
    step("自动生成的局限:把 email 列改名成 mail,migrate 把它识别成 add_column('mail') 加 drop_column('email'),老数据会丢。生成的脚本必须人工检查,改成 alter_column(new_column_name=...)——这一改法本篇没有验证。", t=tl(S(6)), mark=lidx(S(6), 'drop_column'), done=lidx(S(6), 'add_column'), kv=KV([['重命名列', '识别成 删 + 加'], ['结论', '自动脚本要人工审']], ['重命名列'])),
    step("两个开发者各自从同一个父版本生成迁移,就出现两个 head(heads: aaaa1、aaaa2);此时 flask db upgrade 报错「Multiple head revisions are present for given argument 'head'」;flask db merge 生成一个合并迁移后 heads 数变成 1。", t=tl(S(7)), mark=lidx(S(7), 'Multiple head'), done=lidx(S(7), 'flask db merge', '合并后'), kv=KV([['两个 head', 'upgrade 失败'], ['flask db merge', '生成合并迁移,heads 变 1']], ['两个 head'])),
]
A = mkartf('f74', 74, 'Flask,Flask-Migrate,Alembic,数据库迁移,真实验证,动画演示',
    '用真实的 flask db 命令在 SQLite 上走一遍 Flask-Migrate:init 生成的目录、migrate 只生成脚本、upgrade 与 alembic_version、加列加表的迁移内容(SQLite 用 batch_alter_table)、downgrade 与 history、重命名列被识别成删加、两个 head 报错与 merge。',
    'Flask-Migrate 的 init、migrate、upgrade 分别做了什么?数据库里哪张表记着当前版本?自动生成的迁移靠得住吗?两个人同时改模型会怎样?这篇用真实的命令把每一步的文件与数据库状态打印出来。',
    [('3 步', 'init / migrate / upgrade:骨架、脚本、执行,只有最后一步改数据库'), ('alembic_version', '数据库里记录当前 revision 的表'), ('删 + 加', '重命名列被自动识别成的操作,数据会丢')],
    [('flask db init', '<p>上一篇:<a href="flask-flask-wtf-validation.html">Flask-WTF 表单验证</a>;下一篇:<a href="flask-flask-caching.html">Flask-Caching</a>。</p>'), ('flask db migrate', None), ('flask db upgrade', None), ('模型变化后的迁移', None), ('downgrade 与 history', None), ('自动生成的局限', None), ('多个 head 与 merge', '<p>回滚、生产环境的迁移策略见第 97、98 篇。</p>')],
    steps, [ENV_F + '。Flask-Migrate 4.1.0(Alembic),SQLite 数据库', '没有验证:PostgreSQL / MySQL 上的 DDL 事务与锁行为(见第 99 篇)、把重命名列改写成 alter_column 后的效果、online 迁移与大表加列的耗时、flask db stamp 与手工修改 alembic_version'], 'Flask-Migrate 基础')
