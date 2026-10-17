from lib import *
R = J('d30')
B = R['basic'].splitlines(); M = R['multi'].splitlines(); F = R['filter'].splitlines(); G = R['group'].splitlines()
steps = [
    step("aggregate() 返回一个 dict:{'total': 210, 'avg': 35.0, 'n': 6},SQL 是一条不带 GROUP BY 的聚合。annotate() 给每个对象加一列:每个作者的书数和总价,SQL 是 LEFT OUTER JOIN + GROUP BY 作者的所有列;没有书的 dan:Count = 0、Sum = None(要 Coalesce 才是 0)。", t=tl(B[:5] + B[6:], cur=[0, 2, 4]), kv=KV([['aggregate', '返回 dict'], ['annotate', '每行加一列,GROUP BY']], ['annotate'])),
    step("同时对两个多值关系聚合会被放大:Count('books') 与 Count('books__tags') 一起用,ann(3 本书、每本 2~3 个标签)得到 nb=7、nt=7,而不是 3 和 7;因为两次 JOIN 让每一行相乘。加 distinct=True 后 nb 才是 3——但这时 nt 变成「不同标签数」而不是「书-标签对数」,语义已经不同。", t=tl(M[:2], cur=[0], mark=[1]), kv=KV([['两个多值 JOIN', '行相乘,聚合被放大'], ['distinct=True', '只对计数类有效,语义会变']], ['两个多值 JOIN'])),
    step("Sum 也被放大:一旦再引入标签的 JOIN,Sum('books__price') 也被放大(ann 的 sp 从 60 变成 140)。只聚合一个多值关系时(Count + Sum 都来自 books)是对的。要同时算两个多值关系的统计,拆成两条查询、用子查询或 Count(filter=…),别指望 distinct 一劳永逸。", t=tl(M[2:4], cur=[0], mark=[1]), kv=KV([['Sum + 别的关系的 Count', '也会被放大']], ['Sum + 别的关系的 Count'])),
    step("filter 放在 annotate 之前还是之后,含义不同:filter(books__price__gt=15).annotate(n=Count('books')) → WHERE 先过滤,再聚合,n 只算价格>15 的书(ann 2、bob 2、cat 1);annotate(...).filter(books__price__gt=15) → 又 JOIN 了第二次 lab_book(别名 T3),n 被放大(ann 6、bob 4)。filter(n__gt=1) 才是 HAVING。", t=tl([l for l in F if l.strip()][:6], cur=[0, 2], mark=[4]), kv=KV([['顺序', 'filter 在前 = WHERE;在后再过滤同一关系 = 再 JOIN 一次']], ['顺序'])),
    step("想「只统计满足条件的子集,但保留所有作者」:Count('books', filter=Q(price__gt=15)) → SQL 里是 COUNT(...) FILTER (WHERE ...),dan 保留为 0,不被 WHERE 过滤掉。", t=tl([l for l in F if l.strip()][-2:], cur=[0, 1]), kv=KV([['Count(filter=Q)', '条件聚合,不删行']], ['Count(filter=Q)'])),
    step("values().annotate() 的分组:GROUP BY 只按 values 里的列(author__name);Author 的 Meta.ordering = ['name'] 在 annotate 的 SQL 里没有出现 ORDER BY——分组查询不会自动套 Meta.ordering。", t=tl([l for l in G if l.strip()][1:], cur=[0, 1]), kv=KV([['Meta.ordering', '分组查询里不生效']], ['Meta.ordering'])),
]
A = dict(
    n=30, series='django', tags='Django,ORM,聚合,annotate,aggregate,真实验证,动画演示',
    desc='实测 aggregate / annotate 与 SQL:没有关联行时 Count = 0、Sum = None;同时对两个多值关系聚合会被 JOIN 放大(ann 的书数 7 而不是 3);filter 放在 annotate 前后含义不同(WHERE / 再 JOIN / HAVING);Count(filter=Q) 生成 FILTER (WHERE);分组查询不套 Meta.ordering。',
    lead='annotate 和 aggregate 的结果为什么有时「不对」?为什么多算了几倍?filter 写在前面和后面差在哪?这篇用六条小数据把每个坑的数字和 SQL 都摆出来。',
    facts=[('7 而不是 3', '同时 Count("books") 与 Count("books__tags"),ann 的书数被放大成 7(应为 3)'), ('前后不同', 'filter 在 annotate 之前是 WHERE;之后过滤同一关系会再 JOIN 一次并放大'), ('None', '没有关联行时 Sum 是 None,要 Coalesce 才是 0')],
    body=[
        sec('aggregate 与 annotate', '', term('', blk('d30', 2)), '<p>数据:ann 3 本书(10/20/30),bob 2 本(40/50),cat 1 本(60),dan 没有书;每本书 2~3 个标签。<code>aggregate</code> 折叠成一行 dict;<code>annotate</code> 保留每个对象并加一列,靠 <code>LEFT OUTER JOIN + GROUP BY</code>。</p>'),
        sec('多个多值关系一起聚合', '', term('', blk('d30', 3)), '<p>每多一个多值 JOIN,行数就相乘。Sum、Count 都会被放大,<code>distinct=True</code> 只能修计数类,而且语义会变。可靠的做法:分开查、用子查询,或者只聚合一个多值关系。</p>'),
        sec('filter 的位置与条件聚合', '', term('', blk('d30', 4)), '<p>文档里把这叫「filter 与 annotate 的顺序」:先 filter 缩小参与聚合的行;后 filter 过滤聚合后的结果(用聚合别名时是 HAVING,用关系字段时会再 JOIN)。想保留所有对象、又只统计一部分,用 <code>Count(..., filter=Q(...))</code>。</p>'),
        sec('分组与默认排序', '', term('', blk('d30', 5)), '<p><code>values(...).annotate(...)</code> 决定 GROUP BY 的列。分组查询里没有出现 Meta.ordering 的 <code>ORDER BY</code>,需要顺序就显式 <code>order_by</code>。</p>'),
        sec('分步演示:聚合的陷阱', '', demo('annotate 与 aggregate', [('t', 'term', '输出 / SQL'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;数据量很小,只为看语义与 SQL', '没有验证:大数据量下 GROUP BY 的代价与索引、子查询聚合(Subquery + OuterRef)的写法、窗口函数、PostgreSQL 的 ArrayAgg / StringAgg、annotate 与 select_related 的组合'],
)
