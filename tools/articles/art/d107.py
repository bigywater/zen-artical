from lib import *
R = J('d107')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("调用处只有一行 Order.objects.create(name='x')。没有 receiver 时这行发 1 次查询;挂上三个 post_save receiver(写日志、扣库存、写审计)后,同一行发 7 次查询——调用处的代码一个字没变,读代码的人看不出来。", t=tl(L('hidden')), mark=[1], kv=KV([['1 → 7', '同一行 create() 的查询数'], ['可见性', '调用处看不出']], ['1 → 7'])),
    step("receiver 抛异常(比如库存服务不可用):create() 把这个异常抛给调用方。没有 atomic 时订单已经写进库里了(True),只是半截业务;外面包了 atomic 时订单被回滚(False)。", t=tl(L('fail')), mark=[1], done=[2], kv=KV([['无 atomic', '订单已写入,业务只做了一半'], ['有 atomic', '整体回滚']], ['无 atomic'])),
    step("receiver 里再 save() 同一个对象:每次 save 又触发 post_save,直到 RecursionError(递归上限 1000)。改成 queryset.update()(不发信号)就没问题:库里 status = paid。", t=tl(L('loop')), mark=[0], done=[1], kv=KV([['信号里 save() 自己', '无限递归'], ['queryset.update()', '不发信号']], ['信号里 save() 自己'])),
    step("多个 receiver 的执行顺序 = connect 的顺序:先 connect a 再 b 就是 a、b;反过来就是 b、a。如果业务上 b 依赖 a 的结果,顺序就成了隐藏的耦合(本文没有验证 connect 顺序在真实项目里由什么决定)。", t=tl(L('order')), kv=KV([['执行顺序', '就是 connect 的顺序']], ['执行顺序'])),
    step("同样的业务写成一个显式的 place_order() 服务函数:一次调用 6 次查询、全部写在一个函数里,调用处可见、测试时可以直接调,也能显式放进一个 atomic。", t=tl(L('service')), done=[0], kv=KV([['显式函数', '流程一眼可见,不依赖 connect 顺序']], ['显式函数'])),
]
A = dict(
    n=107, series='django', tags='Django,Signal,业务逻辑,真实验证,动画演示',
    desc='把业务逻辑放进 post_save:一行 create() 悄悄变成 7 次查询;receiver 抛异常会让 create() 抛出、无事务时订单已写入;在信号里 save() 自己会 RecursionError;执行顺序就是 connect 顺序;改成显式服务函数则一目了然。',
    lead='信号能解耦,也能把业务流程藏起来。这篇不下定论,而是把「复杂业务放进信号」会遇到的几种情形一一跑出来:隐藏的查询、失败的传播、递归、顺序,最后对比同样逻辑写成显式函数的样子。',
    facts=[('1 → 7', '挂上 3 个 receiver 后,同一行 create() 的查询数'), ('RecursionError', 'receiver 里 save() 同一对象 → 无限递归'), ('connect 顺序', 'receiver 的执行顺序,业务依赖它就是隐性耦合')],
    body=[
        sec('调用处看不到的事', '', term('', blk('d107', 1))),
        sec('失败怎么传播', '', term('', blk('d107', 2)), '<p>post_save 用的是 <code>send()</code>,receiver 的异常会直接抛给 <code>save()</code> 的调用方。有没有外层 <code>atomic()</code> 决定了是「半截业务」还是「整体回滚」。</p>'),
        sec('在信号里保存自己', '', term('', blk('d107', 3)), '<p>要在保存后改自己的字段,用 <code>queryset.update()</code>(不发信号),或者用标志位跳过。</p>'),
        sec('执行顺序', '', term('', blk('d107', 4))),
        sec('显式的服务函数', '', term('', blk('d107', 5)), '<p>信号更适合「发布事件、别的模块可以订阅」这类松耦合的场景(比如缓存失效、日志、索引更新),而不是有先后依赖、必须全部成功的核心业务。这是设计判断,不是本文实验的结论;实验只说明了它的代价:隐藏的查询、失败传播、递归风险和顺序耦合。</p>'),
        sec('分步演示', '', demo('复杂业务放进信号', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;业务是虚构的订单 / 库存 / 日志三张表', '没有验证:真实项目里 receiver 的 connect 顺序由什么决定、信号在 Celery 任务里的表现、on_commit 版本(第 106 篇)的失败传播、性能上的差别'],
)
