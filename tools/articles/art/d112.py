from lib import *
R = J('d112'); rows = R['rows']; th = R['threads']
def L(k): return [l for l in out('d112').split('== ')[k + 1].splitlines()[1:] if l.strip()]
L1, L2 = L(0), L(1)
steps = [
    step("在视图里查两件事:当前线程的名字、当前线程里有没有正在运行的事件循环(asyncio.get_running_loop() 是否成功)。分别在 ASGI(uvicorn)和 WSGI(gunicorn 同步 worker)下、async def 与普通 def 视图各请求两次。", n=fl([['视图', 'threading.current_thread()'], ['视图', 'asyncio.get_running_loop()']], cur=[0, 1]), kv=KV([['服务器', 'uvicorn / gunicorn'], ['视图', 'async def / def']], ['服务器'])),
    step("ASGI + async def:跑在 MainThread,该线程里有运行中的事件循环——视图直接在服务器的事件循环上执行(所以视图里不能阻塞)。", t=tl(L1[0:1]), done=[0], kv=KV([['ASGI + async def', 'MainThread,有事件循环']], ['ASGI + async def'])),
    step("ASGI + 普通 def:跑在 ThreadPoolExecutor-N_0 这样的工作线程里,该线程里没有事件循环——Django 用线程把 sync 视图与事件循环隔开(阻塞它不会卡住循环)。", t=tl(L1[1:2]), done=[1], kv=KV([['ASGI + def', '工作线程,无事件循环']], ['ASGI + def'])),
    step("WSGI + 普通 def:MainThread(gunicorn 同步 worker 的主线程),无事件循环。WSGI + async def:在 ThreadPoolExecutor 线程里,并且这个线程有运行中的事件循环——Django 为这一个请求临时开一个事件循环来跑协程(async_to_sync),跑完就结束,不会带来并发。", t=tl(L1[2:]), done=[2, 3], kv=KV([['WSGI + async def', '临时事件循环,一个请求一个'], ['WSGI + def', '普通同步执行']], ['WSGI + async def'])),
    step("ASGI 下连续 6 次请求 sync 视图,线程名依次是 " + '、'.join(th) + "——每个请求各自一个新线程(6 个不同线程)。这就是上一篇里 sync 视图在 ASGI 下不排队的原因。", t=tl(L2), mark=[0], kv=KV([['6 个请求', '6 个不同线程']], ['6 个请求'])),
]
A = dict(
    n=112, series='django', tags='Django,ASGI,WSGI,事件循环,线程,真实验证,动画演示',
    desc='用线程名和 get_running_loop() 看视图代码到底跑在哪:ASGI 下 async 视图在主线程的事件循环里,sync 视图在每个请求独立的工作线程里;WSGI 下 sync 视图在 worker 主线程,async 视图在一个临时事件循环里。',
    lead='ASGI 和 WSGI 下的同步、异步代码,分别在哪里执行?这篇在视图里直接打印线程名和事件循环状态,请求真实的 uvicorn / gunicorn 进程,把四种组合的执行位置量出来。',
    facts=[('MainThread + 事件循环', 'ASGI 下 async 视图的执行位置'), ('每请求一个线程', 'ASGI 下 sync 视图:6 次请求 6 个不同线程'), ('临时事件循环', 'WSGI 下 async 视图:每个请求在一个线程里临时起一个循环')],
    body=[
        sec('四种组合', '', term('', blk('d112', 1)), '<p>结论只对「执行位置」:ASGI 下 async 视图直接在服务器的事件循环上跑;sync 视图被放到线程里。WSGI 下 sync 视图就是普通的同步调用;async 视图被包了一层,在临时的事件循环里跑完这一个请求(async_to_sync)。</p>'),
        sec('sync 视图每次用的线程', '', term('', blk('d112', 2)), '<p>线程名里的数字每次都不同,说明每个请求用的是新的线程(而不是共享的一个)。这与下一篇里 sync_to_async 的 thread_sensitive 行为是同一个机制。</p>'),
        sec('分步演示', '', demo('视图跑在哪', [('n', 'flow', '检查项'), ('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。uvicorn / gunicorn 各 1 个进程;视图返回线程名与事件循环状态的 JSON', '没有验证:线程与请求的对应关系背后的 asgiref 实现细节(本文只观察了现象)、gunicorn gthread / uvicorn 多 worker、中间件里的执行位置(第 116 篇)'],
)
