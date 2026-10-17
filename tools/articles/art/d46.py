from lib import *
R = J('d46')
def L(k): return [l.strip() for l in R[k].splitlines() if l.strip()]
steps = [
    step("select_for_update() 生成 SELECT … FOR UPDATE;不在 atomic 里使用直接抛 TransactionManagementError: select_for_update cannot be used outside of a transaction.(在 autocommit 下锁会立刻释放,毫无意义)。", t=tl(L('sql')), kv=KV([['前提', '必须在事务里']], ['前提'])),
    step("另一个事务持锁 1 秒期间:普通 select_for_update() 被阻塞,等到对方释放才返回(约 1.06 s);nowait=True 立即失败,OperationalError: could not obtain lock on row;skip_locked=True 立即返回,但结果里没有这一行(0 行)。", t=tl(L('contend')[1:]), b=bars([['普通(等待,s)', 1.06, '1.06'], ['nowait(立即失败,s)', 0.0, '≈0'], ['skip_locked(立即返回,s)', 0.0, '≈0']], 1.2, mark=[0], done=[1, 2]), kv=KV([['默认', '排队等锁'], ['nowait', '立即报错'], ['skip_locked', '跳过被锁的行']], ['skip_locked'])),
    step("skip_locked 做任务队列:30 个任务、3 个工作线程,每个线程循环「锁一个未处理的任务、处理、标记」——各处理 10 个,合计 30,每个任务恰好被处理一次,没有重复也没有遗漏,也没有互相等待。", t=tl(L('queue')), kv=KV([['skip_locked', '并发消费队列,互不阻塞']], ['skip_locked'])),
    step("有 JOIN 时可以用 of=('self',) 只锁主表:SQL 尾部是 FOR UPDATE OF \"lab_task\"(否则会锁住 JOIN 到的所有表的行)。", t=tl(L('of')), kv=KV([['of', '限定要锁的表']], ['of'])),
]
A = dict(
    n=46, series='django', tags='Django,ORM,select_for_update,行锁,PostgreSQL,真实验证,动画演示',
    desc='在 PostgreSQL 上做行锁实验:select_for_update 必须在 atomic 里;持锁期间普通调用阻塞约 1 秒、nowait=True 立即 OperationalError、skip_locked=True 返回 0 行;skip_locked 让 3 个线程并发消费 30 个任务恰好各一次;of 限定锁的表。',
    lead='select_for_update 能保证什么?抢不到锁时是等、报错还是跳过?怎么用它做一个简单的任务队列?这篇让两个事务真的去抢同一行,计时并记录结果。',
    facts=[('必须在事务里', 'select_for_update 在 autocommit 下直接抛 TransactionManagementError'), ('1.06 s / 立即 / 立即', '持锁 1 秒期间:普通调用等待、nowait 立即报错、skip_locked 立即返回空'), ('30 / 30', 'skip_locked 队列:3 个线程消费 30 个任务,恰好各一次')],
    body=[
        sec('SQL 与前提', '', term('', blk('d46', 1)), '<p>行锁的生命周期就是事务的生命周期:事务提交或回滚时释放。</p>'),
        sec('抢同一行', '', term('', blk('d46', 2)), '<p>三种策略:等(默认)、失败(<code>nowait</code>)、跳过(<code>skip_locked</code>)。<code>skip_locked</code> 意味着你看到的是「当前没被别人锁住的那部分」,不是完整的集合——适合队列,不适合需要完整视图的场景。</p>'),
        sec('任务队列', '', term('', blk('d46', 3)), '<p>典型写法:<code>with atomic(): t = qs.select_for_update(skip_locked=True).first(); 处理; 标记完成</code>。本实验里每个任务处理了 10 ms;处理时间更长、失败时事务回滚会让任务重新变为可领取。</p>'),
        sec('of', '', term('', blk('d46', 4)), '<p>有 <code>select_related</code> / JOIN 时,用 <code>of=(\'self\',)</code> 避免锁住不该锁的行。</p>'),
        sec('分步演示:抢锁', '', demo('select_for_update', [('t', 'term', '实测输出'), ('b', 'bars', '等待时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9422),READ COMMITTED;每个线程独立连接;「等待 1.06 s」是实测的一次数字', '没有验证:MySQL / SQLite 对 select_for_update 的支持(SQLite 忽略、MySQL 8 支持 skip_locked)、死锁场景、no_key 选项、on_commit 与锁释放的关系'],
)
