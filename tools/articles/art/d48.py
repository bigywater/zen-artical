from lib import *
R = J('d48')['off']; ks = list(R)
def L(k): return [l for l in R[k].splitlines() if l.strip()]
off = L(ks[0]); on = L(ks[1])
steps = [
    step("默认(ATOMIC_REQUESTS=False):视图先写一行再抛异常 → 500,但 view-write 仍留在表里(每条语句自己提交);写完返回 500 响应、正常 200、@non_atomic_requests 也都留下 view-write。视图里 in_atomic_block = False。", t=tl(off[:5], mark=[0], cur=[4]), kv=KV([['不开', '没有事务,写了就留下']], ['不开'])),
    step("ATOMIC_REQUESTS=True:视图抛异常的那次,view-write 被回滚,表里只剩中间件写的两行;正常的 200 请求提交。视图里 in_atomic_block = True。", t=tl(on[:5], done=[0], cur=[4]), kv=KV([['开启', '视图整体一个事务,异常即回滚']], ['开启'])),
    step("注意边界:①视图返回 500 响应(而不是抛异常)时事务照样提交(view-write 留下);②中间件里的写入在事务之外,不受回滚影响(两行 middleware-* 一直都在);③@transaction.non_atomic_requests 装饰的视图不开事务,异常时写入仍然留下。", t=tl(on[1:4], mark=[0], cur=[1, 2]), kv=KV([['只有「异常」才回滚', '返回 500 响应不回滚'], ['中间件', '在事务外']], ['只有「异常」才回滚'])),
    step("on_commit 的时机:不开时,回调在注册时立即执行(日志里回调排在「视图即将返回响应」之前);开启后,回调等到视图返回、事务提交后才执行(排在它之后)。", t=tl(off[5:6] + on[5:6], cur=[0], done=[1]), kv=KV([['不开', '回调立即执行'], ['开启', '视图结束提交后执行']], ['开启'])),
    step("流式响应:视图函数返回了 StreamingHttpResponse 就算视图结束、事务已提交;之后遍历生成器时的写入(generator-write)在事务之外,即使生成器随后抛异常也不会回滚——开与不开都留下。", t=tl(off[6:] + on[6:], cur=[1, 3]), kv=KV([['流式响应', '生成器里的写入不在视图事务里']], ['流式响应'])),
]
A = dict(
    n=48, series='django', tags='Django,事务,ATOMIC_REQUESTS,真实验证,动画演示',
    desc='实测 ATOMIC_REQUESTS:视图抛异常时整个视图的写入回滚,但返回 500 响应(不是异常)时照样提交;中间件的写入在事务之外;@non_atomic_requests 例外;on_commit 的时机随之改变;流式响应的生成器写入在事务之外。',
    lead='ATOMIC_REQUESTS = True 就是「每个请求一个事务」。它的边界比想象中窄:什么会回滚、什么不会?这篇分别在关闭与开启下打同一组 URL,看表里留下什么。',
    facts=[('只有异常回滚', '视图返回 500 响应不算失败,事务照样提交;只有抛出异常才回滚'), ('中间件在外', '中间件里的写入不在视图事务里,回滚不影响它们'), ('流式响应', '生成器里的写入发生在事务结束之后')],
    body=[
        sec('两组结果', '', term('', blk('d48', 1)), term('', blk('d48', 2)), '<p>同一组视图:抛异常、返回 500、正常返回、被 <code>non_atomic_requests</code> 排除、on_commit、流式响应。</p>'),
        sec('怎么理解边界', '', '<ul><li>事务包住的是「调用视图函数」这一段,不含中间件。</li><li>回滚的触发条件是「视图抛出异常」,与响应状态码无关。</li><li>响应一旦交给服务器开始流式发送,事务已经结束。</li></ul>'),
        sec('分步演示:请求即事务', '', demo('ATOMIC_REQUESTS', [('t', 'term', '结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;用 django.test.Client(raise_request_exception=False)', '没有验证:PostgreSQL 上的相同行为、多数据库下 ATOMIC_REQUESTS 只对指定别名生效、异步视图(ATOMIC_REQUESTS 对 async 视图不支持——文档说法,本文没有验证)、视图里手动 atomic 与它的嵌套'],
)
