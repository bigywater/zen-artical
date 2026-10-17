import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f5'); R = {}
import flask, threading, timeit
from flask import Flask, request, current_app, g, session, Request
from werkzeug.local import LocalProxy
import inspect
app = Flask('demo5'); app.secret_key = 'k'
print('== 一:request、current_app、g、session 都是 LocalProxy,不是真实对象')
with app.test_request_context('/p?x=1'):
    for nm, o in (('request', request), ('current_app', current_app), ('g', g), ('session', session)): print(f'  {nm:<12} type = {type(o).__name__:<11} 真实对象类型 = {type(o._get_current_object()).__name__}')
    print('  isinstance(request, Request) =', isinstance(request, Request), '| request.__class__ =', request.__class__.__name__, '| type(request) is Request =', type(request) is Request)
    print('  request is request._get_current_object():', request is request._get_current_object(), '| request == request._get_current_object():', request == request._get_current_object())
    print('  repr(request) =', repr(request)); R['one'] = [isinstance(request, Request), type(request) is Request, request is request._get_current_object(), repr(request)]
print('  请求之外 repr(request) =', repr(request)); R['unbound'] = repr(request)
print()
print('== 二:proxy 怎么找到真实对象:LocalProxy 里存着一个 ContextVar,每次访问属性都去取一次')
from flask import globals as G
print('  flask.globals._cv_request:', G._cv_request, '| 类型', type(G._cv_request).__name__)
SL = inspect.getsource(LocalProxy.__init__).split('\n'); i0 = [i for i, l in enumerate(SL) if 'isinstance(local, ContextVar)' in l][0]; L = SL[i0:i0 + 9]
print('  werkzeug.local.LocalProxy.__init__ 里处理 ContextVar 的分支(原样):'); print('\n'.join('    ' + l for l in L)); R['src'] = L
print()
print('== 三:每个线程各自看到自己的请求(同时开 4 个线程,各推一个 URL 不同的请求上下文)')
res = {}; bar = threading.Barrier(4)
def worker(i):
    with app.test_request_context(f'/t{i}'):
        bar.wait(); time.sleep(0.05); res[i] = (request.path, id(request._get_current_object()) % 100000)
th = [threading.Thread(target=worker, args=(i,)) for i in range(4)]; [t.start() for t in th]; [t.join() for t in th]
for i in sorted(res): print(f'  线程 {i}:request.path = {res[i][0]},真实 Request 对象 id = {res[i][1]}')
R['threads'] = {str(k): list(v) for k, v in res.items()}; print('  4 个线程看到的路径互不相同:', len({v[0] for v in res.values()}) == 4, '| 对象 id 互不相同:', len({v[1] for v in res.values()}) == 4)
print()
print('== 四:通过代理访问的开销(100 万次 request.path vs 先取出真实对象再 .path)')
with app.test_request_context('/p'):
    real = request._get_current_object(); n = 1_000_000
    ts_proxy = [timeit.timeit(lambda: request.path, number=n) / n * 1e9 for _ in range(3)]; ts_real = [timeit.timeit(lambda: real.path, number=n) / n * 1e9 for _ in range(3)]
    print(f'  通过代理 request.path:{min(ts_proxy):.0f} ns/次;真实对象 .path:{min(ts_real):.0f} ns/次;约 {min(ts_proxy) / min(ts_real):.1f} 倍'); R['cost'] = [min(ts_proxy), min(ts_real)]
print()
print('== 五:g 的接口:get / pop / setdefault / in / 迭代;缺失属性的报错;换成自定义类')
with app.app_context():
    g.a = 1; print('  g.get("b", "默认") =', g.get('b', '默认'), '| "a" in g =', 'a' in g, '| g.setdefault("c", 3) =', g.setdefault('c', 3), '| g.pop("a") =', g.pop('a'), '| list(g) =', list(g)); R['g'] = list(g)
    try: g.missing
    except AttributeError as e: print('  g.missing → AttributeError:', e); R['g_missing'] = str(e)
    print('  repr(g) =', repr(g._get_current_object())[:80])
class MyG(flask.ctx._AppCtxGlobals):
    def __init__(self): self.created = True
app2 = Flask('demo5b'); app2.app_ctx_globals_class = MyG
with app2.app_context(): print('  自定义 app_ctx_globals_class 后 g.created =', g.created, '| 类型 =', type(g._get_current_object()).__name__); R['custom_g'] = [g.created, type(g._get_current_object()).__name__]
print()
print('== 六:把代理对象传给别的线程:代理本身没有值,必须传真实对象')
out = {}
with app.app_context():
    real_app = current_app._get_current_object()
    def w1(): 
        try: out['传代理'] = current_app.name
        except Exception as e: out['传代理'] = f'{type(e).__name__}: {str(e)[:70]}'
    def w2(): out['传真实对象'] = real_app.name
    for w in (w1, w2): t = threading.Thread(target=w); t.start(); t.join()
for k, v in out.items(): print(f'  {k}: {v}')
R['pass'] = dict(out)
save('f5', R)
