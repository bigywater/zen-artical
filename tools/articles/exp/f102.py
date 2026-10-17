import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f102'); R = {}
import uuid, json
from flask import Flask, Blueprint, jsonify, request, abort, g
from werkzeug.exceptions import HTTPException
def routes(app):
    @app.get('/api/items/<int:i>')
    def item(i):
        if i == 0: abort(404, description='item 0 不存在')
        if i == 13: raise RuntimeError('db password is hunter2')
        if i == 7: raise ApiError(409, 'conflict', '版本冲突', {'current': 5})
        return {'id': i}
    @app.post('/api/echo')
    def echo(): return request.get_json()
    @app.get('/page')
    def page(): abort(403)
class ApiError(Exception):
    def __init__(self, status, code, message, extra=None): self.status, self.code, self.message, self.extra = status, code, message, extra or {}
def show(c, label, method, path, **kw):
    r = getattr(c, method)(path, **kw); ct = r.headers.get('Content-Type', ''); body = r.get_data(as_text=True).strip().replace('\n', ' '); print(f'  {label:<26} → {r.status_code} {ct.split(";")[0]:<17} {body[:110]}'); return r
print('== 一:默认:所有错误都是 HTML,调用方是 API 客户端也一样')
a = Flask('d1'); a.logger.disabled = True; routes(a); a.config['PROPAGATE_EXCEPTIONS'] = False; c = a.test_client(); R['default'] = {}
for label, m, p, kw in (('不存在的路径', 'get', '/api/nope', {}), ('abort(404, description=...)', 'get', '/api/items/0', {}), ('方法不允许', 'delete', '/api/items/1', {}), ('未处理异常', 'get', '/api/items/13', {}), ('非法 JSON', 'post', '/api/echo', dict(data='{', content_type='application/json'))):
    r = show(c, label, m, p, **kw); R['default'][label] = [r.status_code, r.headers.get('Content-Type')]
print()
print('== 二:统一成 JSON:一个 HTTPException 处理器 + 一个自定义异常 + 一个兜底 Exception 处理器')
a = Flask('d2'); a.logger.disabled = True; routes(a); a.config['PROPAGATE_EXCEPTIONS'] = False
def err(status, code, message, **extra): 
    r = jsonify(error={'code': code, 'message': message, 'request_id': getattr(g, 'rid', None), **extra}); r.status_code = status; return r
@a.before_request
def rid(): g.rid = request.headers.get('X-Request-Id') or uuid.uuid4().hex[:8]
@a.errorhandler(ApiError)
def h_api(e): return err(e.status, e.code, e.message, **e.extra)
@a.errorhandler(HTTPException)
def h_http(e):
    r = err(e.code, e.name.lower().replace(' ', '_'), e.description); [r.headers.__setitem__(k, v) for k, v in e.get_headers() if k.lower() not in ('content-type', 'content-length')]; return r
@a.errorhandler(Exception)
def h_any(e): a.logger.disabled = True; return err(500, 'internal_error', '服务器内部错误')
c = a.test_client(); R['unified'] = {}
for label, m, p, kw in (('不存在的路径', 'get', '/api/nope', {}), ('abort(404, description=...)', 'get', '/api/items/0', {}), ('方法不允许', 'delete', '/api/items/1', {}), ('自定义 ApiError 409', 'get', '/api/items/7', {}), ('未处理异常', 'get', '/api/items/13', {}), ('非法 JSON', 'post', '/api/echo', dict(data='{', content_type='application/json')), ('Content-Type 不对', 'post', '/api/echo', dict(data='{}', content_type='text/plain'))):
    r = show(c, label, m, p, **kw); R['unified'][label] = [r.status_code, r.get_json()]
r = c.delete('/api/items/1'); print('  405 响应保留了 Allow 头:', r.headers.get('Allow')); R['allow'] = r.headers.get('Allow')
r = c.get('/api/items/13', headers={'X-Request-Id': 'abc-123'}); print('  500 的响应里带着调用方传的 request_id:', r.get_json()['error']['request_id'], '| 响应里有没有泄漏异常信息 "hunter2":', 'hunter2' in r.get_data(as_text=True)); R['leak'] = 'hunter2' in r.get_data(as_text=True)
print()
print('== 三:同一个应用里 HTML 页面保持 HTML:处理器按路径前缀区分')
a = Flask('d3'); a.logger.disabled = True; routes(a)
@a.errorhandler(HTTPException)
def h(e):
    if request.path.startswith('/api/'): return jsonify(error=e.name), e.code
    return e
c = a.test_client(); r1 = show(c, '/api/nope', 'get', '/api/nope'); r2 = show(c, '/page(abort 403)', 'get', '/page'); R['split'] = [r1.headers['Content-Type'], r2.headers['Content-Type']]
print()
print('== 四:蓝图里的 404 处理器抓不到「路由没匹配上」的 404')
a = Flask('d4'); a.logger.disabled = True
bp = Blueprint('api', __name__, url_prefix='/api')
@bp.get('/x')
def x(): abort(404)
@bp.errorhandler(404)
def bp404(e): return jsonify(src='blueprint'), 404
@a.errorhandler(404)
def app404(e): return jsonify(src='app'), 404
a.register_blueprint(bp); c = a.test_client()
r1 = c.get('/api/x'); r2 = c.get('/api/unknown'); print('  蓝图里的视图 abort(404) →', r1.get_json()); print('  /api/unknown(路由没匹配)→', r2.get_json(), '(走的是应用级处理器,不是蓝图的)'); R['bp'] = [r1.get_json(), r2.get_json()]
print()
print('== 五:debug / 测试模式下兜底处理器还生效吗?')
a = Flask('d5'); a.logger.disabled = True; routes(a)
@a.errorhandler(Exception)
def hh(e): return jsonify(error='handled', type=type(e).__name__), 500
R['modes'] = {}
for label, cfg in (('默认', {}), ('TESTING=True', {'TESTING': True}), ('DEBUG=True', {'DEBUG': True})):
    a.config.update({'TESTING': False, 'DEBUG': False, 'PROPAGATE_EXCEPTIONS': None}); a.config.update(cfg)
    try: r = a.test_client().get('/api/items/13'); out = f'{r.status_code} {r.get_json()}'
    except Exception as e: out = f'异常直接抛出:{type(e).__name__}'
    print(f'  {label:<14} → {out}'); R['modes'][label] = out
save('f102', R)
