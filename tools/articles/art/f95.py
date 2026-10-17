from lib import *
S = SS('f95')
R = J('f95'); w = R['wait']; dl = R['deadlock']; q = R['queue']
steps = [
    step("with_for_update() 在 SELECT 末尾加 FOR UPDATE;read=True 是 FOR SHARE;nowait=True 是 FOR UPDATE NOWAIT;skip_locked=True 是 FOR UPDATE SKIP LOCKED。锁在事务结束(commit 或 rollback)时释放。", t=tl(S(1)), done=lidx(S(1), 'FOR UPDATE', 'FOR SHARE', 'NOWAIT', 'SKIP LOCKED'), kv=KV([['with_for_update()', 'FOR UPDATE'], ['read=True', 'FOR SHARE'], ['nowait / skip_locked', 'NOWAIT / SKIP LOCKED']], ['with_for_update()'])),
    step(f"同样的 8 线程 × 20 次加 1:每次先 SELECT ... FOR UPDATE 再读改写,最终 n = {R['inc'][0]}(期望 160),没有重试,耗时 {R['inc'][1]:.0f} ms;线程在锁上排队。与上一篇乐观锁对比:悲观锁一次就对,代价是同一行上的写入被串行化。", t=tl(S(2)), done=lidx(S(2), '期望 160'), kv=KV([['结果', f"{R['inc'][0]} / 160,无重试"], ['代价', '同一行的写入串行']], ['结果'])),
    step(f"别人持有锁时:nowait=True 立即失败(LockNotAvailable,{w['nowait=True'][1]:.0f} ms);skip_locked=True 立即返回空(被跳过,{w['skip_locked=True'][1]:.0f} ms);lock_timeout='500ms' 等了 {w[chr(108)+'ock_timeout='+chr(39)+'500ms'+chr(39)][1]:.0f} ms 后 LockNotAvailable;默认则一直阻塞,持有者 1 秒后 commit,它等了 {w['默认'][1]:.0f} ms 才拿到。", t=tl(S(3)), mark=lidx(S(3), 'nowait', 'skip_locked', 'lock_timeout'), done=lidx(S(3), '默认'), kv=KV([['默认', '阻塞到拿到锁'], ['nowait', '立即失败'], ['skip_locked', '跳过被锁的行'], ['lock_timeout', '限时等待']], ['默认'])),
    step(f"任务队列:3 个 worker 同时取 9 个任务,每次 SELECT ... LIMIT 1 FOR UPDATE SKIP LOCKED 取下一个没人锁的任务:各拿到 3 个不同的任务(worker 0 是 {q[0]['0']},worker 1 是 {q[0]['1']},worker 2 是 {q[0]['2']}),9 个任务全部被处理、没有重复,没有互相阻塞。", t=tl(S(4)), done=lidx(S(4), '每个 worker'), kv=KV([['skip_locked', '多个消费者取不同的行'], ['结果', '9 个任务无重复']], ['skip_locked'])),
    step("死锁:两个事务以相反的顺序锁两行(A 先锁 1 再锁 2,B 先锁 2 再锁 1),约 1 秒后(PostgreSQL 的 deadlock_timeout 默认 1 秒)检测到死锁,其中一个失败(DeadlockDetected),另一个成功;两个事务都按先 1 后 2 的相同顺序加锁则都成功。加锁要有固定顺序。", t=tl(S(5)), mark=lidx(S(5), '相反顺序'), done=lidx(S(5), '相同顺序'), kv=KV([['相反顺序加锁', '死锁,约 1 秒后一个被中止'], ['相同顺序', '只排队不死锁']], ['相反顺序加锁'])),
]
A = mkartf('f95', 95, 'Flask,SQLAlchemy,悲观锁,with_for_update,死锁,真实验证,动画演示',
    f'在真实的 PostgreSQL 上实测悲观锁:with_for_update 的各种参数对应的 SQL、8 线程各加 20 次最终 {R["inc"][0]}、nowait 与 skip_locked 与 lock_timeout 的行为、skip_locked 任务队列 9 个任务无重复、相反加锁顺序约 1 秒后 DeadlockDetected。',
    '悲观锁怎么写?拿不到锁时有哪几种处理?用它做任务队列安全吗?死锁是怎么发生的、怎么避免?这篇在真实的 PostgreSQL 上用多线程把每种情况都跑一遍。',
    [(f'{R["inc"][0]} / 160', '8 线程各加 20 次,FOR UPDATE 下的最终值'), ('1 ms', 'nowait 与 skip_locked 在别人持锁时的返回时间'), ('约 1 秒', '相反加锁顺序时,PostgreSQL 检出死锁的时间')],
    [('with_for_update 的 SQL', '<p>上一篇:<a href="flask-optimistic-lock.html">乐观锁</a>;下一篇:<a href="flask-sqlalchemy-query-log.html">SQLAlchemy 查询日志</a>。</p>'), ('读改写', None), ('拿不到锁时', None), ('任务队列', None), ('死锁', '<p>两个线程各自的 Session,中间 sleep 0.3 秒保证两边都拿到了第一把锁。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口)', '没有验证:MySQL(InnoDB 间隙锁)与 SQLite(不支持 FOR UPDATE)的行为、with_for_update(of=...) 多表连接时锁哪张表、advisory lock、SERIALIZABLE 隔离级别、锁等待在高并发下的吞吐'], '悲观锁', panels=[('t', 'term', '实验输出'), ('kv', 'kv', '要点')])
