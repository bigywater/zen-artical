from lib import *
R = J('d24'); im = R['import']; th = R['threads'].splitlines()
steps = [
    step(f"只导入 proj.wsgi(不发请求):get_wsgi_application() 内部执行了 django.setup(),LabConfig.ready() 已经被调用,并且返回的 {im['WSGI']['cls'].split('.')[-1]} 在创建时就构建了中间件链(MW.__init__ 出现在事件里)。apps.ready = {im['WSGI']['ready'].split('= ')[1]}。", t=tl([f"事件: {e}" for e in im['WSGI']['events']] + [im['WSGI']['ready']], cur=[0, 1]), kv=KV([['WSGI', '导入 wsgi.py = setup + 建中间件链']], ['WSGI'])),
    step(f"ASGI 完全一样:导入 proj.asgi 就 setup(),ready() 被调用,{im['ASGI']['cls'].split('.')[-1]} 创建时构建中间件链。所以「首个请求慢」和「导入模块时慢」不是同一件事:两种入口都在导入时付掉了启动成本。", t=tl([f"事件: {e}" for e in im['ASGI']['events']] + [im['ASGI']['ready']], cur=[0, 1]), kv=KV([['ASGI', '同样在导入时完成']], ['ASGI'])),
    step("调用约定不同:WSGIHandler.__call__(self, environ, start_response) 是普通函数;ASGIHandler.__call__(self, scope, receive, send) 是协程函数。", t=tl(R['sig'].splitlines(), cur=[0, 1]), kv=KV([['WSGI', '(environ, start_response)'], ['ASGI', '(scope, receive, send),协程']], ['ASGI'])),
    step("同步视图与 async 视图各自在哪个线程里运行:WSGI 下同步视图在 MainThread,async 视图被放进线程池(ThreadPoolExecutor-…,main=False);ASGI 下相反——同步视图被放进线程池,async 视图在事件循环所在的 MainThread。Django 总是把「不匹配」的一方桥接过去。", t=tl(th, cur=[0, 3], mark=[1, 2]), n=fl([['WSGI + 同步视图', 'MainThread'], ['WSGI + async 视图', '线程池'], ['ASGI + 同步视图', '线程池'], ['ASGI + async 视图', 'MainThread']], done=[0, 3], mark=[1, 2]), kv=KV([['不匹配的一方', '要跨线程桥接']], ['不匹配的一方'])),
    step("ASGI 服务器通常会先发 lifespan 事件。Django 自带的 ASGIHandler 收到 lifespan 时直接 ValueError: Django can only handle ASGI/HTTP connections, not lifespan.——uvicorn 等服务器把这当成「不支持 lifespan」并继续工作(这一句是服务器的行为,本文只看到了 Django 抛出的异常)。", t=tl([R['lifespan']], mark=[0]), kv=KV([['lifespan', 'Django 自带的 handler 不处理']], ['lifespan'])),
]
A = dict(
    n=24, series='django', tags='Django,WSGI,ASGI,启动,真实验证,动画演示',
    desc='对比 wsgi.py 与 asgi.py 的启动:导入即 django.setup() 并构建中间件链;调用约定 (environ, start_response) vs (scope, receive, send);同步视图与 async 视图在两种入口下分别运行在哪个线程;Django 自带的 ASGIHandler 收到 lifespan 事件会抛 ValueError。',
    lead='WSGI 和 ASGI 两个入口,启动流程有什么不同?同一个视图在两种入口下运行在哪个线程?这篇不启动服务器,直接导入 wsgi.py / asgi.py,并用最小的 WSGI 环境与 ASGI scope 调用 handler。',
    facts=[('导入即启动', '导入 wsgi.py / asgi.py 就会 django.setup() 并构建中间件链,与是否有请求无关'), ('线程互换', 'WSGI:同步视图在主线程、async 视图进线程池;ASGI:同步视图进线程池、async 视图在主线程'), ('lifespan', 'ASGIHandler 收到 lifespan 事件时抛 ValueError')],
    body=[
        sec('导入时发生了什么', '', term('', blk('d24', 1)), '<p><code>get_wsgi_application()</code> 与 <code>get_asgi_application()</code> 都先 <code>django.setup()</code>(所以 <code>ready()</code> 在导入时就跑完),再创建 handler,handler 的构造函数里构建中间件链。</p>'),
        sec('调用约定', '', term('', blk('d24', 2)), '<p>WSGI 是同步的可调用对象;ASGI 是协程函数,收发消息都通过 <code>await</code>。</p>'),
        sec('视图在哪个线程里运行', '', term('', blk('d24', 3)), '<p>这是理解「为什么在 ASGI 下调同步 ORM 会有线程问题」「为什么 WSGI 下的 async 视图没有好处」的关键:Django 在两种入口下都保证视图能运行,但「不匹配」的一方要付线程切换的代价(第 111–116 篇)。</p>'),
        sec('lifespan', '', term('', blk('d24', 4)), '<p>需要 startup / shutdown 钩子时要自己包一层 ASGI 应用(本文没有做)。</p>'),
        sec('分步演示:两个入口', '', demo('WSGI vs ASGI', [('t', 'term', '观察'), ('n', 'flow', '线程'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。WSGI 用 wsgiref.util.setup_testing_defaults 构造 environ;ASGI 手写 scope / receive / send 并在 asyncio.run 里调用', '没有验证:真实 gunicorn / uvicorn / daphne 下的线程模型、lifespan 事件在 uvicorn 中的处理、线程池大小限制、thread_sensitive 的含义(第 113 篇)'],
)
