from lib import *
S = SS('f138')
R = J('f138')
steps = [
    step("async 视图的代码不在主线程运行:sync 视图的线程是 MainThread(main = True),async 视图的线程名是 ThreadPoolExecutor-1_0(main = False)——asgiref 把协程放到一个工作线程里的新事件循环中执行,执行完把结果交回请求线程。", t=tl(S(1)), done=lidx(S(1), 'sync 视图', 'async 视图'), kv=KV([['sync 视图', '请求所在的线程'], ['async 视图', '线程池里的线程 + 新事件循环']], ['async 视图'])),
    step("async 视图里能用的上下文:request.path(/ctx)、current_app(app 名是 b)、g(拿到 before_request 里设置的值)、session(能读写,session_x = 1)、contextvars(before_request 里设置的 ContextVar 在视图里读到 'set in before_request'),has_request_context() 为 True。请求上下文与 contextvars 都被带进了协程。", t=tl(S(2)), done=lidx(S(2), 'app_name', 'contextvar', 'g_value', 'has_request_context', 'request_path', 'session_x'), kv=KV([['request / g / session / current_app', '都可用'], ['contextvars', '被带过去']], ['request / g / session / current_app'])),
    step("响应返回之后,视图里 create_task 启动的任务不会继续:create_task 一个 0.5 秒后置位的任务、视图立刻返回,1 秒后检查,状态仍是 not run——请求结束时这个请求的事件循环就被关闭了,没跑完的任务被取消。await 了任务再返回,任务状态是 finished。要在响应之后继续做的事,要交给后台任务系统(第 146 篇),不是 create_task。", t=tl(S(3)), mark=lidx(S(3), 'create_task 之后'), done=lidx(S(3), 'await 了任务'), kv=KV([['create_task + 立刻返回', '响应后任务被取消'], ['await 任务', '正常完成']], ['create_task + 立刻返回'])),
    step("模块级的 asyncio 对象(Event、Lock)绑定到事件循环,而每个请求都是新循环:第一个请求能用(Event 等了 0.2 秒超时返回,Lock 的两个协程顺序执行返回 lock ok);第二个请求都返回 500,让异常传播出来是 RuntimeError「<asyncio.locks.Event object ...> is bound to a different event loop」与 Lock 的同样错误。异步的锁、队列、连接池不能是模块级全局的(跨请求共享),要在每个请求里创建,或用线程安全的同步版本。", t=tl(S(4)), mark=lidx(S(4), '500', 'bound to a different event loop'), done=lidx(S(4), '200'), kv=KV([['全局 asyncio.Event / Lock', '第二个请求 RuntimeError'], ['原因', '每个请求一个新事件循环']], ['全局 asyncio.Event / Lock'])),
    step("从 async 视图里启动的线程:asyncio.to_thread 里直接 has_request_context() 是 True(它会复制当前的 contextvars,请求上下文跟着过去),再用 copy_current_request_context 包装也能读到 request.path;而自己 new 的 threading.Thread 里 has_request_context() 是 False——普通线程没有上下文,要自己用 copy_current_request_context 包装(这一点只在 to_thread 之外的线程验证了无上下文)。", t=tl(S(5)), done=lidx(S(5), 'to_thread', 'copy_current_request_context'), mark=lidx(S(5), 'threading.Thread'), kv=KV([['asyncio.to_thread', '自动带上下文'], ['threading.Thread', '没有上下文']], ['threading.Thread'])),
]
A = mkartf('f138', 138, 'Flask,async,事件循环,上下文,asyncio,真实验证,动画演示',
    '实测 Flask async 视图的执行边界:协程在工作线程的新事件循环里运行、request 与 g 与 session 与 contextvars 都可用、响应返回后 create_task 的任务被取消、模块级的 asyncio.Event 与 Lock 第二个请求报 bound to a different event loop、asyncio.to_thread 带上下文而普通线程没有。',
    'async 视图到底在哪里执行?请求上下文还在吗?视图返回后后台任务会怎样?全局的异步锁能用吗?这篇逐项验证 async 视图的边界。',
    [('新事件循环', '每个请求都有自己的事件循环,请求结束就关闭'), ('bound to a different event loop', '模块级 asyncio.Event 与 Lock 在第二个请求里的报错'), ('not run', '视图返回后 create_task 启动的任务 1 秒后的状态')],
    [('执行线程', '<p>上一篇:<a href="flask-async-view.html">Flask Async View</a>;下一篇:<a href="flask-sync-blocks-async.html">同步代码阻塞异步请求</a>。</p>'), ('可用的上下文', None), ('响应之后的任务', None), ('全局 asyncio 对象', None), ('线程里的上下文', None)],
    steps, [ENV_F + '。asgiref 3.12.1', '没有验证:在 ASGI 服务器下同样的行为(第 140 篇)、异步数据库连接池与 HTTP 客户端的正确生命周期管理、Flask 的 ensure_sync 与 async 错误处理器、取消(客户端断开)时协程收到的异常'], 'Async View 执行边界')
