import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f11'); R = {}
import flask
from flask import Flask, abort, jsonify, make_response, redirect, Response
from werkzeug.exceptions import HTTPException, default_exceptions, TooManyRequests, MethodNotAllowed, Unauthorized, NotFound
a = Flask('ab'); a.logger.disabled = True
@a.get('/404')
def v404(): abort(404)
@a.get('/desc')
def vdesc(): abort(404, description='文章 42 不存在')
@a.get('/429')
def v429(): raise TooManyRequests(retry_after=30)
from werkzeug.datastructures import WWWAuthenticate
@a.get('/401')
def v401(): raise Unauthorized(www_authenticate=WWWAuthenticate('basic', {'realm': 'lab'}), description='请先登录')
@a.get('/resp')
def vresp(): abort(Response('自定义响应体', status=418, headers={'X-Why': '茶壶'}))
@a.get('/redir')
def vredir(): abort(redirect('/elsewhere', code=302))
@a.get('/after')
def vafter():
    trace = []
    def inner(): trace.append('进入 inner'); abort(400); trace.append('abort 之后(不会执行)')
    inner(); return 'unreachable'
@a.post('/only-post')
def vpost(): return 'ok'
class Teapot499(HTTPException): code = 499; description = '客户端关闭了请求'
a.aborter.mapping[499] = Teapot499
@a.get('/499')
def v499(): abort(499)
def one(path, method='GET'):
    r = a.test_client().open(path, method=method); return r
print('== 一:abort(404) 生成的响应:状态、Content-Type、正文、头')
r = one('/404'); print('  ', r.status); [print(f'    {k}: {v}') for k, v in r.headers]; print('    正文:', r.get_data(as_text=True).strip().replace('\n', ' | ')); R['abort404'] = [r.status, dict(r.headers), r.get_data(as_text=True)]
print()
print('== 二:abort(404, description=...):自定义描述会放进默认错误页;e.description / e.name / e.code')
r = one('/desc'); print('  ', r.status, '|', r.get_data(as_text=True).strip().replace('\n', ' | ')); R['desc'] = r.get_data(as_text=True)
try: abort(404, description='文章 42 不存在')
except HTTPException as e: print('  捕获到的异常:', type(e).__name__, '| code =', e.code, '| name =', e.name, '| description =', e.description); R['exc'] = [type(e).__name__, e.code, e.name, e.description]
print()
print('== 三:有些异常会带响应头:429 的 Retry-After、405 的 Allow、401 的 WWW-Authenticate')
r = one('/429'); print('  429:', r.status, '| Retry-After =', r.headers.get('Retry-After')); R['retry'] = r.headers.get('Retry-After')
r = one('/only-post'); print('  GET 一个只允许 POST 的路由:', r.status, '| Allow =', r.headers.get('Allow')); R['allow'] = [r.status, r.headers.get('Allow')]
r = one('/401'); print('  401:', r.status, '| WWW-Authenticate =', r.headers.get('WWW-Authenticate')); R['wwwauth'] = r.headers.get('WWW-Authenticate')
print()
print('== 四:abort 传入一个现成的 Response(或重定向):直接作为最终响应')
r = one('/resp'); print('  abort(Response(...)):', r.status, '|', r.get_data(as_text=True), '| X-Why =', r.headers.get('X-Why')); R['resp'] = [r.status, r.get_data(as_text=True), r.headers.get('X-Why')]
r = one('/redir'); print('  abort(redirect("/elsewhere")):', r.status, '| Location =', r.headers.get('Location')); R['redir'] = [r.status, r.headers.get('Location')]
print()
print('== 五:abort 抛出异常,后面的代码不会执行;不认识的状态码:LookupError')
r = one('/after'); print('  /after:', r.status)
try: abort(498)
except LookupError as e: print('  abort(498) → LookupError:', e); R['lookup'] = str(e)
print()
print('== 六:abort 背后的映射表:werkzeug 里有多少个状态码对应异常类;Flask 的 abort 调用的是 current_app.aborter')
print(f'  default_exceptions 共 {len(default_exceptions)} 个状态码;其中 4xx {len([c for c in default_exceptions if 400 <= c < 500])} 个、5xx {len([c for c in default_exceptions if c >= 500])} 个'); R['n'] = [len(default_exceptions), len([c for c in default_exceptions if 400 <= c < 500]), len([c for c in default_exceptions if c >= 500])]
print('  部分:', {c: default_exceptions[c].__name__ for c in (400, 401, 403, 404, 405, 409, 410, 413, 415, 418, 422, 429, 500, 501, 503)}); R['some'] = {c: default_exceptions[c].__name__ for c in (400, 401, 403, 404, 405, 409, 410, 413, 415, 418, 422, 429, 500, 501, 503)}
print('  type(current_app.aborter) =', end=' ')
with a.app_context(): print(type(flask.current_app.aborter).__name__, '| 是否是 app.aborter:', flask.current_app.aborter is a.aborter)
r = one('/499'); print('  事先往 app.aborter.mapping 里注册了 499 之后,abort(499):', r.status, '|', r.get_data(as_text=True).strip().replace('\n', ' | ')[:100]); R['custom499'] = [r.status, r.get_data(as_text=True)[:100]]
save('f11', R)
