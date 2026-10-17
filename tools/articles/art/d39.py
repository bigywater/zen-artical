from lib import *
R = J('d39')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("自定义 Lookup __ne(不等于)与 Transform __abs(取绝对值)的 SQL:score__ne=5 → WHERE score <> 5;score__abs=5 → WHERE ABS(score) = 5;score__abs__gt=498 → ABS(score) > 498;两者可以叠加 score__abs__ne=5 → ABS(score) <> 5。", t=tl(L('sql'), cur=[0, 1, 2, 3]), kv=KV([['Lookup', '生成一个比较(WHERE 的右半)'], ['Transform', '生成一个函数,可以继续接 lookup']], ['Transform'])),
    step("Transform 也能用在 values_list(score__abs)、order_by(score__abs)。因为注册在 Field 基类上,所有字段类型都能用:CharField 上写 name__abs=1 会在 SQL 里生成 ABS(name),由数据库报错(function abs(character varying) does not exist)——注册得太宽,错误要到数据库才暴露。", t=tl(L('misc'), cur=[0, 1], mark=[3]), kv=KV([['注册在 Field 上', '所有字段都能用,错误推迟到数据库']], ['注册在 Field 上'])),
    step("与函数索引配合(PostgreSQL EXPLAIN):有 Lower(name) 索引时,annotate(l=Lower('name')).filter(l='name777') → Index Scan using person_lower_name_idx;但 filter(name__iexact=…) 生成的是 UPPER(name) = UPPER(…),用不上这个 Lower 索引 → Seq Scan;普通 name=… 没有 name 上的索引也是 Seq Scan。", t=tl(L('plan'), cur=[0], mark=[1, 2]), kv=KV([['函数索引', '表达式要和查询里的表达式一致才能用上']], ['函数索引'])),
    step("注册是全局的:IntegerField().get_lookup('ne') 和 CharField().get_lookup('ne') 都是 NotEqual;IntegerField 共有 19 个 lookup(含 ne),get_transform('abs') 是 AbsoluteValue。", t=tl(L('reg'), cur=[0, 1]), kv=KV([['register_lookup', '装饰器注册,全局生效']], ['register_lookup'])),
]
A = dict(
    n=39, series='django', tags='Django,ORM,Lookup,Transform,PostgreSQL,真实验证,动画演示',
    desc='实测自定义 Lookup(__ne)与 Transform(__abs):生成的 SQL、叠加使用、在 values_list / order_by 里的使用;注册在 Field 基类上会让所有字段都有它;PostgreSQL EXPLAIN 显示 Lower(name) 函数索引对 annotate(Lower) 有效,对 __iexact(UPPER)无效。',
    lead='Lookup 和 Transform 是 ORM 的扩展点:一个生成比较,一个生成函数。这篇各写一个,看它们怎么出现在 SQL 里、怎么叠加,再验证函数索引到底什么时候能用上。',
    facts=[('叠加', 'score__abs__gt=498 → ABS(score) > 498,Transform 后面还能接 lookup'), ('Index Scan vs Seq Scan', 'Lower(name) 索引对 annotate(Lower).filter 生效;__iexact 生成 UPPER(name),用不上'), ('注册太宽', '注册在 Field 上,CharField 也有 __abs,错误要到数据库才报')],
    body=[
        sec('自定义 Lookup 与 Transform', '', term('', blk('d39', 1)), '<p>Lookup 继承 <code>Lookup</code> 并实现 <code>as_sql</code>;Transform 继承 <code>Transform</code>,给出 <code>function</code> 和 <code>output_field</code>。装饰器 <code>@Field.register_lookup</code> 把它们挂到字段类上。</p>'),
        sec('使用与边界', '', term('', blk('d39', 2)), '<p>Transform 可以出现在 <code>filter</code>、<code>values</code>、<code>order_by</code>。想限制只给特定字段用,注册到具体的字段类(如 <code>IntegerField</code>)而不是 <code>Field</code>,并且最好在 lookup 里做类型检查(本文没有做)。</p>'),
        sec('和函数索引', '', term('', blk('d39', 3)), '<p>数据库只有在查询里的表达式与索引定义完全一致时才会用索引:<code>Lower(name)</code> 索引对应 <code>LOWER(name)</code>,而 Django 的 <code>iexact</code> 在 PostgreSQL 上生成的是 <code>UPPER(name) = UPPER(…)</code>。要让 <code>iexact</code> 用上索引,索引表达式要写成 <code>Upper</code>(本文没有验证这一点)。</p>'),
        sec('注册的范围', '', term('', blk('d39', 4)), '<p>注册是进程级别的全局操作,模型导入时执行一次。</p>'),
        sec('分步演示:Lookup 与 Transform', '', demo('自定义 Lookup 与 Transform', [('t', 'term', 'SQL / 计划'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9403),2 万行,ANALYZE 之后 EXPLAIN', '没有验证:register_lookup 上下文管理器(局部注册)、Transform 的 bilateral、自定义 lookup 在 MySQL / SQLite 上的 SQL、索引对 iexact 在 Upper 索引下是否生效'],
)
