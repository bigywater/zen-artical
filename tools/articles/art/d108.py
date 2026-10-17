from lib import *
R = J('d108')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("自定义信号:order_paid = Signal();receiver 用 @receiver(order_paid) 声明,签名里可以直接写具体的关键字参数(order_id、amount),其余用 **kw 接住;发送 order_paid.send(sender='shop', order_id=7, amount=99)。", t=tl(L('define')[:1]), kv=KV([['定义', 'Signal()'], ['发送', 'send(sender=…, 关键字参数)']], ['定义'])),
    step("老教程里的 Signal(providing_args=[...]) 在 Django 6.1.1 里已经不可用:TypeError: Signal.__init__() got an unexpected keyword argument 'providing_args'。参数是什么,靠文档和 receiver 的签名约定。", t=tl(L('define')[1:]), mark=[0], kv=KV([['providing_args', '已移除,传就报 TypeError']], ['providing_args'])),
    step("sender 的匹配是「相等」:connect(sender=Shop) 只响应 send(sender=Shop)(类本身);connect(sender='shop') 只响应字符串 'shop';send(sender=Shop()) 用实例发送时,两个 receiver 都不响应。所以约定好 sender 传什么,发和收要一致。", t=tl(L('sender')), mark=[2], kv=KV([['Shop 类', '匹配 for Shop'], ['Shop() 实例', '什么都不匹配']], ['Shop() 实例'])),
    step("async receiver:send() 与 asend() 都能调用同步和异步的 receiver(各睡 0.2 秒的 sync 与 async 各一个),两种方式总耗时都是 0.41 s;返回列表里 slow_sync 排在前面,虽然 slow_async 是先 connect 的——返回的顺序不一定等于 connect 顺序。", t=tl(L('async')), mark=[0, 1], kv=KV([['send() / asend()', '都是 0.41 s'], ['返回顺序', 'sync 在 async 前(与 connect 顺序不同)']], ['返回顺序'])),
    step("send_robust:一个 receiver 抛 KeyError,另一个正常;返回里 ok → 'fine',bad → KeyError('missing')(异常对象本身),调用方自己决定记日志或忽略。", t=tl(L('robust')), done=[0], mark=[1], kv=KV([['send_robust', '异常放在返回值里']], ['send_robust'])),
]
A = dict(
    n=108, series='django', tags='Django,Signal,自定义信号,async,真实验证,动画演示',
    desc='自定义 Signal 的写法与边界(Django 6.1.1):providing_args 已移除;sender 按相等匹配,类、字符串、实例互不相通;send() 与 asend() 对同步/异步 receiver 的耗时;send_robust 把异常放进返回值。',
    lead='除了 post_save 这些内置信号,你也可以定义自己的信号,让一个模块「宣布」某件事发生了,而不必知道谁在监听。这篇把自定义信号的定义、发送、sender 匹配、异步 receiver 与容错发送逐项跑一遍。',
    facts=[('providing_args', '在 Django 6.1.1 里传入会 TypeError,已被移除'), ('sender 相等匹配', '类、字符串、实例互不匹配'), ('0.41 s', 'send() 与 asend() 各调用一个 0.2 s 的 sync 与 async receiver 的总耗时')],
    body=[
        sec('定义与发送', '', term('', blk('d108', 1))),
        sec('sender 怎么匹配', '', term('', blk('d108', 2)), '<p>发送时 <code>sender</code> 传什么,connect 时 <code>sender=</code> 就要传同样的东西。</p>'),
        sec('异步 receiver', '', term('', blk('d108', 3)), '<p>我原本以为 <code>asend()</code> 会明显更快,实测两者都是 0.41 s(总和约等于两个 receiver 各自的 0.2 s 相加)——所以本文<b>不能</b>说 asend 让 receiver 并行。同步 receiver 在 asend 里怎么被调度也没有进一步查证。</p>'),
        sec('send_robust', '', term('', blk('d108', 4))),
        sec('分步演示', '', demo('自定义信号', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自建 Signal,不涉及数据库;asend / async receiver 在 Django 5.0 起提供,本文只在 6.1.1 上测', '没有验证:在真实视图里发送并结合 on_commit(第 106 篇)、asend 中 sync receiver 的线程调度细节、多线程下的发送、signal 的文档约定(如把 Signal 放在哪个模块)'],
)
