from lib import *
S = SS('f13')
R = J('f13')
steps = [
    step("自己造 environ 与 start_response 直接调用 flask_app(environ, start_response):返回值是 ClosingIterator(带 close 方法),start_response 收到 200 OK 与头 [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', '19')];迭代 body 得到 [b\"hello 1 GET body=''\"]。callable(flask_app) 是 True —— Flask 对象本身就是一个 WSGI callable。", t=tl(S(1)), done=lidx(S(1), '返回值类型', '响应体(迭代 body)'), mark=lidx(S(1), '有 close 方法'), kv=KV([['返回值', 'ClosingIterator(有 close)'], ['start_response', '200 OK + 头'], ['callable(app)', 'True']], ['callable(app)'])),
    step("werkzeug.test.EnvironBuilder 能生成完整的 environ(这次 18 个键,POST 带 7 字节正文:CONTENT_LENGTH = 7);run_wsgi_app(flask_app, env) 返回 200 OK 与正文 hello 2 POST body='payload'。不必手写 environ 就能在不起服务器的情况下调试 WSGI 应用。", t=tl(S(2)), done=lidx(S(2), 'environ 键数', 'run_wsgi_app'), kv=KV([['EnvironBuilder', '生成 18 个 environ 键'], ['run_wsgi_app', "200 OK,正文 hello 2 POST body='payload'"]], ['run_wsgi_app'])),
    step("中间件的包法:app.wsgi_app = AddHeader(app.wsgi_app) 后,响应带 X-Mw: on,且 app 仍然是 Flask 对象、app.config 可用;wrapped = AddHeader(app) 同样加上了头,但 wrapped 的类型是 AddHeader,没有 config 属性(hasattr 为 False),Flask 的 API 用不了。包住 wsgi_app 是保留 Flask 对象的做法。", t=tl(S(3)), done=lidx(S(3), 'app.wsgi_app = AddHeader'), mark=lidx(S(3), 'wrapped = AddHeader(app)'), kv=KV([['包 app.wsgi_app', 'app 还是 Flask,config 可用'], ['包 app', 'wrapped 是 AddHeader,没有 config']], ['包 app.wsgi_app'])),
    step("用标准库 wsgiref 的服务器(不是 gunicorn 也不是 Werkzeug 服务器)跑同一个 Flask 对象:GET /hello?n=wsgiref → 200,正文 hello wsgiref GET body='',响应的 Server 头是 WSGIServer/0.2 CPython/3.14.7。只要是 WSGI 服务器就能运行 Flask 应用。", t=tl(S(4)), done=lidx(S(4), 'GET /hello?n=wsgiref'), kv=KV([['服务器', 'wsgiref.simple_server'], ['响应', '200 hello wsgiref']], ['服务器'])),
    step("不同的启动方式都是导入一个 callable:gunicorn wsgiapp:application 与 flask --app wsgiapp:application run,都能找到模块 wsgiapp 里叫 application 的 Flask 对象并返回「from application」。", t=tl(S(5)), done=lidx(S(5), 'gunicorn wsgiapp:application', 'flask --app wsgiapp:application run'), kv=KV([['gunicorn', '模块:变量'], ['flask --app', '模块:变量']], ['gunicorn'])),
]
A = mkartf('f13', 13, 'Flask,WSGI,wsgi_app,中间件,真实验证,动画演示',
    '验证 Flask 对象就是一个 WSGI callable:手工构造 environ 与 start_response 直接调用;EnvironBuilder 生成 environ;包 wsgi_app 与包 app 的区别;用标准库 wsgiref 服务器运行;gunicorn 与 flask --app 都是按「模块:变量」导入。',
    'WSGI 到底是什么接口?Flask 对象的真实结构是什么?能不能不借助任何服务器就调用它?这篇从 environ 与 start_response 开始,一层层验证。',
    [('2', 'WSGI callable 的参数个数(environ、start_response)'), ('18', 'EnvironBuilder 生成的 environ 键数'), ('wsgiref', '本篇用来运行 Flask 对象的标准库 WSGI 服务器')],
    [('直接调用 Flask 对象', '<p>上一篇:<a href="flask-make-response.html">make_response() 的响应转换过程</a>;下一篇:<a href="flask-flask-and-werkzeug.html">Flask 与 Werkzeug 的关系</a>。第 7 篇看过 wsgi_app 的内部流程:<a href="flask-request-lifecycle.html">请求进入 Flask 后的完整生命周期</a>。</p>'), ('EnvironBuilder', None), ('中间件', None), ('wsgiref 服务器', None), ('服务器如何找到应用', None)],
    steps, [ENV_F, '没有验证:uWSGI 的 module= 写法(见第 173 篇)、WSGI 规范里 start_response 的 exc_info 与 write 回调、environ 里 wsgi.file_wrapper 的作用、生成器响应在 close 时的资源释放顺序'], 'WSGI 应用')
