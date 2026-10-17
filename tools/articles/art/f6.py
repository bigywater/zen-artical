from lib import *
S = SS('f6')
R = J('f6'); gu = R['gunicorn']
steps = [
    step("ContextVar 与线程:主线程里 cv.set('主线程设的值') 之后,新开的线程里 cv.get() 返回的是默认值,不是主线程设的;把 contextvars.copy_context() 交给线程并用 ctx.run(cv.get) 调用,才读到「主线程设的值」。这个 Python 3.14.7 里 sys.flags.thread_inherit_context 是 0(新线程默认不继承上下文)。", t=tl(S(1)), done=lidx(S(1), '新线程里 cv.get()'), mark=lidx(S(1), 'thread_inherit_context'), kv=KV([['新线程里读到', '默认值'], ['copy_context().run', '主线程设的值'], ['thread_inherit_context', '0']], ['新线程里读到'])),
    step("ContextVar 与 asyncio:gather 并发三个任务 A、B、C,各自 cv.set 自己的值并睡不同时间;每个任务睡醒后读到的都是自己设的值,gather 结束后 main 里仍然是「main 设的值」。每个 Task 创建时复制一份上下文,任务里的修改不会漏到别处。", t=tl(S(2)), done=lidx(S(2), '任务A', '任务B', '任务C'), mark=lidx(S(2), 'gather 结束后'), kv=KV([['3 个任务', '各读到自己设的值'], ['gather 之后的 main', '值没变']], ['3 个任务'])),
    step("threading.local 在 asyncio 里会串:三个协程跑在同一个线程里,各自写 tl_.v 然后睡眠,醒来时读到的都是最后写入的 Z(['X 睡醒后读到 Z', 'Y 睡醒后读到 Z', 'Z 睡醒后读到 Z']);同样的流程换成 ContextVar,读到的是各自的 X、Y、Z。", t=tl(S(3)), mark=lidx(S(3), 'threading.local'), done=lidx(S(3), 'ContextVar'), kv=KV([['threading.local', '三个协程都读到 Z'], ['ContextVar', '各读到自己的']], ['threading.local'])),
    step("werkzeug.local.Local 的接口像 threading.local:3 个线程各自读到线程0/1/2,3 个协程各自读到任务0/1/2,主线程读到「主线程」;它内部存储的类型是 ContextVar。release_local(L) 之后再读 L.name 抛 AttributeError: name。", t=tl(S(4)), done=lidx(S(4), '3 个线程各自读到', 'Local 的内部存储'), mark=lidx(S(4), 'release_local'), kv=KV([['线程 / 协程', '都隔离'], ['内部存储', 'ContextVar'], ['release_local 之后', 'AttributeError: name']], ['内部存储'])),
    step(f"真实的 gunicorn(1 个 worker、8 个线程):16 个并发请求各自把参数 n 存进 g.me,随机睡 50~250 ms,再读回来;全部 {len(R['gunicorn'][2]) and 16} 个请求都读回自己的值,不一致的有 {gu[1]} 个(示例 0|0|thread-ok、1|1|thread-ok、2|2|thread-ok),总耗时 {gu[0]} ms(并发,不是 16 次串行相加)。", t=tl(S(5)), done=lidx(S(5), '16 个并发请求'), kv=KV([['并发请求', '16 个'], ['g 值错乱', f'{gu[1]} 个'], ['总耗时', f'{gu[0]} ms']], ['g 值错乱'])),
    step("线程池里没有请求上下文:在视图里直接 ex.submit(plain) 抛 RuntimeError;用 copy_current_request_context 包装后线程池里读到 request.path = /;用 ctx = contextvars.copy_context() 再 ex.submit(ctx.run, safe) 同样读到 /。", t=tl(S(6)), mark=lidx(S(6), '直接 submit'), done=lidx(S(6), 'copy_current_request_context', 'copy_context().run'), kv=KV([['直接 submit', 'RuntimeError'], ['copy_current_request_context', '读到 /'], ['copy_context().run', '读到 /']], ['直接 submit'])),
]
A = mkartf('f6', 6, 'Flask,Context Local,ContextVar,线程隔离,真实验证,动画演示',
    f'验证上下文隔离:ContextVar 在新线程里不继承(thread_inherit_context=0);asyncio 任务各复制一份;threading.local 在协程间会串;werkzeug.Local 底层是 ContextVar;gunicorn 8 线程下 16 个并发请求 g 读回 {gu[1]} 个错值;线程池要用 copy_context 才带得上请求。',
    'Flask 靠什么保证两个同时进来的请求看到的是各自的 request 和 g?线程、协程、线程池分别怎么样?这篇用 ContextVar、threading.local 和真实的 gunicorn 并发请求逐个验证。',
    [('0', '16 个并发请求里 g 值读回不一致的个数'), ('3 / 3', '3 个协程用 ContextVar 各读到自己的值(threading.local 则全读到 Z)'), ('0', 'sys.flags.thread_inherit_context(新线程默认不继承上下文)')],
    [('线程里的 ContextVar', '<p>上一篇:<a href="flask-current-app-request-g.html">current_app、request、g 的实现</a>;下一篇:<a href="flask-request-lifecycle.html">请求进入 Flask 后的完整生命周期</a>。</p>'), ('asyncio 任务', None), ('threading.local 的问题', None), ('werkzeug.local.Local', None), ('gunicorn 多线程下的 g', None), ('线程池', None)],
    steps, [ENV_F + '。gunicorn 用 --workers 1 --threads 8', '没有验证:gevent / eventlet 下的 greenlet 隔离(见第 142 篇)、free-threaded(无 GIL)Python 构建下的行为、thread_inherit_context 设为 1 时的表现、更大并发下的 g 隔离'], '上下文隔离')
