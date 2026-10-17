from lib import *
S = SS('f94')
R = J('f94'); cc = R['conc']
p, g, rt = cc['没有锁(Plain)'], cc['乐观锁,冲突就放弃(Versioned)'], cc['乐观锁 + 重试(Versioned)']
steps = [
    step(f"丢失更新:两个会话都读到 n=0,各自加 10 再提交,没有任何锁;期望 20,库里实际 {R['lost']}。ORM 发出的 UPDATE 是 UPDATE plain SET n=... WHERE plain.id = ...,只按主键找行,不关心行有没有被别人改过。", t=tl(S(1)), mark=lidx(S(1), '实际库里'), kv=KV([['无锁的读改写', '后提交的覆盖先提交的'], ['UPDATE 条件', '只有主键']], ['无锁的读改写'])),
    step(f"version_id_col:UPDATE 变成 UPDATE versioned SET n=..., ver=... WHERE versioned.id = ... AND versioned.ver = ...(版本号作为条件并自增)。两个会话读到的版本号都是 1;先提交的成功(库里 n={R['after'][0]}、ver={R['after'][1]});后提交的那条 UPDATE 没匹配到行,抛 StaleDataError「UPDATE statement on table 'versioned' expected to update 1 row(s); 0 were matched.」。", t=tl(S(2)), done=lidx(S(2), '先提交', '库里'), mark=lidx(S(2), 'StaleDataError'), kv=KV([['UPDATE', 'WHERE id = ? AND ver = ?'], ['冲突', 'StaleDataError']], ['冲突'])),
    step(f"8 个线程各给同一行加 1、共 20 次(期望 160):没有锁最终 n={p[0]}(大量丢失更新);乐观锁但冲突就放弃,最终 n={g[0]}、冲突 {g[1]} 次(不会写错,只是失败了);乐观锁加重试,最终 n={rt[0]},重试 {rt[1]} 次,耗时 {rt[2]:.0f} ms。乐观锁让「错」变成「冲突」,正确性要靠重试来换。热点行上冲突很多,重试成本不小。", b=bars([['无锁 最终值', p[0], str(p[0])], ['乐观锁不重试', g[0], str(g[0])], ['乐观锁 + 重试', rt[0], str(rt[0])]], 160, mark=[0, 1], done=[2]), t=tl(S(3)), mark=lidx(S(3), '没有锁', '冲突就放弃'), done=lidx(S(3), '乐观锁 + 重试'), kv=KV([['无锁', f'{p[0]} / 160'], ['乐观锁不重试', f'{g[0]} / 160,冲突 {g[1]} 次'], ['乐观锁 + 重试', f'{rt[0]} / 160,重试 {rt[1]} 次']], ['乐观锁 + 重试'])),
    step("HTTP API 里的乐观锁:GET 返回 ETag: \"1\"(版本号);第一个客户端带 If-Match 更新,200;第二个客户端用同一个旧 ETag 更新,版本已变,412 {'error': '版本已变化'};重新 GET 得到的新 ETag 是 \"2\"。视图里先比较版本,再靠 StaleDataError 兜住比较之后到提交之前的竞争(409)。", t=tl(S(4)), done=lidx(S(4), 'ETag', '第一个客户端'), mark=lidx(S(4), '第二个客户端'), kv=KV([['If-Match 匹配', '200'], ['If-Match 不匹配', '412'], ['比较后到提交前的竞争', 'StaleDataError → 409']], ['If-Match 不匹配'])),
]
A = mkartf('f94', 94, 'Flask,SQLAlchemy,乐观锁,version_id_col,并发,真实验证,动画演示',
    f'在真实的 PostgreSQL 上实测乐观锁:无锁时丢失更新(期望 20 实际 {R["lost"]})、version_id_col 的 UPDATE 带版本条件与 StaleDataError、8 线程各加 20 次时无锁最终 {p[0]}、乐观锁不重试 {g[0]}、加重试 {rt[0]}(重试 {rt[1]} 次)、ETag 与 If-Match 返回 412。',
    '怎么避免两个请求同时改同一行而互相覆盖?乐观锁的 UPDATE 长什么样?冲突了怎么办?这篇在真实的 PostgreSQL 上用多线程把无锁、乐观锁、乐观锁加重试的结果摆在一起。',
    [(f'{p[0]} → {rt[0]}', '8 线程各加 20 次(期望 160):无锁与乐观锁加重试的最终值'), (f'{rt[1]} 次', '乐观锁加重试时的冲突与重试次数'), ('412', '带过期的 If-Match 更新时的状态码')],
    [('丢失更新', '<p>上一篇:<a href="flask-expire-on-commit.html">expire_on_commit</a>;下一篇:<a href="flask-pessimistic-lock.html">悲观锁</a>。</p>'), ('version_id_col', None), ('并发下的三种做法', '<p>线程里每个都用自己的 Session,sleep(1 ms) 放大读改写之间的窗口。</p>'), ('ETag 与 If-Match', None)],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口)', '没有验证:version_id_generator 自定义版本号(如时间戳或 UUID)、批量 UPDATE 语句(core update())不经过 version_id_col 的情况、SERIALIZABLE 隔离级别下的另一种解法、多行聚合冲突'], '乐观锁', panels=[('t', 'term', '实验输出'), ('b', 'bars', '最终值'), ('kv', 'kv', '要点')])
