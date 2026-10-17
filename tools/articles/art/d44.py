from lib import *
R = J('d44')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("嵌套 atomic 的 SQL:外层是 BEGIN … COMMIT;内层是 SAVEPOINT … RELEASE SAVEPOINT。三次 INSERT 都在同一个事务里。", t=tl(L('nested'), cur=[0, 2, 4, 6], mark=[3, 5]), kv=KV([['外层', 'BEGIN / COMMIT'], ['内层', 'SAVEPOINT / RELEASE']], ['内层'])),
    step("内层抛异常、被外层 try/except 捕获:SQL 里是 ROLLBACK TO SAVEPOINT + RELEASE SAVEPOINT,只回滚内层的 INSERT b;外层继续插入 c 并 COMMIT。最终表里是 a 和 c。", t=tl(L('inner_fail')[:-1], cur=[2, 3], mark=[4], done=[5, 6, 7]), kv=KV([['结果', 'a 和 c;b 被回滚']], ['结果'])),
    step("常见错误:在 atomic 里捕获 IntegrityError 却没有内层 atomic:事务已经处于「失败」状态,之后的任何查询都报 TransactionManagementError: An error occurred in the current transaction. You can't execute queries until the end of the 'atomic' block。给可能失败的语句包一层内层 atomic(即保存点),外层就能继续,最终留下 after 和 dup。", t=tl(L('integrity')), n=fl([['不包内层 atomic 捕获 IntegrityError', 'TransactionManagementError'], ['内层再包一层 atomic', '外层继续,结果 after + dup']], mark=[0], done=[1]), kv=KV([['捕获数据库错误', '要包在自己的 atomic(保存点)里']], ['捕获数据库错误'])),
    step("其它:durable=True 的 atomic 不能嵌套在另一个 atomic 里(RuntimeError: A durable atomic block cannot be nested within another atomic block.);savepoint=False 的内层不建保存点,内层失败后外层被标记为需要回滚,继续用外层会报同样的 TransactionManagementError,提交时整体 ROLLBACK,表里为空;没有 atomic 的单条 create 是 autocommit,一条 INSERT 自己提交。", t=tl(L('misc'), mark=[0, 8, 9]), kv=KV([['savepoint=False', '内层失败 = 外层作废'], ['durable=True', '必须是最外层']], ['savepoint=False'])),
]
A = dict(
    n=44, series='django', tags='Django,事务,atomic,保存点,PostgreSQL,真实验证,动画演示',
    desc='在 PostgreSQL 上记录 transaction.atomic() 的实际 SQL:外层 BEGIN/COMMIT、内层 SAVEPOINT/RELEASE;内层异常只回滚到保存点;atomic 里吞掉 IntegrityError 而不包内层 atomic 会导致后续查询全部 TransactionManagementError;durable 与 savepoint=False 的行为。',
    lead='atomic 嵌套起来是怎么回事?在里面捕获数据库异常为什么会让后面的查询全部失败?这篇直接看 Django 发给 PostgreSQL 的每一条 SQL。',
    facts=[('SAVEPOINT', '内层 atomic 用保存点实现:异常时 ROLLBACK TO SAVEPOINT,外层不受影响'), ('TransactionManagementError', 'atomic 里捕获了 IntegrityError 却没有内层 atomic,之后的查询全部失败'), ('savepoint=False', '内层失败会让整个外层事务作废')],
    body=[
        sec('嵌套 atomic 的 SQL', '', term('', blk('d44', 1)), '<p>只有最外层才会 <code>BEGIN</code> / <code>COMMIT</code>;里面的每一层只是保存点。</p>'),
        sec('内层失败', '', term('', blk('d44', 2)), '<p>捕获异常的位置很重要:让异常在 <code>with atomic()</code> 的内层「穿过」出口,Django 才会执行 <code>ROLLBACK TO SAVEPOINT</code>。</p>'),
        sec('最常见的坑', '', term('', blk('d44', 3)), '<p>PostgreSQL 里一条语句出错,整个事务进入「已中止」状态,直到回滚。所以要「尝试插入、失败就换个办法」,必须把尝试包在内层 <code>atomic</code>(保存点)里。<code>get_or_create</code> 内部就是这么做的(第 35 篇)。</p>'),
        sec('durable、savepoint=False、autocommit', '', term('', blk('d44', 4)), '<p><code>durable=True</code> 用来断言「这里必须是最外层事务」(比如需要在其后可靠执行 <code>on_commit</code>);<code>savepoint=False</code> 省一次保存点,代价是失败时不能局部恢复。</p>'),
        sec('分步演示:事务与保存点', '', demo('atomic 与保存点', [('t', 'term', 'SQL'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9420);SQL 用 CaptureQueriesContext 记录', '没有验证:SQLite / MySQL 上保存点的行为差异、autocommit=False 的用法、数据库事务超时、异步代码里的 atomic(第 119 篇)'],
)
