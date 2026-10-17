from lib import *
import re
R = J('d40')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
tm = R['time']; vals = [float(x) for x in re.findall(r'([\d.]+) µs', tm)]
steps = [
    step("QuerySet 只是包着一个 Query 对象(django.db.models.sql.query.Query):此时没有 SQL 文本。它的 where 是一棵树(WhereNode),子条件是 IntegerGreaterThan、IContains 和一个 NOT 子树;alias_map 里有参与的表别名(lab_book、lab_author);还带着 order_by、切片范围 low_mark/high_mark、select_related 等状态。", t=tl(L('query'), cur=[0, 1, 2, 3]), kv=KV([['QuerySet.query', '条件树 + 状态,不是 SQL 字符串']], ['QuerySet.query'])),
    step("编译:query.get_compiler(using=alias).as_sql() 才把它变成 SQL 与参数。同一个 Query 在 SQLite 上 icontains 是 LIKE %s ESCAPE '\\',在 PostgreSQL 上是 UPPER(title::text) LIKE UPPER(%s);参数占位符都是 %s,参数值单独返回。", t=tl(L('compile'), cur=[0, 2], mark=[1, 3]), kv=KV([['编译', '由数据库后端决定 SQL 方言'], ['参数', '与 SQL 分开']], ['编译'])),
    step(f"三个阶段的耗时(2000 次平均):构建 QuerySet(链式 filter/exclude/select_related/order_by/切片){vals[0]:.0f} µs;编译成 SQL {vals[1]:.0f} µs;从头到尾 list(build())(含 SQLite 执行和构造对象){vals[2]:.0f} µs。每个请求都会重复构建与编译(没有缓存)。", b=bars([['构建 QuerySet(µs)', vals[0], f"{vals[0]:.0f}"], ['编译 SQL(µs)', vals[1], f"{vals[1]:.0f}"], ['整个流程(µs)', vals[2], f"{vals[2]:.0f}"]], vals[2] * 1.1, mark=[2]), kv=KV([['构建 + 编译', f"≈ {vals[0] + vals[1]:.0f} µs 的纯 Python 开销"]], ['构建 + 编译'])),
    step("看 SQL 的几种办法:str(qs.query)(参数已拼入,仅供阅读,不保证能直接执行);qs.query.sql_with_params() 返回 (sql, params);CaptureQueriesContext 或 connection.queries(需要 DEBUG=True)看真实执行的语句。", t=tl(L('views'), cur=[0, 1, 2]), kv=KV([['真实发出的 SQL', 'CaptureQueriesContext']], ['真实发出的 SQL'])),
]
A = dict(
    n=40, series='django', tags='Django,ORM,SQL,编译,真实验证,动画演示',
    desc=f'拆开 Django ORM 生成 SQL 的过程:QuerySet 包着的 Query 是条件树而不是字符串;compiler 按数据库后端编译出不同方言(SQLite LIKE vs PostgreSQL UPPER(...) LIKE UPPER(...));构建 {vals[0]:.0f} µs、编译 {vals[1]:.0f} µs、整体 {vals[2]:.0f} µs;看 SQL 的几种办法。',
    lead='.filter().exclude().select_related() 一路链下来,SQL 是什么时候、由谁写出来的?这篇拆开 QuerySet.query,看它的内部结构,再让同一个 Query 在 SQLite 与 PostgreSQL 上各编译一次,并量三个阶段各花多少时间。',
    facts=[('Query 对象', 'QuerySet.query 是条件树 + 状态,不是 SQL 字符串;compiler 才生成 SQL'), ('后端方言', '同一个 Query:SQLite 用 LIKE,PostgreSQL 用 UPPER(…) LIKE UPPER(…)'), (f'{vals[0]:.0f} + {vals[1]:.0f} µs', '本例构建 QuerySet 与编译 SQL 的纯 Python 开销')],
    body=[
        sec('Query 对象', '', term('', blk('d40', 1)), '<p>每次链式调用(<code>filter</code>、<code>exclude</code> …)都是克隆一个 <code>QuerySet</code> 并修改它的 <code>Query</code>。<code>Query</code> 里 <code>where</code> 是一棵 <code>WhereNode</code> 树,各种 lookup 是树上的节点。</p>'),
        sec('编译', '', term('', blk('d40', 2)), '<p><code>SQLCompiler</code> 遍历这棵树,调用每个节点的 <code>as_sql</code>,把 <code>Col</code>、lookup、JOIN、ORDER BY 拼成 SQL,后端(<code>connection.ops</code>、<code>connection.features</code>)决定方言细节。所以同一份 ORM 代码换数据库时,SQL 会变、性能特征也会变。</p>'),
        sec('每个阶段的开销', '', term('', blk('d40', 3)), '<p>构建与编译是纯 Python,没有缓存,每次调用都做一遍。对绝大多数请求这些微秒级开销不是瓶颈;热点路径上可以用 <code>values_list</code> / 原生 SQL / 缓存结果绕开(本文没有测这些替代方案)。</p>'),
        sec('怎么看 SQL', '', term('', blk('d40', 4)), '<p>最可靠的是看真实执行的语句(<code>CaptureQueriesContext</code>);<code>str(qs.query)</code> 只适合阅读。</p>'),
        sec('分步演示:从 QuerySet 到 SQL', '', demo('ORM 生成 SQL', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite 与 PostgreSQL 16.15(本机临时实例,端口 9404);耗时为进程内 2000 次平均', '没有验证:多数据库路由(using=)下的编译差别、子查询与窗口函数的编译、query.explain 的输出、连接池对总耗时的影响'],
)
