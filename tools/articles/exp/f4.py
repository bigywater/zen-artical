import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f4'); R = {}
import flask, threading
from flask import Flask, request, session, has_app_context, has_request_context, copy_current_request_context, current_app
print('== 一:没有请求上下文时访问 request / session')
R['err'] = {}
for nm, f in (('request.path', lambda: request.path), ('session', lambda: session.get('a'))):
    try: f()
    except Exception as e: print(f'  {nm:<14} → {type(e).__name__}: {" ".join(str(e).split())[:260]}'); R['err'][nm] = " ".join(str(e).split())
print()
print('== 二:test_request_context 用 WSGI environ 构造一个请求(不经过网络);request 上能读到什么')
app = Flask('demo')
src('''
    with app.test_request_context('/a/b?x=1&y=2', method='POST', data={'k': 'v'}, headers={'X-T': '1'}):
        print(request.method, request.path, dict(request.args), dict(request.form), request.headers['X-T'])
        print([k for k in request.environ if k.isupper()][:8], len(request.environ))
''')
with app.test_request_context('/a/b?x=1&y=2', method='POST', data={'k': 'v'}, headers={'X-T': '1'}):
    print(' ', request.method, request.path, dict(request.args), dict(request.form), request.headers['X-T'])
    ks = [k for k in request.environ if k.isupper()]; print('  environ 里的大写键:', ks); print('  environ 里 wsgi.* 键:', [k for k in request.environ if k.startswith('wsgi.')]); R['environ'] = [ks, [k for k in request.environ if k.startswith('wsgi.')]]
print()
print('== 三:push 时发生了什么:自动推应用上下文、打开会话、做 URL 匹配')
app = Flask('demo3'); app.secret_key = 'k'
@app.get('/user/<int:uid>')
def user(uid): return str(uid)
ctx = app.test_request_context('/user/42')
print('  push 之前 has_app_context / has_request_context:', has_app_context(), has_request_context(), '| ctx.url_adapter 类型:', type(ctx.url_adapter).__name__)
try: ctx.session
except AssertionError as e: print('  push 之前读 ctx.session → AssertionError:', e); R['pre_session'] = str(e)
ctx.push(); print('  push 之后:', has_app_context(), has_request_context(), '| request.url_rule =', request.url_rule, '| view_args =', request.view_args, '| session 类型 =', type(session._get_current_object()).__name__)
R['push'] = [str(request.url_rule), dict(request.view_args), type(session._get_current_object()).__name__]
ctx.pop(); print('  pop 之后:', has_app_context(), has_request_context())
print()
print('== 四:路由失败(404)不是在 push 时抛出,而是在分发时')
with app.test_request_context('/nope') as ctx:
    print('  push 成功;request.url_rule =', request.url_rule, '| routing_exception =', repr(request.routing_exception)); R['rexc'] = repr(request.routing_exception)
    try: app.dispatch_request()
    except Exception as e: print('  dispatch_request() 才抛出:', type(e).__name__, '-', str(e)[:80]); R['dispatch'] = [type(e).__name__, str(e)]
print()
print('== 五:没有 SECRET_KEY 时 session 是 NullSession:读可以,写报错')
app = Flask('demo5')
with app.test_request_context('/'):
    print('  session 类型:', type(session._get_current_object()).__name__, '| session.get("a") =', session.get('a'))
    try: session['a'] = 1
    except RuntimeError as e: print('  写入 →', str(e)[:200]); R['nullsession'] = [type(session._get_current_object()).__name__, str(e)]
app.secret_key = 'k'
with app.test_request_context('/'):
    session['a'] = 1; print('  配了 SECRET_KEY 后:', type(session._get_current_object()).__name__, dict(session))
print()
print('== 六:新线程里没有请求上下文;copy_current_request_context 把当前请求上下文复制进去')
app = Flask('demo6'); out = {}
@app.get('/')
def idx():
    def worker(tag, fn): 
        try: out[tag] = fn()
        except Exception as e: out[tag] = f'{type(e).__name__}: {str(e)[:60]}'
    t1 = threading.Thread(target=worker, args=('裸线程', lambda: request.path))
    @copy_current_request_context
    def with_ctx(): return request.path + ' (线程里读到)'
    t2 = threading.Thread(target=worker, args=('copy_current_request_context', with_ctx))
    t1.start(); t2.start(); t1.join(); t2.join(); return 'ok'
app.test_client().get('/'); [print(f'  {k}: {v}') for k, v in out.items()]; R['thread'] = dict(out)
print()
print('== 七:with client: 让请求上下文在响应之后继续保留(测试里检查 request / session 常用)')
app = Flask('demo7'); app.secret_key = 'k'
@app.get('/set')
def setv(): session['u'] = 'ann'; return 'ok'
with app.test_client() as c:
    c.get('/set?x=1'); print('  响应返回之后仍可访问:request.path =', request.path, '| request.args =', dict(request.args), '| session =', dict(session)); R['preserve'] = [request.path, dict(request.args), dict(session)]
print('  with 块之后 has_request_context =', has_request_context())
print()
print('== 八:flask.globals 里的真身:两个 ContextVar')
from flask import globals as G
print('  _cv_app =', G._cv_app, '| _cv_request =', G._cv_request); print('  请求之外 _cv_request.get(None) =', G._cv_request.get(None))
with Flask('x').test_request_context('/'):
    rc_ = G._cv_request.get(); print('  请求内 _cv_request.get() 的类型:', type(rc_).__module__ + '.' + type(rc_).__name__, '| ctx.app.name =', rc_.app.name, '| ctx.request 类型:', type(rc_.request).__name__)
    R['cv'] = [type(rc_).__name__, type(rc_.request).__name__]
save('f4', R)
