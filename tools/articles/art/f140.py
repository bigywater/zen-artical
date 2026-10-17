from lib import *
S = SS('f140')
R = J('f140'); b = R['bench']; h = b['/hello']; w = b['/work']
kh = list(h); kw = list(w)
steps = [
    step(f"同一个 Flask 应用,4 种部署方式,ApacheBench 4000 个请求、32 并发(本机 10 核,压测工具也占 CPU,每种只测了一次,只看相对关系)。轻量接口 /hello:gunicorn sync×4 {h[kh[0]][0]:.0f} 请求/秒、gunicorn gthread 4×4 {h[kh[1]][0]:.0f}、uvicorn×4 加 a2wsgi {h[kh[2]][0]:.0f}、uvicorn×4 加 asgiref WsgiToAsgi {h[kh[3]][0]:.0f}。有 2 万次乘加的 /work:{w[kw[0]][0]:.0f}、{w[kw[1]][0]:.0f}、{w[kw[2]][0]:.0f}、{w[kw[3]][0]:.0f}。计算占主导时几种方式几乎一样(都是 4 个进程在算);轻量接口上 a2wsgi 那一栏高出近一倍,我没有重复测量也没有分析原因,不能据此下结论。所有请求都成功(失败 0)。", b=bars([['gunicorn sync×4', h[kh[0]][0], f'{h[kh[0]][0]:.0f}'], ['gunicorn gthread', h[kh[1]][0], f'{h[kh[1]][0]:.0f}'], ['uvicorn + a2wsgi', h[kh[2]][0], f'{h[kh[2]][0]:.0f}'], ['uvicorn + WsgiToAsgi', h[kh[3]][0], f'{h[kh[3]][0]:.0f}']], h[kh[2]][0], mark=[2], done=[0, 1, 3]), t=tl(S(1)), done=lidx(S(1), '[轻量接口', '[有点计算'), kv=KV([['/hello 请求/秒', f'{h[kh[0]][0]:.0f} / {h[kh[1]][0]:.0f} / {h[kh[2]][0]:.0f} / {h[kh[3]][0]:.0f}'], ['/work 请求/秒', f'{w[kw[0]][0]:.0f} / {w[kw[1]][0]:.0f} / {w[kw[2]][0]:.0f} / {w[kw[3]][0]:.0f}']], ['/hello 请求/秒'])),
    step("WebSocket:Flask 经 a2wsgi 放到 uvicorn 上,对 /ws 这个只有普通 GET 路由的路径发 WebSocket 握手,得到 403(WebSocketBadStatusException: Handshake status 403);同一路径的普通 HTTP GET 是 200。WSGI 适配器只翻译 HTTP 请求,WebSocket 这类 ASGI 才有的协议它不处理。要在 Flask 里做 WebSocket,需要 Flask-SocketIO 一类的方案(第 78、150 篇),不是靠换 ASGI 服务器。", t=tl(S(2)), mark=lidx(S(2), '403', 'WebSocket 握手'), done=lidx(S(2), '普通 HTTP GET'), kv=KV([['WSGI 适配器', '只翻译 HTTP'], ['WebSocket 握手', '403']], ['WSGI 适配器'])),
]
A = mkartf('f140', 140, 'Flask,ASGI,uvicorn,a2wsgi,WebSocket,真实验证,动画演示',
    f'实测 Flask 与 ASGI:同一个 Flask 应用用 gunicorn sync、gunicorn gthread、uvicorn 加 a2wsgi、uvicorn 加 WsgiToAsgi 四种方式,用 ApacheBench 压测轻量与计算型两种接口(单次测量);WSGI 适配器下 WebSocket 握手返回 403。',
    'Flask 是 WSGI 框架,放到 uvicorn 这类 ASGI 服务器上有什么用?吞吐量会变好吗?能不能因此支持 WebSocket?这篇用真实的 ApacheBench 压测与 WebSocket 握手,把这两个问题的答案量出来。',
    [(f'{h[kh[0]][0]:.0f} / {h[kh[2]][0]:.0f}', '轻量接口 /hello 的请求/秒:gunicorn sync×4 与 uvicorn×4 加 a2wsgi(单次测量)'), ('403', '对 Flask 经 WSGI 适配器暴露的路径发 WebSocket 握手得到的状态码'), ('失败 0', '全部压测请求都成功')],
    [('四种部署的压测', '<p>上一篇:<a href="flask-sync-blocks-async.html">同步代码阻塞异步请求</a>;下一篇:<a href="flask-wsgi-to-asgi.html">WSGI 到 ASGI 的适配</a>。</p><p>压测工具是系统自带的 ApacheBench,与被测服务同机运行,每个数字只测一次。</p>'), ('WebSocket', None)],
    steps, [ENV_F + '。uvicorn 0.54.0、gunicorn、a2wsgi 1.10.10、asgiref 3.12.1、ApacheBench', '没有验证:多次重复测量的方差、keep-alive 开启时的数字、HTTP/2、生产环境的反向代理叠加、Quart 等原生异步 Flask 兼容框架、更长时间的稳定性'], 'Flask 与 ASGI', panels=[('t', 'term', '实验输出'), ('b', 'bars', '请求/秒'), ('kv', 'kv', '要点')])
