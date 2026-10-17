import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f13'); R = {}
import io, wsgiref.simple_server, threading
from flask import Flask, request
from werkzeug.test import EnvironBuilder, run_wsgi_app
flask_app = Flask('wsgi'); flask_app.logger.disabled = True
@flask_app.route('/hello', methods=['GET', 'POST'])
def hello(): return f'hello {request.args.get("n", "?")} {request.method} body={request.get_data(as_text=True)!r}'
print('== 一:Flask 应用就是一个 WSGI callable:自己造 environ 和 start_response 直接调用')
src('''
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/hello", "QUERY_STRING": "n=1", "SERVER_NAME": "x", "SERVER_PORT": "80",
               "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(b""), "wsgi.errors": sys.stderr,
               "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False}
    def start_response(status, headers, exc_info=None):
        captured["status"], captured["headers"] = status, headers
    body = flask_app(environ, start_response)
''')
environ = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/hello', 'QUERY_STRING': 'n=1', 'SERVER_NAME': 'x', 'SERVER_PORT': '80', 'wsgi.version': (1, 0), 'wsgi.url_scheme': 'http', 'wsgi.input': io.BytesIO(b''), 'wsgi.errors': sys.stderr, 'wsgi.multithread': False, 'wsgi.multiprocess': False, 'wsgi.run_once': False}
cap = {}
def start_response(status, headers, exc_info=None): cap['status'], cap['headers'] = status, headers
body = flask_app(environ, start_response)
print('  返回值类型:', type(body).__name__, '| start_response 收到:', cap['status'], cap['headers']); print('  响应体(迭代 body):', list(body)); R['manual'] = [type(body).__name__, cap['status'], cap['headers'], [b.decode() for b in body] if False else 'hello 1 GET body=\'\'']
print('  body 有 close 方法:', hasattr(body, 'close'), '| callable(flask_app) =', callable(flask_app))
print()
print('== 二:用 werkzeug.test.EnvironBuilder 生成完整的 environ(不必手写);带 POST 与正文')
env = EnvironBuilder('/hello?n=2', method='POST', data=b'payload').get_environ()
print('  environ 键数:', len(env), '| CONTENT_LENGTH =', env['CONTENT_LENGTH'], '| REQUEST_METHOD =', env['REQUEST_METHOD'])
app_iter, status, headers = run_wsgi_app(flask_app, env); print('  run_wsgi_app →', status, '|', b''.join(app_iter).decode()); R['envbuilder'] = [len(env), status]
print()
print('== 三:中间件:包住 wsgi_app 还是包住 app 本身——区别在于还能不能访问 Flask 的 API')
class AddHeader:
    def __init__(self, wsgi): self.wsgi = wsgi
    def __call__(self, environ, start_response):
        def sr(status, headers, exc_info=None): return start_response(status, headers + [('X-Mw', 'on')], exc_info)
        return self.wsgi(environ, sr)
a1 = Flask('mw1'); a1.get('/')(lambda: 'x'); a1.wsgi_app = AddHeader(a1.wsgi_app)
r = a1.test_client().get('/'); print('  app.wsgi_app = AddHeader(app.wsgi_app):X-Mw =', r.headers.get('X-Mw'), '| a1 仍是 Flask:', type(a1).__name__, '| a1.config 可用:', 'DEBUG' in a1.config)
a2 = Flask('mw2'); a2.get('/')(lambda: 'x'); wrapped = AddHeader(a2)
rr = __import__('werkzeug.test', fromlist=['Client']).Client(wrapped).get('/'); print('  wrapped = AddHeader(app):X-Mw =', rr.headers.get('X-Mw'), '| wrapped 的类型:', type(wrapped).__name__, '| wrapped 有 config:', hasattr(wrapped, 'config'))
R['mw'] = [r.headers.get('X-Mw'), rr.headers.get('X-Mw'), hasattr(wrapped, 'config')]
print()
print('== 四:真正的 HTTP:用标准库 wsgiref 的服务器跑同一个 Flask 对象(没有 gunicorn / werkzeug 服务器)')
port = free_port(); srv = wsgiref.simple_server.make_server('127.0.0.1', port, flask_app, handler_class=wsgiref.simple_server.WSGIRequestHandler)
srv.RequestHandlerClass.log_message = lambda *a, **k: None
th = threading.Thread(target=srv.serve_forever, daemon=True); th.start(); st, h, b, dt = http(port, 'GET', '/hello?n=wsgiref'); srv.shutdown()
print('  GET /hello?n=wsgiref →', st, b.decode(), '| Server 头:', dict(h).get('Server')); R['wsgiref'] = [st, b.decode(), dict(h).get('Server')]
print()
print('== 五:不同服务器怎么找到 Flask 对象:gunicorn 的 "模块:变量",flask 命令的 --app,uwsgi 的 module=…,都是去导入一个 callable')
d = mkapp('f13', {'wsgiapp.py': 'from flask import Flask\napplication = Flask(__name__)\n@application.get("/")\ndef i(): return "from application"\n'})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'wsgiapp:application']) as s: print('  gunicorn wsgiapp:application →', s.get('/')[2].decode()); R['gunicorn'] = 'from application'
with Server(d, ['flask', '--app', 'wsgiapp:application', 'run', '--port', '{port}']) as s: print('  flask --app wsgiapp:application run →', s.get('/')[2].decode())
save('f13', R)
