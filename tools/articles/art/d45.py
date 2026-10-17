from lib import *
R = J('d45')
def L(k): return [l.strip() for l in R[k].splitlines() if l.strip()]
steps = [
    step("在 atomic 里注册 on_commit:写入 a、注册回调 A、内层 atomic 里写 b 并注册回调 B、内层退出——回调此时都没有执行。外层 atomic 提交时,回调 A、B 才依次执行;回调里用另一个数据库连接去查,此刻已经能看到 a 和 b(True)——回调是在提交之后运行的。", t=tl(L('basic'), cur=[0, 1, 2, 3], done=[4, 5, 6]), kv=KV([['on_commit', '外层事务提交后才执行'], ['此刻', '别的连接已经看得见数据']], ['on_commit'])),
    step("事务因异常回滚:回调 R 永远不会执行(注册了但被丢弃)。没有 atomic(autocommit)时注册:回调立刻执行,发生在「autocommit 下注册 N 之后」这一行之前。", t=tl(L('rollback'), mark=[0, 1], cur=[2]), kv=KV([['回滚', '回调被丢弃'], ['autocommit', '立即执行']], ['回滚'])),
    step("内层保存点回滚:内层注册的回调(将回滚)被丢弃,只有外层的两个回调执行。回调和「它注册时所在的保存点」绑定。", t=tl(L('savepoint'), cur=[1, 2], mark=[0]), kv=KV([['保存点回滚', '连同其中注册的回调一起丢弃']], ['保存点回滚'])),
    step("回调之间:一个回调抛异常时(默认 robust=False),它后面的回调不再执行(回调 3 没有执行),异常向外抛出;但事务已经提交,kept-1 仍在库里。robust=True 时,异常被记录(日志)并继续,回调 3 也会执行,不向外抛。", t=tl([l for l in L('exc') if '===' not in l]), kv=KV([['默认', '一个失败,后面的不执行'], ['robust=True', '全部执行,不向外抛']], ['robust=True'])),
    step("回调里再写数据库:此时事务已经提交,处于 autocommit 状态,每条语句自己提交(回调里的 INSERT 没有 BEGIN)。如果回调里的写入也需要原子性,要自己再包一层 atomic。", t=tl(L('write')), kv=KV([['回调里的写入', 'autocommit,不在原事务里']], ['回调里的写入'])),
]
A = dict(
    n=45, series='django', tags='Django,事务,on_commit,PostgreSQL,真实验证,动画演示',
    desc='实测 transaction.on_commit():外层事务提交后才执行(此时别的连接已能看见数据);回滚与保存点回滚都会丢弃回调;autocommit 下立即执行;一个回调抛异常会阻止后面的回调,robust=True 则继续;回调里的写入处于 autocommit。',
    lead='on_commit 是「事务提交之后再做」的标准写法(发通知、入队任务)。它到底什么时候执行?回滚了怎么办?多个回调互相影响吗?这篇用事件日志把每种情形排出来,并用另一个数据库连接验证「此刻数据是否已经可见」。',
    facts=[('提交之后', '回调在外层事务提交后执行,此时其它连接已能看到写入'), ('丢弃', '回滚(包括保存点回滚)会丢弃在其中注册的回调'), ('robust=True', '默认一个回调抛异常会阻止后面的回调;robust=True 则继续执行并记录异常')],
    body=[
        sec('什么时候执行', '', term('', blk('d45', 1)), '<p>回调是在 <code>COMMIT</code> 之后、<code>atomic</code> 块退出时执行的,所以可以放心地在里面通知别人「数据已经在了」(第 106、119、120 篇会用到)。</p>'),
        sec('回滚与 autocommit', '', term('', blk('d45', 2)), '<p>没有事务时没有「提交」这件事,回调立即执行。</p>'),
        sec('保存点', '', term('', blk('d45', 3)), '<p>回调按保存点记录,保存点回滚时一起丢弃。</p>'),
        sec('回调抛异常', '', term('', blk('d45', 4)), '<p>事务已经提交,异常不会让数据回滚。用 <code>robust=True</code> 让后面的回调不受影响(异常只记录日志)。</p>'),
        sec('回调里的写入', '', term('', blk('d45', 5)), '<p>回调里的数据库写入不在原事务里。</p>'),
        sec('分步演示:on_commit 的时机', '', demo('on_commit', [('t', 'term', '事件日志'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9421);「可见性」用另一个线程里的独立连接查询', '没有验证:测试框架里 on_commit 的行为(TestCase 默认不执行,需要 captureOnCommitCallbacks)、多数据库下的 on_commit(using=)、on_commit 与 ATOMIC_REQUESTS 的组合见第 48 篇'],
)
