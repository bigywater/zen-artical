import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f8'); R = {}
from flask import Flask, Blueprint, abort, request, jsonify
def make(extra=None):
    a = Flask('hooks'); a.logger.disabled = True; ev = []
    @a.before_request
    def b1(): ev.append('before_1')
    @a.before_request
    def b2():
        ev.append('before_2')
        if request.path == '/short': return 'before 里直接返回'
        if request.path == '/before-boom': raise RuntimeError('before boom')
    @a.after_request
    def a1(r): ev.append('after_1'); return r
    @a.after_request
    def a2(r): ev.append('after_2'); return r
    @a.teardown_request
    def t1(e): ev.append(f'teardown_1({type(e).__name__ if e else None})')
    @a.teardown_request
    def t2(e): ev.append(f'teardown_2({type(e).__name__ if e else None})')
    @a.get('/')
    def ok(): ev.append('view'); return 'ok'
    @a.get('/forbidden')
    def forbidden(): ev.append('view'); abort(403)
    @a.get('/boom')
    def boom(): ev.append('view'); raise ValueError('boom')
    @a.get('/short')
    def short(): ev.append('view'); return 'view'
    @a.get('/before-boom')
    def bb(): ev.append('view'); return 'view'
    if extra: extra(a, ev)
    return a, ev
print('== 一:同一组钩子(2 个 before_request、2 个 after_request、2 个 teardown_request)在不同请求下实际触发的顺序')
src('''
    @app.before_request   def b1 / b2         # b2 在 /short 返回响应,在 /before-boom 抛异常
    @app.after_request    def a1 / a2         # 参数是响应,必须返回响应
    @app.teardown_request def t1 / t2         # 参数是异常或 None
''', '钩子定义(简写)')
app, ev = make(); c = app.test_client(); R['sc'] = {}
for label, path in (('正常 GET /', '/'), ('abort(403)', '/forbidden'), ('视图里 ValueError', '/boom'), ('before 里直接返回响应', '/short'), ('before 里抛异常', '/before-boom'), ('路径不存在(404)', '/nope'), ('静态文件 /static/x', '/static/x.txt')):
    ev.clear(); r = c.get(path); R['sc'][label] = [r.status_code, list(ev)]
    print(f'  {label:<18} → {r.status_code}  ' + ' → '.join(ev))
print()
print('== 二:after_request 忘了 return 会怎样;返回别的东西会怎样')
def bad(a, ev):
    @a.get('/noret')
    def noret(): return 'x'
a1, e1 = make(); a1.after_request_funcs[None].insert(0, lambda r: None)
try:
    r = a1.test_client().get('/'); print('  状态', r.status_code)
except Exception as e: print(f'  最后执行的 after_request 返回 None → test_client 抛出 {type(e).__name__}: {e}'); R['none'] = [type(e).__name__, str(e)]
print('  (after_request_funcs 按注册顺序存放,执行时倒序,所以 insert(0) 的函数最后执行(这里让它返回 None))')
print()
print('== 三:多个钩子的执行顺序(各 3 个):before 按注册顺序;after、teardown 按注册的相反顺序')
a = Flask('order'); ev = []
for i in range(3):
    a.before_request((lambda i: lambda: ev.append(f'before_{i}'))(i)); a.after_request((lambda i: lambda r: (ev.append(f'after_{i}'), r)[1])(i)); a.teardown_request((lambda i: lambda e: ev.append(f'teardown_{i}'))(i))
a.get('/')(lambda: 'ok'); a.test_client().get('/'); print('  ' + ' → '.join(ev)); R['order'] = list(ev)
print()
print('== 四:蓝图里的钩子:blueprint.before_request 只对本蓝图的路由生效;before_app_request 对整个应用生效')
bp = Blueprint('bp', __name__); ev = []; a = Flask('bpapp'); a.logger.disabled = True
@a.before_request
def app_b(): ev.append('app.before_request')
@bp.before_request
def bp_b(): ev.append('bp.before_request')
@bp.before_app_request
def bp_ba(): ev.append('bp.before_app_request')
@bp.after_request
def bp_a(r): ev.append('bp.after_request'); return r
@a.after_request
def app_a(r): ev.append('app.after_request'); return r
@bp.get('/in-bp')
def inbp(): ev.append('view(bp)'); return 'bp'
@a.get('/in-app')
def inapp(): ev.append('view(app)'); return 'app'
a.register_blueprint(bp); c = a.test_client(); R['bp'] = {}
for path in ('/in-bp', '/in-app', '/nope'):
    ev.clear(); r = c.get(path); R['bp'][path] = [r.status_code, list(ev)]; print(f'  GET {path:<8} → {r.status_code}  ' + ' → '.join(ev))
print()
print('== 五:teardown_request 与 after_request 的区别:异常没有被处理时(TESTING=True,异常向外抛),after_request 不执行但 teardown_request 一定执行')
app, ev = make(); app.testing = True; ev.clear()
try: app.test_client().get('/boom')
except ValueError as e: print('  test_client 向上抛出了:', type(e).__name__, e)
print('  ' + ' → '.join(ev)); R['testing'] = list(ev)
save('f8', R)
