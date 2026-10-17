from lib import *
R = J('d114')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("在 async 代码里直接写同步 ORM:Item.objects.count()、list(Item.objects.all())、Item.objects.create()、甚至 connection.cursor(),全都抛 SynchronousOnlyOperation: You cannot call this from an async context - use a thread or sync_to_async.。", t=tl(L('direct')), mark=[0, 1, 2, 3], kv=KV([['报错', 'SynchronousOnlyOperation'], ['触发条件', '当前线程里有运行中的事件循环']], ['报错'])),
    step("三种正确写法:await Item.objects.acount()(a 前缀的异步方法)、await sync_to_async(Item.objects.count)()、[i async for i in Item.objects.all()]。", t=tl(L('ok')), done=[0, 1, 2], kv=KV([['首选', 'a 前缀方法 / async for'], ['备选', 'sync_to_async 包起来']], ['首选'])),
    step("设环境变量 DJANGO_ALLOW_ASYNC_UNSAFE=true:同样的 count() 不再报错,返回 0。这只是关掉检查,查询仍然是同步的,会阻塞事件循环——不是修复。", t=tl(L('unsafe')), mark=[0], kv=KV([['DJANGO_ALLOW_ASYNC_UNSAFE', '只关检查,不解决阻塞']], ['DJANGO_ALLOW_ASYNC_UNSAFE'])),
    step("真实 uvicorn 服务里:async 视图里直接 count() → HTTP 500,页面标题 SynchronousOnlyOperation at /bad/;用 await Item.objects.acount() 的视图 → 200。检查由 django/utils/asyncio.py 里的 async_unsafe 装饰器做(读源码得知)。", t=tl([l for l in out('d114').split('== ')[4].splitlines()[1:] if l.strip()]), done=[1], mark=[0], kv=KV([['/bad/', '500'], ['/good/', '200']], ['/bad/'])),
]
A = dict(
    n=114, series='django', tags='Django,异步,SynchronousOnlyOperation,ORM,真实验证,动画演示',
    desc='在 async 上下文里直接调用同步 ORM(count、遍历、create、cursor)全部抛 SynchronousOnlyOperation;用 a 前缀方法、async for 或 sync_to_async 才可以;DJANGO_ALLOW_ASYNC_UNSAFE=true 只是关掉检查;真实 uvicorn 服务里表现为 500。',
    lead='第一次在 async 视图里写 ORM,大多会撞上 SynchronousOnlyOperation。这篇把它出现的条件、几种正确写法、以及那个「关掉检查」的环境变量分别跑出来。',
    facts=[('SynchronousOnlyOperation', '当前线程里有运行中的事件循环时调用同步 ORM 抛出'), ('a 前缀 / async for', '异步 ORM 的写法'), ('DJANGO_ALLOW_ASYNC_UNSAFE', '只关检查,查询仍会阻塞事件循环')],
    body=[
        sec('直接调用会怎样', '', term('', blk('d114', 1)), '<p>不是只有查询才会触发:<code>connection.cursor()</code> 也一样。它检查的是「当前线程里有没有正在运行的事件循环」,而不是「这个函数是不是 async def」。</p>'),
        sec('正确写法', '', term('', blk('d114', 2))),
        sec('DJANGO_ALLOW_ASYNC_UNSAFE', '', term('', blk('d114', 3)), '<p>官方留它是为了 Jupyter 这类环境。在服务里打开它,只会让你失去这个提醒,同步查询照样阻塞整个事件循环里的所有请求。</p>'),
        sec('在真实服务里', '', term('', blk('d114', 4))),
        sec('分步演示', '', demo('SynchronousOnlyOperation', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;asyncio.run 里的脚本 + 1 个 uvicorn 进程', '没有验证:「阻塞事件循环」的实际延迟影响(本文只演示报错与开关)、Jupyter 场景、其它会触发 async_unsafe 检查的操作清单'],
)
