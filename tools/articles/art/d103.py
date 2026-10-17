from lib import *
R = J('d103')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("Signal 是「发布-订阅」:sig.connect(r1)、sig.connect(r2),sig.send(sender='S', x=42) 会按连接顺序依次调用(r1 → r2),并把每个 receiver 的返回值收集成 [(receiver, response), …] 返回。关键字参数原样传给 receiver。", t=tl(L('basic')[:2]), kv=KV([['调用顺序', '连接顺序'], ['send() 返回', '[(receiver, 返回值)]']], ['调用顺序'])),
    step("receiver 必须接受 **kwargs:connect 一个签名里没有 **kwargs 的函数,直接 ValueError: Signal receivers must accept keyword arguments (**kwargs).——这样以后信号加新参数不会打断老 receiver。", t=tl(L('basic')[2:]), mark=[0], kv=KV([['无 **kwargs', 'connect 时报错']], ['无 **kwargs'])),
    step("sender 过滤:connect(only_a, sender=A) 只响应 A 发出的信号;没指定 sender 的 receiver 对所有发送者都响应。sender=A 时两个都被调用,sender=B 时只有不限 sender 的那个。", t=tl(L('sender')), kv=KV([['sender=A', 'only_a + any'], ['sender=B', 'any']], ['sender=A'])),
    step("receiver 抛异常:send() 直接把异常抛出来,后面的 receiver 不再执行(已执行 ok1、boom,ok2 没跑);send_robust() 捕获异常并把它作为返回值,三个 receiver 都执行了,返回里 boom 对应 ValueError('receiver failed')。", t=tl(L('errors')), mark=[0], done=[1, 2], kv=KV([['send()', '异常向外抛,后续 receiver 不执行'], ['send_robust()', '异常放进返回值,全部执行']], ['send_robust()'])),
    step("同一个函数 connect 两次只算一个;用 dispatch_uid 时按 uid 去重(x、x、y 只调用 2 次);disconnect(dispatch_uid='x') 返回 True,之后只剩 1 个;@receiver(sig) 装饰器等价于 connect。", t=tl(L('uid')), kv=KV([['去重依据', '函数身份或 dispatch_uid']], ['去重依据'])),
    step("开销(10 万次 send 取平均,Python 3.14):0 个 receiver 0.12 µs;1 个 0.78 µs;5 个 1.87 µs;20 个 5.61 µs。信号本身很轻,代价主要在 receiver 里做的事。", t=tl(L('cost')), b=bars([['0 个', 0.12, '0.12 µs'], ['1 个', 0.78, '0.78 µs'], ['5 个', 1.87, '1.87 µs'], ['20 个', 5.61, '5.61 µs']], 6, done=[0, 1, 2, 3]), kv=KV([['send 自身开销', '微秒级']], ['send 自身开销'])),
]
A = dict(
    n=103, series='django', tags='Django,Signal,信号,真实验证,动画演示',
    desc='Signal 的基本行为:按连接顺序调用并返回 [(receiver, 返回值)];receiver 必须有 **kwargs;sender 过滤;send() 遇异常直接抛出、send_robust() 捕获并继续;dispatch_uid 去重;一次 send 的开销 0.12–5.61 µs。',
    lead='Signal 是 Django 内置的观察者模式。这篇不涉及模型,只用一个自建的 Signal 把它的规则逐条跑一遍:调用顺序、返回值、sender 过滤、异常、去重与开销。',
    facts=[('连接顺序', 'receiver 按 connect 的先后依次被调用'), ('send / send_robust', 'send 遇异常抛出并中断,send_robust 捕获并继续'), ('**kwargs', 'receiver 签名必须带,否则 connect 时报错')],
    body=[
        sec('发送与接收', '', term('', blk('d103', 1)), '<p><code>send()</code> 是同步的:在调用方的线程里一个个执行 receiver,全部执行完才返回。</p>'),
        sec('sender 过滤', '', term('', blk('d103', 2))),
        sec('receiver 出错时', '', term('', blk('d103', 3)), '<p>Django 自带的模型信号(<code>post_save</code> 等)用的是 <code>send()</code>,所以某个 receiver 抛异常会打断后面的 receiver,并让调用方(比如 <code>save()</code>)也失败。自己发的信号如果不希望被 receiver 拖垮,用 <code>send_robust()</code>,但要自己检查返回值里有没有异常。</p>'),
        sec('去重与断开', '', term('', blk('d103', 4))),
        sec('开销', '', term('', blk('d103', 5)), '<p>信号机制本身是微秒级的,不需要为它「省」;要注意的是 receiver 里执行的代码。</p>'),
        sec('分步演示', '', demo('Signal 的规则', [('t', 'term', '输出'), ('b', 'bars', '开销'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。使用自建的 django.dispatch.Signal,不涉及数据库', '没有验证:多线程同时 send、receiver 用 weak 引用时被回收(第 109 篇)、async receiver(Django 5.0 起 send 可以调用 async receiver,本文没有测)、use_caching 参数的效果'],
)
