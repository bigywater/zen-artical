from lib import *
R = J('d41')
def L(k): return [l for l in R[k].splitlines()]
steps = [
    step("QuerySet.explain() 让数据库给出执行计划,不带 analyze 时并不真正执行查询。20 万行的表上按没有索引的 customer 过滤:PostgreSQL → Seq Scan on lab_order … Filter: (customer = 42),估算返回 199 行;SQLite 的输出是一行 SCAN lab_order(格式不同、信息少得多)。", t=tl(L('basic')[:6], cur=[0, 1], mark=[5]), kv=KV([['无索引', 'Seq Scan / SCAN'], ['不同后端', '输出格式完全不同']], ['无索引'])),
    step("在 customer 上加索引并 ANALYZE 之后,同一个查询的计划变成 Bitmap Heap Scan + Bitmap Index Scan on order_customer_idx,估算成本从 3774 降到 536。而 amount__gt=100(amount 没有索引、匹配几乎所有行)仍是 Seq Scan,估算返回 199921 行——匹配的行太多时,规划器本来就不会用索引。", t=tl(L('index'), cur=[1, 2, 3], mark=[6, 7]), kv=KV([['有索引', 'Bitmap Index Scan'], ['选择性差', '仍然 Seq Scan']], ['选择性差'])),
    step("explain(analyze=True) 会真的执行查询并给出实际耗时:实际 0.175 ms、返回 200 行、200 个 heap block;估算 rows=199 与实际 200 很接近。format='json' 返回 JSON(顶层键 Plan);buffers=True(需要 analyze)加上 Buffers: shared hit=2 这类缓冲区统计。", t=tl(L('analyze')[:9], cur=[0, 7], mark=[6]), kv=KV([['analyze=True', '真的执行,给出实际时间'], ['buffers', '需要 analyze']], ['analyze=True'])),
    step("边界:explain 只能用在 QuerySet 上,qs.count() 返回 int,没有 explain;聚合查询(values().annotate())可以 explain,计划以 Finalize GroupAggregate 开头。analyze 会执行语句——对有副作用的操作要小心(本文只对 SELECT 使用)。", t=tl(L('misc')), kv=KV([['explain', '只在 QuerySet 上']], ['explain'])),
]
A = dict(
    n=41, series='django', tags='Django,ORM,explain,执行计划,PostgreSQL,真实验证,动画演示',
    desc='用 QuerySet.explain() 在 PostgreSQL 与 SQLite 上看执行计划:无索引 Seq Scan、加索引后 Bitmap Index Scan(估算成本 3774 → 536)、选择性差时仍全表扫描;analyze=True 给出实际耗时(0.175 ms),buffers / format 选项;explain 只能用在 QuerySet 上。',
    lead='ORM 生成的 SQL 慢,第一步不是猜,是看执行计划。QuerySet.explain() 一行代码就能做到。这篇在 20 万行的 PostgreSQL 表上,看索引前后计划的变化,以及 analyze 选项。',
    facts=[('3774 → 536', '给 customer 加索引前后,PostgreSQL 估算的查询成本'), ('Seq Scan', '匹配大多数行(amount > 100)时,即使有索引也是全表扫描;这里 amount 本来也没有索引'), ('analyze=True', '真的执行语句,给出实际耗时;SQLite 的 explain 输出只有一行')],
    body=[
        sec('explain() 的基本用法', '', term('', blk('d41', 1)), '<p><code>explain()</code> 返回字符串。PostgreSQL 给出包含成本估算的计划树;SQLite 给的是「SCAN / SEARCH」的简要计划。</p>'),
        sec('索引带来的变化', '', term('', blk('d41', 2)), '<p>加索引后要 <code>ANALYZE</code> 更新统计信息,规划器才会据此选计划。选择性差的条件(匹配大多数行)全表扫描本来就更快。</p>'),
        sec('analyze 与其它选项', '', term('', blk('d41', 3)), '<p><code>analyze=True</code> 让数据库真正执行并统计,对比「估算 rows」与「actual rows」能发现统计信息过期。<code>buffers</code>、<code>verbose</code>、<code>format</code> 是 PostgreSQL 的选项(其它数据库支持的选项集不同,本文没有逐个测)。</p>'),
        sec('限制', '', term('', blk('d41', 4)), '<p>只有返回 QuerySet 的链能 <code>explain()</code>;<code>count()</code>、<code>exists()</code> 的计划要自己写等价的 QuerySet 或直接 <code>EXPLAIN</code>。</p>'),
        sec('分步演示:读执行计划', '', demo('QuerySet.explain()', [('t', 'term', '执行计划'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9410),20 万行,ANALYZE 之后;SQLite 只有 1000 行', '没有验证:MySQL 的 explain 输出与选项、大表上 analyze 的副作用(对 UPDATE/DELETE 的 explain)、复杂 JOIN 的计划阅读、pg_stat_statements'],
)
