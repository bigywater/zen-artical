from lib import *
S = SS('f143')
R = J('f143'); rc = R['race']
steps = [
    step("request、g、current_app 都是 LocalProxy,背后的真实对象分别是 Request、_AppCtxGlobals、Flask;你读 request.path 时,代理去「当前上下文」里取真实对象。Werkzeug 的 Local 源码里用的是 ContextVar(True),没有用 threading.local(False)——所以它按「执行上下文」而不是按线程隔离,线程与 greenlet(第 142 篇)与异步任务都适用。", t=tl(S(1)), done=lidx(S(1), 'type(request)', 'type(g)', 'type(current_app)', 'ContextVar'), kv=KV([['request / g / current_app', 'LocalProxy,转发到当前上下文里的对象'], ['存储', 'ContextVar,不是 threading.local']], ['存储'])),
    step("三个线程各自推入自己的请求上下文(路径 /a、/b、/c),睡 0.2 秒再读 request.path,各自读到自己的路径(A → /a、B → /b、C → /c),没有串。在任何上下文之外访问 request.path,抛 RuntimeError「Working outside of request context.」。", t=tl(S(2)), done=lidx(S(2), '三个线程'), mark=lidx(S(2), '上下文外'), kv=KV([['每个线程自己的上下文', '互不影响'], ['上下文之外', 'RuntimeError']], ['每个线程自己的上下文'])),
    step("把请求带进新线程:新线程里直接读 request.path,得到 RuntimeError「Working outside of request context.」(新线程没有上下文);用 copy_current_request_context 包装线程函数后,读到 /parent。要在后台线程里用 request,必须显式复制上下文(见第 146 篇)。", t=tl(S(3)), mark=lidx(S(3), '直接读'), done=lidx(S(3), 'copy_current_request_context'), kv=KV([['新线程', '默认没有上下文'], ['copy_current_request_context', '复制调用时的上下文']], ['新线程'])),
    step("g 属于应用上下文,不属于线程:嵌套推入两个应用上下文,内层写 g.v = 'inner',外层的 g.v 仍然是 'outer';请求上下文里的 g 就是它所属应用上下文的 g。所以 g 的生命周期是「一个应用上下文」,通常就是一个请求。", t=tl(S(4)), done=lidx(S(4), '内层', '回到外层', '请求上下文里的 g'), kv=KV([['g', '属于应用上下文'], ['嵌套', '各有各的 g']], ['g'])),
    step(f"模块级全局变量不隔离,所有线程共享:100 次并发 POST(gunicorn gthread 16 线程),每次「读出计数、睡 1 ms、写回计数 + 1」,不加锁的计数只到 {rc['unlocked']}(期望 100,丢了 {100 - rc['unlocked']} 次更新);用 threading.Lock 保护读算写后是 {rc['locked']}。多进程部署时,每个进程各有一份全局变量,加锁也只在本进程内有效(第 145 篇)。", b=bars([['不加锁', rc['unlocked'], str(rc['unlocked'])], ['加锁', rc['locked'], str(rc['locked'])]], 100, mark=[0], done=[1]), t=tl(S(5)), mark=lidx(S(5), '不加锁'), kv=KV([['不加锁', f"{rc['unlocked']} / 100"], ['threading.Lock', f"{rc['locked']} / 100"]], ['不加锁'])),
]
A = mkartf('f143', 143, 'Flask,Thread Local,ContextVar,请求隔离,LocalProxy,真实验证,动画演示',
    f'实测 Flask 的请求隔离:request、g、current_app 是 LocalProxy,Werkzeug 的 Local 基于 ContextVar;三个线程各自的请求上下文互不影响;新线程要用 copy_current_request_context;g 属于应用上下文;模块级全局变量被线程共享,100 次并发读算写不加锁只计到 {rc["unlocked"]}。',
    'request 为什么能在任何地方直接用?它是怎么做到每个请求互不干扰的?新线程里为什么读不到?全局变量安全吗?这篇用真实的多线程把每一层都验证一遍。',
    [('ContextVar', 'Werkzeug Local 的存储,不是 threading.local'), (f'{rc["unlocked"]} / 100', '100 次并发读算写,不加锁时全局计数的结果'), ('copy_current_request_context', '把请求上下文带进新线程的办法')],
    [('LocalProxy 与 ContextVar', '<p>上一篇:<a href="flask-greenlet-context.html">Greenlet 与 Flask Context</a>;下一篇:<a href="flask-gunicorn-worker-types.html">Gunicorn Worker 类型</a>。</p>'), ('线程各有各的上下文', None), ('后台线程里的 request', None), ('g 的归属', None), ('全局变量不隔离', None)],
    steps, [ENV_F + '。gunicorn gthread worker', '没有验证:Werkzeug 旧版本(2.0 之前基于 threading.local 与 greenlet 的实现)的差别、asyncio 任务里上下文的复制时机、current_app 在应用工厂与测试里的推入顺序、全局变量在多进程部署下的表现(见第 145 篇)'], 'Thread Local 与请求隔离')
