import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f10'); R = {}
from flask import Flask, Blueprint, abort, jsonify, request
from werkzeug.exceptions import HTTPException, NotFound, Forbidden, BadRequest, InternalServerError
class AppError(Exception): pass
class DbError(AppError): pass
def new(): a = Flask('eh'); a.logger.disabled = True; return a
def hit(a, path, **kw):
    r = a.test_client().get(path, **kw); return r.status_code, r.get_data(as_text=True).strip()[:70].replace('\n', ' ')
print('== 一:按异常类的继承关系匹配:最接近的类优先,与注册先后无关')
a = new()
@a.errorhandler(Exception)
def h_exc(e): return f'Exception 处理器 收到 {type(e).__name__}', 500
@a.errorhandler(AppError)
def h_app(e): return f'AppError 处理器 收到 {type(e).__name__}', 500
@a.get('/db')
def r_db(): raise DbError()
@a.get('/app')
def r_app(): raise AppError()
@a.get('/val')
def r_val(): raise ValueError()
R['mro'] = {p: hit(a, p) for p in ('/db', '/app', '/val')}
for p, nm in (('/db', 'DbError(继承 AppError)'), ('/app', 'AppError'), ('/val', 'ValueError')): print(f'  GET {p:<5} 抛 {nm:<22} → {R["mro"][p][0]} {R["mro"][p][1]}')
print('  (DbError → AppError 处理器,因为 DbError 的 MRO 里 AppError 排在 Exception 前面;反过来先注册 Exception 再注册 AppError 也是这个结果)')
print()
print('== 二:HTTP 异常(abort)会不会被 @errorhandler(Exception) 接住;状态码处理器与 HTTPException 处理器谁优先')
def http_app(*kinds):
    a = new(); a.get('/403')(lambda: abort(403))
    if 'exc' in kinds:
        @a.errorhandler(Exception)
        def h_exc2(e): return f'Exception 处理器 收到 {type(e).__name__}', 500
    if 'http' in kinds:
        @a.errorhandler(HTTPException)
        def h_http(e): return f'HTTPException 处理器 收到 {type(e).__name__}', e.code
    if '403' in kinds:
        @a.errorhandler(403)
        def h_403(e): return f'403 处理器 收到 {type(e).__name__}', 403
    return a
R['http'] = {}
for label, kinds in (('只注册 Exception 处理器', ('exc',)), ('Exception + HTTPException', ('exc', 'http')), ('Exception + HTTPException + 403', ('exc', 'http', '403'))):
    a = http_app(*kinds); R['http'][label] = {p: hit(a, p) for p in ('/403', '/missing')}
    for p, v in R['http'][label].items(): print(f'  {label:<32} GET {p:<9} → {v[0]} {v[1]}')
a = http_app(); R['http']['无处理器'] = {p: hit(a, p) for p in ('/403', '/missing')}
for p, v in R['http']['无处理器'].items(): print(f'  {"没有注册任何处理器":<32} GET {p:<9} → {v[0]} {v[1]}')
a = http_app(); a.test_client().get('/403')
try:
    @a.errorhandler(404)
    def late(e): return 'x'
