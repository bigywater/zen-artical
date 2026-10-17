from lib import *
R = J('d32')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
ops = L('ops'); dyn = L('dyn'); mu = L('multi'); ex = L('excl')
steps = [
    step("Q 对象用 & | ~ 组合,变成 SQL 里的 AND / OR / NOT:Q(a) | Q(b) → (a OR b);(Q(a) & Q(b)) | Q(c) → ((a AND b) OR c);~Q(a) → NOT (a);~(Q(a) | Q(b)) → NOT (a OR b);filter(Q(a), Q(b)) 的两个位置参数是 AND。", t=tl(ops, cur=[2, 4, 6, 8, 10]), kv=KV([['&', 'AND'], ['|', 'OR'], ['~', 'NOT']], ['~'])),
    step("动态拼条件:q = Q(); q &= Q(**{k: v}) 逐个拼,结果与手写一致;Q() 是空条件,filter(Q()) 不过滤;Q() | Q(price__gt=50) 里空 Q 被忽略,得到的就是 price>50(而不是「永远为真」);functools.reduce(or_, [], Q()) 对空列表得到的是空 Q,而空 Q 会让 filter 不过滤——OR 拼接的初始值和空列表要小心。", t=tl(dyn, cur=[0, 1, 2, 3], mark=[4, 5]), kv=KV([['空 Q', 'AND 里无影响,| 里被忽略'], ['空列表 OR', '会退化成「不过滤」']], ['空列表 OR'])),
    step("多值关系(一对多)上,filter(a, b) 与 filter(a).filter(b) 语义不同:filter(books__price__gt=25, books__title='ann0') 要求同一本书同时满足两个条件(1 次 INNER JOIN),ann 没有 → [];分开写 filter(a).filter(b) 各自 JOIN 一次(2 次 INNER JOIN),ann 有价格>25 的书 ann2、也有书名 ann0 的书 ann0 → ['ann']。", t=tl(mu, cur=[0], mark=[1]), kv=KV([['同一个 filter 里', '同一个关联对象'], ['链式 filter', '各自独立的关联对象']], ['链式 filter'])),
    step("exclude() 与多值关系:exclude(books__price__gt=45) 用的是 NOT EXISTS 子查询,含义是「没有价格>45 的书」——ann(最贵 30)和没有书的 dan 都在结果里;而 filter(books__price__lte=45).distinct() 是「有价格≤45 的书」,dan 不在、bob 因为有一本 40 在。exclude 不等于「filter 取反」。", t=tl(ex, cur=[0, 3], mark=[4]), kv=KV([['exclude', '没有任何一本满足'], ['filter(lte)', '至少一本满足']], ['exclude'])),
]
A = dict(
    n=32, series='django', tags='Django,ORM,Q对象,查询,真实验证,动画演示',
    desc='实测 Q 对象:& | ~ 对应的 SQL、动态拼条件与空 Q 的陷阱(空 Q 在 | 里被忽略);多值关系上 filter(a, b) 与 filter(a).filter(b) 的语义差别;exclude 用 NOT EXISTS 子查询,与 filter 取反不同。',
    lead='Q 对象看起来只是把 OR 写成了 |,但用起来有几个反直觉的地方:空 Q 怎么算,链式 filter 和一个 filter 有什么差别,exclude 到底排除了什么。这篇每个都用数据说话。',
    facts=[('空 Q', 'Q() | Q(x) 得到的是 Q(x)(空 Q 被忽略),reduce(or_, [], Q()) 对空列表就是「不过滤」'), ('同一个 filter', '多值关系上 filter(a, b) 要求同一个关联对象同时满足;filter(a).filter(b) 不要求'), ('exclude', 'exclude 多值关系用 NOT EXISTS 子查询,含义是「没有任何一个满足」')],
    body=[
        sec('组合与 SQL', '', term('', blk('d32', 1)), '<p>数据:ann 三本书(10/20/30),bob 两本(40/50),cat 一本(60),dan 没有书。上面每一行都是结果加对应的 WHERE 子句。</p>'),
        sec('动态拼条件', '', term('', blk('d32', 2)), '<p>按用户选择的过滤条件拼 <code>Q</code> 是最常见的用法。注意 <code>Q()</code> 的「空」在 AND 里是单位元(没影响),在 OR 里被忽略而不是「永真」——<b>用户一个条件都没选</b>时你拼出来的 OR 会是空 Q,结果是不过滤而不是无结果。</p>'),
        sec('多值关系:一个 filter 还是两个', '', term('', blk('d32', 3)), '<p>这个差别文档里有专门一节。简单记:同一个 <code>filter()</code> 里的多个条件作用于「同一个关联对象」;分成两个 <code>filter()</code> 就成了两个独立的关联对象。</p>'),
        sec('exclude 不是取反', '', term('', blk('d32', 4)), '<p>对多值关系,<code>exclude(books__price__gt=45)</code> 要求「没有任何一本」满足条件。想要「至少有一本 ≤ 45」应当用 <code>filter</code> + <code>distinct</code>。</p>'),
        sec('分步演示:Q 的四个坑', '', demo('Q 对象', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;str(qs.query) 里的参数是直接拼接的显示值', '没有验证:PostgreSQL / MySQL 上 exclude 子查询的性能、Q 与 F / 表达式混用、对 JSONField 路径的 Q、大量 OR 条件的编译代价'],
)
