from lib import *
R = J('d115')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
c = L('conc')
steps = [
    step("外键懒加载:await Post.objects.afirst() 之后访问 post.author → SynchronousOnlyOperation(懒加载是同步查询);用 select_related('author') 取出来就可以直接读 post.author.name;反向关系 p.author.post_set.all() 用 for 遍历也报错,用 async for 遍历才可以。", t=tl(L('fk')), mark=[0, 2], done=[1, 3], kv=KV([['懒加载', 'async 里不行'], ['解法', 'select_related / async for']], ['解法'])),
    step("事务:async 里 with transaction.atomic() → SynchronousOnlyOperation;async with transaction.atomic() → TypeError('Atomic' object does not support the asynchronous context manager…)。可行做法:把事务放进用 sync_to_async 包起来的同步函数里,里面照常用 atomic。", t=tl(L('tx')), mark=[0, 1], done=[2], kv=KV([['async 事务', '不支持'], ['做法', 'sync_to_async + 同步 atomic']], ['做法'])),
    step("async ORM 其实是把同步 ORM 放进线程里跑:给 SQLCompiler.execute_sql 打点,事件循环在 MainThread,acount() / aget() 执行 SQL 的线程是 ThreadPoolExecutor-0_0,而且两次是同一个线程。", t=tl(L('thread')), kv=KV([['a 前缀方法', '在线程里执行同步查询']], ['a 前缀方法'])),
    step("因此并发查询是排队的:PostgreSQL 上 gather 10 个 pg_sleep(0.2) 的 async 查询,总耗时约 2030 ms,同一时刻正在执行 pg_sleep 的连接只有 1 个。改用 thread_sensitive=False 的同步查询(每个线程自己关连接):约 227 ms,同一时刻有 10 个连接在执行。", t=tl(c), b=bars([['10 个 async 查询(默认)', 2030, '≈ 2030 ms'], ['10 个 thread_sensitive=False', 227, '≈ 227 ms']], 2100, mark=[0], done=[1]), kv=KV([['async ORM', '串行,1 个连接'], ['thread_sensitive=False', '并行,10 个连接']], ['async ORM'])),
]
A = dict(
    n=115, series='django', tags='Django,异步,ORM,事务,PostgreSQL,真实验证,动画演示',
    desc='异步 ORM 的限制(Django 6.1.1 / PostgreSQL):外键懒加载与反向关系遍历要用 select_related / async for;async 里没有异步事务;a 前缀方法底层是线程里的同步查询,所以 10 个并发 async 查询排队执行(≈2030 ms、1 个连接)。',
    lead='Django 的异步 ORM 有 a 前缀的方法和 async for,看起来什么都能 await 了。这篇列出还不能做的事:懒加载、事务;并且在 PostgreSQL 上量一下「并发查询」是不是真的并发。',
    facts=[('懒加载不行', 'async 里访问未取出的外键 → SynchronousOnlyOperation'), ('没有 async 事务', 'async with atomic() → TypeError'), ('≈2030 ms', '10 个各 0.2 s 的 async 查询 gather 的耗时:串行执行,1 个连接')],
    body=[
        sec('外键与反向关系', '', term('', blk('d115', 1))),
        sec('事务', '', term('', blk('d115', 2))),
        sec('底层其实是线程', '', term('', blk('d115', 3)), '<p>a 前缀方法本身是 async,但查询仍是同步的数据库驱动调用,被放到线程里执行。所以它的好处是「不阻塞事件循环」,不是「数据库查询并行」。</p>'),
        sec('并发查询排队', '', term('', blk('d115', 4)), '<p>要真正并发地跑多个数据库查询,只能用 <code>thread_sensitive=False</code> 把它们放到不同线程——但每个线程会自己开连接,要自己负责关闭(实验里用 <code>connection.close()</code>),连接数会随并发数增长。(用 <code>pg_sleep</code> 模拟的是「慢查询」,没有测真实业务查询。)</p>'),
        sec('分步演示', '', demo('异步 ORM 的边界', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自己起的临时 PostgreSQL 16(fsync=off);并发数 10;连接数由另一个连接查 pg_stat_activity(state=active 且 query 含 pg_sleep)得出', '没有验证:异步驱动(如 psycopg 的 async 连接池)下的行为、CONN_MAX_AGE 与线程连接的关系、prefetch_related 在 async 中的用法、Django 更早版本'],
)