except AssertionError as e: print('  处理第一个请求之后再注册 @errorhandler → AssertionError:', str(e).split('\n')[0][:150]); R['late'] = str(e).split('\n')[0]
print()
print('== 三:@errorhandler(403) 与 @errorhandler(Forbidden) 是同一个键;后注册的覆盖先注册的')
a = new()
@a.errorhandler(403)
def first(e): return 'first(403)', 403
@a.errorhandler(Forbidden)
def second(e): return 'second(Forbidden)', 403
a.get('/403')(lambda: abort(403)); R['same'] = hit(a, '/403'); print('  先 403 后 Forbidden:', R['same'])
print('  error_handler_spec 的结构:', {k: {c: {t.__name__: f.__name__ for t, f in m.items()} for c, m in v.items()} for k, v in a.error_handler_spec.items()}); R['spec'] = str(a.error_handler_spec)
print()
print('== 四:蓝图里的处理器:蓝图内的路由先找蓝图的处理器;但 404(路由没匹配)不属于任何蓝图,只能走应用级处理器')
a = new(); bp = Blueprint('api', __name__, url_prefix='/api')
@bp.errorhandler(ValueError)
def bp_val(e): return 'blueprint 的 ValueError 处理器', 400
@a.errorhandler(ValueError)
def app_val(e): return '应用的 ValueError 处理器', 400
@bp.errorhandler(404)
def bp_404(e): return 'blueprint 的 404 处理器', 404
@a.errorhandler(404)
def app_404(e): return '应用的 404 处理器', 404
@bp.get('/v')
def bpv(): raise ValueError()
@a.get('/v')
def appv(): raise ValueError()
@bp.get('/abort404')
def bp404(): abort(404)
a.register_blueprint(bp); R['bp'] = {p: hit(a, p) for p in ('/api/v', '/v', '/api/abort404', '/api/nope', '/nope')}
for p, v in R['bp'].items(): print(f'  GET {p:<14} → {v[0]} {v[1]}')
print()
print('== 五:500:没有任何处理器时的默认响应;@errorhandler(500) 收到的是 InternalServerError,原始异常在 original_exception')
def boom(): raise ZeroDivisionError('x/0')
def boom_app(kind=None, testing=False):
    a = new(); a.testing = testing; a.get('/boom')(boom)
    if kind == '500':
        @a.errorhandler(500)
        def h500(e): return f'500 处理器:{type(e).__name__};original_exception = {type(e.original_exception).__name__}: {e.original_exception}', 500
    if kind == 'exc':
        @a.errorhandler(Exception)
        def hall(e): return f'Exception 处理器:{type(e).__name__}', 500
    return a
r = boom_app().test_client().get('/boom'); print('  无处理器:', r.status_code, r.get_data(as_text=True).strip().replace('\n', ' ')[:130]); R['default500'] = [r.status_code, r.get_data(as_text=True)[:130]]
R['h500'] = hit(boom_app('500'), '/boom'); print('  有 @errorhandler(500):', R['h500'])
R['hall'] = hit(boom_app('exc'), '/boom'); print('  有 @errorhandler(Exception):', R['hall'])
for kind, lab in ((None, '没有处理器'), ('500', '有 @errorhandler(500)'), ('exc', '有 @errorhandler(Exception)')):
    try: r = boom_app(kind, True).test_client().get('/boom'); print(f'  TESTING=True 且{lab}:状态 {r.status_code},正文 {r.get_data(as_text=True).strip()[:60]}'); R[f'testing_{kind}'] = [r.status_code, r.get_data(as_text=True)[:60]]
    except ZeroDivisionError as e: print(f'  TESTING=True 且{lab}:异常直接传出 test_client → {type(e).__name__}'); R[f'testing_{kind}'] = 'propagates'
print()
print('== 六:处理器本身出错;处理器返回 JSON;错误页的 Content-Type')
a = new()
@a.errorhandler(404)
def bad_handler(e): raise RuntimeError('处理器自己出错')
r = a.test_client().get('/x'); print('  404 处理器里再抛异常 →', r.status_code, r.get_data(as_text=True).strip().replace('\n', ' ')[:90]); R['handler_err'] = r.status_code
a = new()
@a.errorhandler(HTTPException)
def jsonify_http(e): return jsonify(code=e.code, name=e.name, description=e.description), e.code
r = a.test_client().get('/x'); print('  JSON 处理器:', r.status_code, r.content_type, r.get_data(as_text=True).strip()); R['json'] = [r.status_code, r.content_type, r.get_data(as_text=True).strip()]
r = new().test_client().get('/x'); print('  默认 404 页:', r.status_code, r.content_type, '|', r.get_data(as_text=True).strip().replace('\n', ' ')[:90]); R['default404'] = [r.content_type]
save('f10', R)
