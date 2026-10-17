from lib import *
S = SS('f7')
R = J('f7'); H = R['hooks']; ph = R['per_hook']
steps = [
    step("用 sys.setprofile 记录一次 GET / 经过的 Flask 函数(实测):wsgi_app → request_context(创建 url_adapter)→ push(推应用上下文、open_session、match_request)→ full_dispatch_request → preprocess_request(my_before)→ dispatch_request(index)→ finalize_request → make_response → process_response(my_after、save_session)→ pop(do_teardown_request、my_teardown、do_teardown_appcontext)。响应 200,带 X-After 头与 Set-Cookie(因为 before_request 里写了 session)。", t=tl(S(1)), done=lidx(S(1), 'wsgi_app', 'push', 'full_dispatch_request', 'dispatch_request'), mark=lidx(S(1), 'my_before', 'my_after', 'my_teardown'), kv=KV([['入口', 'wsgi_app'], ['请求前', 'push → match_request'], ['处理', 'preprocess → dispatch → finalize'], ['收尾', 'pop → teardown']], ['处理'])),
    step("本机 Flask 3.1.3 的 WSGI 入口代码:__call__ 只有一行 return self.wsgi_app(environ, start_response);wsgi_app 先 ctx = self.request_context(environ),在 try 里 ctx.push()、response = self.full_dispatch_request();任何 Exception 交给 self.handle_exception(e);最后 finally 里 ctx.pop(error)。所以无论视图成功还是失败,上下文一定会被弹出。", t=tl(S(2)), done=lidx(S(2), 'def __call__', 'def wsgi_app', 'ctx = self.request_context', 'ctx.pop(error)'), mark=lidx(S(2), 'handle_exception', 'finally'), kv=KV([['__call__', '= wsgi_app'], ['异常', 'handle_exception'], ['finally', 'ctx.pop(error)']], ['finally'])),
    step(f"钩子的成本(test_client,每组 3000 次请求取最小):没有 before_request 钩子每个请求 {H['0']:.1f} µs;10 个空钩子 {H['10']:.1f} µs;100 个空钩子 {H['100']:.1f} µs;平均每个空钩子约 {ph:.2f} µs。钩子本身便宜,慢的是钩子里做的事(查库、读缓存)。", t=tl(S(3)), b=bars([['0 个钩子', H['0'], f"{H['0']:.1f} µs"], ['10 个', H['10'], f"{H['10']:.1f} µs"], ['100 个', H['100'], f"{H['100']:.1f} µs"]], H['100'], done=[0, 1, 2]), kv=KV([['0 / 10 / 100 个钩子', f"{H['0']:.0f} / {H['10']:.0f} / {H['100']:.0f} µs"], ['每个空钩子', f'≈{ph:.2f} µs']], ['每个空钩子'])),
]
A = mkartf('f7', 7, 'Flask,请求生命周期,wsgi_app,真实验证,动画演示',
    f'用 sys.setprofile 记录一次请求经过的 Flask 内部函数:wsgi_app → push → full_dispatch_request → finalize_request → pop;展示 3.1.3 的 wsgi_app 源码;每个空的 before_request 钩子约 {ph:.2f} µs。',
    '一个请求从 WSGI 入口进来,到响应出去,Flask 内部按什么顺序做了哪些事?这篇用调用记录和源码把整条路径摆出来,再量一下钩子的成本。',
    [('wsgi_app', '整个请求处理的入口函数'), ('10', '调用记录里出现的主要阶段函数数(request_context、push、full_dispatch_request 等)'), (f'{ph:.2f} µs', '每个空 before_request 钩子的平均开销')],
    [('一次请求经过的函数', '<p>上一篇:<a href="flask-context-local-isolation.html">Context Local 与线程隔离</a>;下一篇:<a href="flask-before-after-teardown.html">before_request、after_request、teardown_request</a>。</p>'), ('WSGI 入口的源码', None), ('钩子的成本', None)],
    steps, [ENV_F, '没有验证:真实网络服务器(gunicorn)下 wsgi_app 之前的 WSGI 服务器那一段;流式响应时 ctx.pop 的时机(第 42 篇);错误处理路径(handle_exception)在这篇没有展开,见第 8 与第 10 篇'], '请求生命周期')
