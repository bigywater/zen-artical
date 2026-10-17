from lib import *
S = SS('f141')
R = J('f141'); en = R['env']; kv_ = R['keyvals']; st = R['stream']
ks = list(st)
steps = [
    step(f"同一个 Flask 应用,交给它的 WSGI environ(去掉 HTTP_ 头)在四种环境里的差别:gunicorn(原生 WSGI){en[ks[0]]['n']} 个键;a2wsgi {en[ks[1]]['n']} 个,多了 asgi.scope(原始的 ASGI scope 被放进来);asgiref WsgiToAsgi {en[ks[2]]['n']} 个;我自己写的 mini 适配器 {en[ks[3]]['n']} 个。适配器都少了 gunicorn 特有的键(RAW_URI、SERVER_SOFTWARE、gunicorn.socket、wsgi.file_wrapper、wsgi.early_hints 等);REMOTE_PORT 在 asgiref 与 mini 里没有。wsgi.input 的类型各不相同(gunicorn 与 a2wsgi 的 Body、asgiref 的 SpooledTemporaryFile、mini 的 BytesIO)。关键值 SERVER_NAME、REMOTE_ADDR、wsgi.url_scheme 在四种环境里一致。", t=tl(S(1)), done=lidx(S(1), '[gunicorn', '几个关键值'), mark=lidx(S(1), '少了'), kv=KV([['环境字典', '适配器把 ASGI scope 翻译成 environ'], ['缺失的键', '服务器特有的键不会有']], ['缺失的键'])),
    step(f"请求体与响应流:POST 2 MB 的请求体,四种环境里 Flask 都读到完整的 {st[ks[0]][0]} 字节。流式响应(每 0.3 秒一块、共 4 块):gunicorn 各块到达是 {st[ks[0]][1]} ms,a2wsgi {st[ks[1]][1]},asgiref {st[ks[2]][1]},都是边生成边发出;我自己写的 mini 适配器把 WSGI 应用返回的所有块收集完再一次性发送,4 块在 {st[ks[3]][1][0]} ms 同时到达——写适配器时,响应必须按块转发,否则流式响应(第 118、149 篇)会失效。", b=bars([['gunicorn 首块', max(st[ks[0]][1][0], 1), f'{st[ks[0]][1][0]} ms'], ['a2wsgi 首块', max(st[ks[1]][1][0], 1), f'{st[ks[1]][1][0]} ms'], ['mini 适配器 首块', st[ks[3]][1][0], f'{st[ks[3]][1][0]} ms']], st[ks[3]][1][0], mark=[2], done=[0, 1]), t=tl(S(2)), done=lidx(S(2), 'gunicorn', 'a2wsgi', 'asgiref'), mark=lidx(S(2), 'mini'), kv=KV([['a2wsgi / asgiref', '边生成边发出'], ['收集完再发的适配器', '流式失效']], ['收集完再发的适配器'])),
    step("自己写一个最小适配器大约 25 行:从 ASGI scope 与请求体拼出 WSGI environ(REQUEST_METHOD、PATH_INFO、QUERY_STRING、SERVER_NAME、REMOTE_ADDR、wsgi.input、头里的 HTTP_*),在线程里同步调用 WSGI 应用,再把状态与头与正文用 http.response.start 和 http.response.body 发回去。它能跑通 Flask 的路由(GET /hello → 200 hi)与 404。它只支持 HTTP、不流式、整体读取请求体——这就是生产里该用现成适配器的原因。", t=tl(S(3)), done=lidx(S(3), 'GET /hello', 'GET /nope'), kv=KV([['适配器的工作', 'scope → environ,同步调用,结果 → send'], ['自己写的限制', '不流式,只支持 HTTP']], ['适配器的工作'])),
]
A = mkartf('f141', 141, 'Flask,WSGI,ASGI,适配器,a2wsgi,asgiref,真实验证,动画演示',
    '实测 WSGI 到 ASGI 的适配:对比 gunicorn、a2wsgi、asgiref 与自己写的 25 行适配器交给 Flask 的 environ 差别(asgi.scope、缺失的服务器特有键、wsgi.input 的类型),2 MB 请求体读取,以及流式响应是否边生成边发出——收集完再发的适配器让 4 块同时到达。',
    'WSGI 到 ASGI 的适配器到底做了什么?环境字典里少了什么?流式响应经过它们会怎样?这篇用 Flask 的 request.environ 把四种适配方式摊开对比,并亲手写一个最小适配器。',
    [(f'{en[ks[0]]["n"]} / {en[ks[1]]["n"]} / {en[ks[2]]["n"]}', 'environ 键的个数:gunicorn、a2wsgi、asgiref'), ('asgi.scope', 'a2wsgi 额外放进 environ 的原始 ASGI scope'), (f'{st[ks[3]][1][0]} ms', '一次性收集响应的适配器下,流式响应第一块到达的时间')],
    [('environ 的差别', '<p>上一篇:<a href="flask-flask-and-asgi.html">Flask 与 ASGI</a>;下一篇:<a href="flask-greenlet-context.html">Greenlet 与 Flask Context</a>。</p>'), ('请求体与响应流', None), ('自己写的最小适配器', None)],
    steps, [ENV_F + '。uvicorn 0.54.0、a2wsgi 1.10.10、asgiref 3.12.1、gunicorn gthread', '没有验证:ASGI lifespan 事件的处理、WebSocket 的转发、请求体边到边读(流式上传)、错误与异常在适配器中的传播、SCRIPT_NAME 与 root_path 的映射细节'], 'WSGI 到 ASGI 的适配')
