import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f23'); R = {}
from flask import Flask, request
from flask.views import MethodView
a = Flask('hm'); a.logger.disabled = True
@a.route('/default')
def default(): return f'method={request.method}'
@a.route('/post-only', methods=['POST'])
def post_only(): return 'posted'
@a.route('/multi', methods=['GET', 'POST', 'DELETE'])
def multi(): return f'multi {request.method}'
@a.get('/g')
def g(): return 'g'
@a.post('/p')
def p(): return 'p'
@a.delete('/d')
def d_(): return 'd'
class Res(MethodView):
    def get(self): return 'MethodView GET'
    def post(self): return 'MethodView POST'
a.add_url_rule('/mv', view_func=Res.as_view('mv'))
c = a.test_client()
print('== 一:默认只允许 GET(自动带上 HEAD 与 OPTIONS);其它方法得到 405 与 Allow 头')
R['rows'] = {}
for path in ('/default', '/post-only', '/multi', '/g', '/p', '/d', '/mv'):
    rule = [r for r in a.url_map.iter_rules() if r.rule == path][0]; R['rows'][path] = sorted(rule.methods); print(f'  {path:<12} methods = {sorted(rule.methods)}')
print()
print('== 二:各种方法请求各路由:状态码(405 时附 Allow 头)')
methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
print(f'  {"路径":<12}' + ''.join(f'{m:<9}' for m in methods)); R['matrix'] = {}
for path in ('/default', '/post-only', '/multi', '/mv'):
    row = {m: c.open(path, method=m).status_code for m in methods}; R['matrix'][path] = row; print(f'  {path:<12}' + ''.join(f'{row[m]:<9}' for m in methods))
r = c.put('/default'); print('  PUT /default 的 405 响应:', r.status, '| Allow =', r.headers.get('Allow')); R['allow'] = r.headers.get('Allow')
print('  正文:', r.get_data(as_text=True).strip().replace('\n', ' | ')[:150]); R['body405'] = r.get_data(as_text=True)[:150]
print()
print('== 三:视图里按 request.method 分支(一个函数同时处理 GET 与 POST),以及方法大小写')
print('  GET /multi →', c.get('/multi').get_data(as_text=True), '| POST /multi →', c.post('/multi').get_data(as_text=True), '| DELETE /multi →', c.delete('/multi').get_data(as_text=True))
r = c.open('/multi', method='get'); print('  方法写成小写 "get" 的请求 →', r.status_code, r.get_data(as_text=True)); R['lower'] = [r.status_code, r.get_data(as_text=True)]
print()
print('== 四:methods 参数里写小写;写了不存在的方法;methods 传字符串而不是列表')
b = Flask('hm2')
b.add_url_rule('/lower', 'lower', lambda: 'x', methods=['get', 'post']); print('  methods=["get","post"] 之后规则的 methods:', sorted([r for r in b.url_map.iter_rules() if r.endpoint == 'lower'][0].methods)); R['lower_methods'] = sorted([r for r in b.url_map.iter_rules() if r.endpoint == 'lower'][0].methods)
try: b.add_url_rule('/str', 'str_', lambda: 'x', methods='POST')
except TypeError as e: print('  methods="POST" → TypeError:', e); R['str'] = str(e)
b.add_url_rule('/weird', 'weird', lambda: 'x', methods=['FOO']); r = b.test_client().open('/weird', method='FOO'); print('  methods=["FOO"] 与自定义方法 FOO 请求 →', r.status_code); R['foo'] = r.status_code
print()
print('== 五:MethodView:按 get/post 等方法名自动分派;没有定义的方法 405')
print('  MethodView 的 methods 属性:', sorted(Res.methods)); R['mv_methods'] = sorted(Res.methods)
print('  PUT /mv →', c.put('/mv').status_code, '| Allow =', c.put('/mv').headers.get('Allow')); R['mv_put'] = [c.put('/mv').status_code, c.put('/mv').headers.get('Allow')]
print()
print('== 六:真实的浏览器表单只能发 GET 与 POST:用一个隐藏字段 _method 模拟 PUT/DELETE 的常见做法(自己写的中间件,不是 Flask 内置)')
class MethodOverride:
    def __init__(self, app): self.app = app
    def __call__(self, environ, start_response):
        from werkzeug.wrappers import Request
        if environ['REQUEST_METHOD'] == 'POST':
            ov = environ.get('HTTP_X_HTTP_METHOD_OVERRIDE')
            if ov: environ['REQUEST_METHOD'] = ov.upper()
        return self.app(environ, start_response)
e = Flask('hm3'); e.add_url_rule('/res', 'res', lambda: f'收到 {request.method}', methods=['DELETE', 'GET']); e.wsgi_app = MethodOverride(e.wsgi_app)
r = e.test_client().post('/res', headers={'X-HTTP-Method-Override': 'DELETE'}); print('  POST + X-HTTP-Method-Override: DELETE →', r.status_code, r.get_data(as_text=True)); R['override'] = [r.status_code, r.get_data(as_text=True)]
save('f23', R)
