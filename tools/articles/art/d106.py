from lib import *
R = J('d106')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("atomic() 里保存对象,post_save 里用另一个数据库连接(另开线程)去查这一行:此时看不到(False)——事务还没提交。在 post_save 里注册的 transaction.on_commit 回调,在事务提交后触发,此时另一个连接能看到(True)。", t=tl(L('visible')), mark=[0], done=[2], kv=KV([['post_save 时', '别的连接看不到这行'], ['on_commit 时', '看得到']], ['on_commit 时'])),
    step("post_save 里直接做「不可撤销的事」(比如通知外部系统):事务随后回滚,库里没有这个订单(False),但外部通知已经发出去了(列表里有「订单 2 创建」)。on_commit 版本的回调没有执行。", t=tl(L('rollback')), mark=[0], kv=KV([['回滚后', '库里没有,通知却已发出']], ['回滚后'])),
    step("把通知放进 on_commit:回滚时通知列表是空的;提交后才出现「订单 4」的通知。这是把副作用绑定到「事务真正成功」的办法。", t=tl(L('oncommit')), done=[0, 1], kv=KV([['回滚', '不通知'], ['提交', '才通知']], ['提交'])),
    step("没有 atomic()(autocommit)时,每条语句自己提交:post_save 触发时另一个连接就能看到这一行(True),on_commit 回调会立刻执行(也是 True)。所以同一段 receiver 代码,在有没有外层事务时行为不一样。", t=tl(L('auto')), mark=[0], kv=KV([['autocommit', 'post_save 时数据已可见']], ['autocommit'])),
]
A = dict(
    n=106, series='django', tags='Django,Signal,事务,on_commit,PostgreSQL,真实验证,动画演示',
    desc='在自己起的 PostgreSQL 上验证:atomic 里 post_save 触发时另一个连接看不到数据,on_commit 时看得到;回滚后 post_save 里的副作用已经发生,on_commit 回调不执行;autocommit 时 post_save 已可见。',
    lead='post_save 里发通知、发消息、触发异步任务,是最常见的用法,也是最容易出事故的地方:信号是在事务提交之前触发的。这篇在真实的 PostgreSQL 上用第二个连接去「偷看」,把这件事量出来。',
    facts=[('False → True', 'atomic 里另一个连接对新数据的可见性:post_save 时 → on_commit 时'), ('回滚', 'post_save 里已发出的通知收不回来,on_commit 回调则不会执行'), ('autocommit', '没有外层事务时 post_save 触发时数据已提交')],
    body=[
        sec('提交之前 vs 提交之后', '', term('', blk('d106', 1)), '<p>可见性用「另开一个线程、用它自己的数据库连接去查」来测,这是同一个数据库上的第二个会话。异步任务(比如 Celery worker)就是这样的第二个会话:如果在 post_save 里就把任务发出去,worker 可能在事务提交前就来查这行数据,结果查不到。</p>'),
        sec('回滚之后', '', term('', blk('d106', 2)), '<p>post_save 里做的外部调用不会因回滚而撤销。</p>'),
        sec('改用 on_commit', '', term('', blk('d106', 3)), '<p><code>transaction.on_commit(func)</code> 把回调挂到当前事务上:提交后执行,回滚则丢弃。</p>'),
        sec('没有外层事务时', '', term('', blk('d106', 4)), '<p>autocommit 模式下 <code>on_commit</code> 的回调会立即执行,所以写 receiver 时不必区分有没有外层事务,统一用 on_commit 即可。</p>'),
        sec('分步演示', '', demo('信号与事务提交', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自己起的临时 PostgreSQL 16;第二个连接由另一个线程里的 Django ORM 查询提供', '没有验证:嵌套 atomic / savepoint 里 on_commit 的行为、on_commit 回调自己抛异常时的后果、测试用例里(TestCase 包在事务里)on_commit 不执行的问题、MySQL 上的行为'],
)
