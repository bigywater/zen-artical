from lib import *
R = J('d102')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
M = L('modes'); P = L('prefetch')
steps = [
    step("表里 20 万行(每行约 260 字节)。SQLite 上:list(qs) 727 ms、峰值内存 155.0 MiB;直接 for r in qs 同样把结果缓存在 QuerySet 里,726 ms、155.0 MiB;qs.iterator() 564 ms、峰值 1.7 MiB;iterator(chunk_size=500) 562 ms、0.5 MiB。", t=tl(M[:4]), mark=[0, 1], done=[2, 3], b=bars([['list(qs)', 155.0, '155.0 MiB'], ['for r in qs', 155.0, '155.0 MiB'], ['iterator()', 1.7, '1.7 MiB'], ['iterator(500)', 0.5, '0.5 MiB']], 160, mark=[0, 1], done=[2, 3]), kv=KV([['结果缓存', '普通遍历会缓存全部对象'], ['iterator()', '不缓存,内存与行数无关']], ['iterator()'])),
    step("PostgreSQL(自己起的临时实例)上结果相同:list 153.4 MiB / for 153.4 MiB / iterator() 1.7 MiB / chunk_size=500 0.4 MiB;耗时 782 / 684 / 607 / 617 ms(iterator 没有更慢,这里还略快,可能是不用建缓存列表)。", t=tl(M[4:]), done=[2, 3], kv=KV([['PostgreSQL', '153.4 → 1.7 MiB']], ['PostgreSQL'])),
    step("iterator() 和 prefetch_related 一起用:不给 chunk_size 直接报 ValueError(chunk_size must be provided when using QuerySet.iterator() after prefetch_related());给了 chunk_size=20000,处理 6 万行(3 批)共 4 次查询,其中预取 tag 的有 3 次——预取按批做。SQLite 与 PostgreSQL 一致。", t=tl(P[:2]), mark=[0], done=[1], kv=KV([['prefetch + iterator', '必须给 chunk_size'], ['预取', '每一批一次']], ['prefetch + iterator'])),
    step("iterator() 不缓存:对同一个 QuerySet 想遍历第二遍,要再发一次查询。实测:两次 iterator()(各只取第一条)共 2 次查询;普通遍历两次只有 1 次查询(第二次用缓存)。", t=tl(L('nocache')), kv=KV([['iterator()', '每次都重新查询'], ['普通遍历', '第二次用缓存']], ['iterator()'])),
]
A = dict(
    n=102, series='django', tags='Django,iterator,内存,QuerySet,真实验证,动画演示',
    desc='遍历 20 万行:list() 与直接 for 峰值内存 155.0 MiB,iterator() 1.7 MiB、chunk_size=500 时 0.5 MiB;PostgreSQL 上同样;iterator() 与 prefetch_related 一起用必须给 chunk_size;iterator() 之后不缓存。',
    lead='QuerySet 遍历时会把所有结果对象缓存在 _result_cache 里。表大了,一次 for 循环就是几百 MiB。iterator() 让 Django 分批取、用完即弃。这篇量一下 20 万行数据的内存和耗时,再看它与 prefetch_related 的配合。',
    facts=[('155.0 → 1.7 MiB', '20 万行遍历的峰值内存:list() → iterator()(SQLite)'), ('153.4 → 1.7 MiB', '同样的对比,在自己起的 PostgreSQL 上'), ('chunk_size', 'iterator() 与 prefetch_related 同用时必须指定')],
    body=[
        sec('三种遍历方式', '', term('', blk('d102', 1)), '<p>峰值内存用 <code>tracemalloc</code> 测得(单独一次运行,不与计时混在一起)。<code>list(qs)</code> 与普通 <code>for</code> 都把 20 万个模型对象留在内存里;<code>iterator()</code> 只保留当前批次,内存基本与总行数无关。<code>chunk_size</code> 调小还能再降内存,代价是与数据库的往返更多(本文没有量化这一点)。</p>'),
        sec('和 prefetch_related 一起用', '', term('', blk('d102', 3)), '<p>Django 4.1 起 <code>iterator()</code> 支持 <code>prefetch_related</code>,前提是显式给出 <code>chunk_size</code>;预取是每一批做一次。</p>'),
        sec('不缓存意味着什么', '', term('', blk('d102', 4)), '<p>拿到 <code>iterator()</code> 就只能消费一遍。如果之后还要再遍历同一批数据,要么再查一次,要么就不要用 <code>iterator()</code>。</p>'),
        sec('关于服务端游标', '', '<p>我在 PostgreSQL 上另外查了一次:<code>iterator()</code> 取完第一批后,从另一个连接看 <code>pg_stat_activity</code>,没有处于非 idle 的语句(输出 0)。但我<b>没有</b>查 <code>pg_cursors</code>,所以「Django 用了服务端游标」这一机制本文没有验证——只能确认内存确实下降了。</p>'),
        sec('分步演示:内存与耗时', '', demo('iterator() 的效果', [('t', 'term', '输出'), ('b', 'bars', '峰值内存'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。表 lab_row 20 万行,每行约 260 字节(整型、40 字符串、200 字符文本、外键);SQLite 与自己起的临时 PostgreSQL 16 各测一遍;内存用 tracemalloc,每种方式独立进程测', '没有验证:服务端游标的实际使用、MySQL 的行为、iterator() 的耗时随 chunk_size 变化、多线程并发遍历、DISABLE_SERVER_SIDE_CURSORS 设置(与 pgbouncer 事务池化的兼容)'],
)
