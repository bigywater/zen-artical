from lib import *
S = SS('f90')
R = J('f90'); sq = R['seq']
steps = [
    step(f"rollback 之后对象的状态:改了 bal 的 a 从 persistent 变成 persistent (expired),再访问 a.bal 重新发 1 条 SELECT,读到数据库里的 {R['a_bal']},内存里改成的 999 丢了;已经 flush 的新对象 new 从 persistent 变成 transient(不再属于 session,也没有数据库行);已经 delete 并 flush 的 d 从 deleted 变回 persistent (expired),数据库里的行恢复。", t=tl(S(1)), done=lidx(S(1), 'a(改了', 'd(已'), mark=lidx(S(1), 'new(已', 'rollback 之后访问'), kv=KV([['改过的对象', 'expired,重新从库里读'], ['新建并 flush 的', '变回 transient'], ['删除并 flush 的', '恢复为 persistent']], ['新建并 flush 的'])),
    step(f"rollback 撤销不了序列号:被回滚掉的 INSERT 用过 id={sq[0]},下一次成功插入的 id={sq[1]}——自增主键中间有空洞。不要假设主键连续。", t=tl(S(2)), mark=lidx(S(2), '空洞'), kv=KV([['回滚的 INSERT', f'用掉 id={sq[0]}'], ['下一次插入', f'id={sq[1]}']], ['下一次插入'])),
    step("保存点:先 add outer,begin_nested() 里 add inner 然后 sp.rollback(),最后 commit——outer 在库里,inner 不在:rollback 只回到保存点。", t=tl(S(3)), done=lidx(S(3), 'outer'), kv=KV([['begin_nested().rollback()', '只撤销保存点之内的']], ['begin_nested().rollback()'])),
    step("commit 失败(违反唯一约束,IntegrityError / UniqueViolation)之后,事务已被自动回滚,但 session 还要显式 rollback 才能继续:没 rollback 就再 add 并 commit,抛 PendingRollbackError「This Session's transaction has been rolled back due to a previous exception during flush.」;rollback() 的同时,那个在失效事务里 add 的对象被丢弃,并给出 SAWarning「Session's state has been changed on a non-active transaction - this state will be discarded.」;rollback 之后重新 add 才成功。", t=tl(S(4)), mark=lidx(S(4), 'PendingRollbackError', '警告'), done=lidx(S(4), 'rollback 之后重新来'), kv=KV([['commit 失败后', '必须 rollback()'], ['失效事务里 add 的对象', '被丢弃并有警告']], ['commit 失败后'])),
    step("底层 Core 连接更严格:违反唯一约束(UniqueViolation)之后 PostgreSQL 的事务进入 aborted 状态,接着执行 select 1 抛 InFailedSqlTransaction「current transaction is aborted, commands ignored until end of transaction block」;rollback 之后 select 1 返回 1。", t=tl(S(5)), mark=lidx(S(5), 'InFailedSqlTransaction'), done=lidx(S(5), 'rollback 之后'), kv=KV([['PG 的 aborted 事务', '只接受 rollback']], ['PG 的 aborted 事务'])),
    step("commit 之后再 rollback 什么都不撤销:库里的 committed 行数是 1。rollback 只影响还没提交的事务。", t=tl(S(6)), done=lidx(S(6), 'committed'), kv=KV([['commit 之后 rollback', '无效果']], ['commit 之后 rollback'])),
    step("Flask 里没人调用 rollback:视图 flush 之后抛异常(HTTP 500),库里没有 viewlost 这一行;PostgreSQL 里也没有留下 idle in transaction 的连接——请求结束时 session 被清理,未提交的事务被回滚。", t=tl(S(7)), done=lidx(S(7), '视图 flush', 'idle in transaction'), kv=KV([['视图抛异常', '请求结束时回滚'], ['连接', '不会停在 idle in transaction']], ['视图抛异常'])),
]
A = mkartf('f90', 90, 'Flask,SQLAlchemy,rollback,事务,真实验证,动画演示',
    f'在真实的 PostgreSQL 上实测 rollback 的实际行为:改过的对象变 expired、新建并 flush 的对象变回 transient、删除的对象恢复、序列号不回退(id {sq[0]} 之后是 {sq[1]})、保存点只回到保存点、commit 失败后 PendingRollbackError 与被丢弃的对象、Core 连接的 InFailedSqlTransaction、请求结束时的清理。',
    'rollback 之后 session 里的对象是什么状态?哪些东西回滚不了?commit 失败之后为什么还要手动 rollback?这篇用真实的 PostgreSQL 把每一种情况跑一遍。',
    [('transient', '已 flush 的新对象在 rollback 之后的状态'), (f'{sq[0]} → {sq[1]}', '回滚的 INSERT 用掉的 id 与下一次成功插入的 id,序列号不回退'), ('PendingRollbackError', 'commit 失败后没 rollback 就继续使用 session 的异常')],
    [('对象的状态', '<p>上一篇:<a href="flask-flush-commit.html">Session Flush 与 Commit</a>;下一篇:<a href="flask-connection-pool.html">数据库连接池</a>。</p>'), ('序列号', None), ('保存点', None), ('commit 失败之后', None), ('Core 连接的 aborted 事务', None), ('commit 之后 rollback', None), ('Flask 请求结束时', None)],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口)', '没有验证:MySQL 等不支持事务内 DDL 回滚的数据库、rollback 与触发器或外部副作用(发邮件、写文件)的关系、两阶段提交、多个 bind 之间的事务一致性'], 'Rollback 的实际行为')
