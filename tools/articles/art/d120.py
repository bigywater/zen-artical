from lib import *
R = J('d120')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("on_commit 回调按注册顺序、在事务提交之后执行:atomic 里注册 A、B,最后的顺序是 ['块内最后一行', 'A', 'B']。没有 atomic(autocommit)时注册 C,会立刻执行:['C', '注册之后的下一行']。", t=tl(L('order')), kv=KV([['有事务', '提交后按顺序执行'], ['无事务', '立刻执行']], ['有事务'])),
    step("回调抛异常(默认):atomic 退出时把异常抛出来,后面的回调没有执行(只有 first),但订单已经提交了(True)。这说明:提交成功之后回调才失败,数据不会回滚——回调里做的事失败了要自己处理。", t=tl(L('robust')[:2]), mark=[0], kv=KV([['回调抛异常', '数据已提交,后续回调不执行']], ['回调抛异常'])),
    step("robust=True(on_commit(bad, robust=True)):异常被记录成错误日志「Error calling bad in on_commit() during transaction (通知服务挂了).」,atomic 正常退出,first 和 third 都执行了。", t=tl(L('robust')[2:]), done=[0], kv=KV([['robust=True', '记录日志,其余回调照常执行']], ['robust=True'])),
    step("savepoint(嵌套 atomic)回滚:里面注册的回调被丢弃;外层提交时只执行 outer 与成功的 inner2。整个外层回滚时一个回调都不执行。", t=tl(L('savepoint')), mark=[0], done=[1], kv=KV([['savepoint 回滚', '回调丢弃'], ['整体回滚', '回调都不执行']], ['savepoint 回滚'])),
    step("测试里:普通 TestCase 把每个测试包在事务里,永远不提交,回调不会执行(ran = []);captureOnCommitCallbacks(execute=True) 捕获到 1 个回调并执行;TransactionTestCase 真的提交,回调执行。", t=tl(L('tests')), mark=[0], done=[1, 2], kv=KV([['TestCase', '回调不会执行'], ['解法', 'captureOnCommitCallbacks(execute=True)']], ['解法'])),
]
A = dict(
    n=120, series='django', tags='Django,事务,on_commit,异步任务,测试,真实验证,动画演示',
    desc='transaction.on_commit 的规则:提交后按注册顺序执行,autocommit 时立即执行;回调抛异常时默认中断后续回调(数据已提交),robust=True 记录日志并继续;savepoint 回滚会丢弃回调;TestCase 里回调不执行,要用 captureOnCommitCallbacks。',
    lead='把任务放进 transaction.on_commit 是「事务提交之后才触发」的标准做法。这篇把它的执行顺序、失败行为、savepoint 语义以及在测试里的坑逐条验证。',
    facts=[('提交后按顺序', 'on_commit 回调在事务提交之后、按注册顺序执行'), ('robust=True', '回调失败只记日志,其余回调继续'), ('TestCase 里不执行', '要用 captureOnCommitCallbacks(execute=True)')],
    body=[
        sec('顺序与时机', '', term('', blk('d120', 1))),
        sec('回调失败', '', term('', blk('d120', 2)), '<p>回调在提交之后执行,所以它的失败不会让数据回滚。如果任务发不出去就必须保证可靠(不能丢),就需要额外的机制(比如把任务先写进数据库表,再由后台可靠地投递——这是设计上的建议,本文没有实验)。<code>on_commit</code> 本身是「至多一次」:提交成功后、回调执行前进程崩溃,回调就丢了(本文没有模拟崩溃)。</p>'),
        sec('嵌套事务', '', term('', blk('d120', 3))),
        sec('在测试里', '', term('', blk('d120', 4)), '<p>用 <code>manage.py test</code> 真实跑出的结果。测试 on_commit 的逻辑用 <code>captureOnCommitCallbacks</code>,或者 <code>TransactionTestCase</code>(更慢)。</p>'),
        sec('分步演示', '', demo('on_commit 的规则', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;测试用 manage.py test lab -v 0', '没有验证:多数据库(using=)、on_commit 与 Celery 的组合、进程在回调之前崩溃时的丢失、on_commit 里再注册 on_commit 的嵌套行为(仅测了 autocommit 下立即执行)'],
)
