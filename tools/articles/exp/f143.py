import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f143'); R = {}
import threading, inspect, contextvars, http.client as hc
from flask import Flask, request, g, current_app, has_request_context, has_app_context, copy_current_request_context
import werkzeug.local as wl
app = Flask('t'); app.logger.disabled = True
print('== 一:request、g、current_app 是什么对象')
with app.test_request_context('/x?a=1'):
    print('  type(request) =', type(request).__name__, '| 真实对象 =', type(request._get_current_object()).__name__); print('  type(g) =', type(g).__name__, '| 真实对象 =', type(g._get_current_object()).__name__); print('  type(current_app) =', type(current_app).__name__, '| 真实对象 =', type(current_app._get_current_object()).__name__)
    R['types'] = [type(request).__name__, type(request._get_current_object()).__name__, type(g._get_current_object()).__name__]
print('  Werkzeug Local 的存储:', type(wl.Local().__dict__.get('_storage', None)).__name__ if False else '', end='')
src = inspect.getsource(wl.Local); print('Local 的源码里用到了 ContextVar:', 'ContextVar' in src, '| 用到了 threading.local:', 'threading.local' in src); R['local_src'] = ['ContextVar' in src, 'threading.local' in src]
print()
print('== 二:多个线程各推入自己的请求上下文,互不影响;上下文外访问 request 的报错')
res = {}
def t(name, path):
    with app.test_request_context(path): time.sleep(0.2); res[name] = request.path
ths = [threading.Thread(target=t, args=(n, p)) for n, p in (('A', '/a'), ('B', '/b'), ('C', '/c'))]; [x.start() for x in ths]; [x.join() for x in ths]; print('  三个线程各自读到:', res); R['threads'] = res
try: request.path
except RuntimeError as e: print('  上下文外访问 request.path →', str(e).splitlines()[0][:100]); R['outside'] = str(e).splitlines()[0][:100]
print()
print('== 三:把 request 带进新线程:直接用 vs copy_current_request_context')
out = {}
with app.test_request_context('/parent'):
    def plain():
        try: out['plain'] = request.path
        except RuntimeError as e: out['plain'] = 'RuntimeError: ' + str(e).splitlines()[0][:60]
    @copy_current_request_context
    def copied(): out['copied'] = request.path
    t1 = threading.Thread(target=plain); t2 = threading.Thread(target=copied); t1.start(); t2.start(); t1.join(); t2.join()
print('  新线程里直接读 request.path →', out['plain']); print('  用 copy_current_request_context 包装后 →', out['copied']); R['spawn'] = [out['plain'], out['copied']]
print()
print('== 四:g 属于应用上下文,不是线程:嵌套推入两个应用上下文,各有自己的 g')
with app.app_context():
    g.v = 'outer'
    with app.app_context(): g.v = 'inner'; print('  内层 g.v =', g.v)
    print('  回到外层 g.v =', g.v); R['g_nested'] = g.v
with app.test_request_context('/'):
    g.in_request = 1; print('  请求上下文里的 g 就是它所属应用上下文的 g:', has_app_context(), g.get('in_request'))
print()
print('== 五:模块级全局变量是所有线程共享的:并发请求里「读、算、写」会丢更新')
APP = '''
import threading, time
from flask import Flask, jsonify
app = Flask(__name__)
COUNT = {"n": 0}; LOCKED = {"n": 0}; LOCK = threading.Lock()
@app.post("/inc")
def inc():
    v = COUNT["n"]; time.sleep(0.001); COUNT["n"] = v + 1; return "ok"
@app.post("/inc-lock")
def inc_lock():
    with LOCK:
        v = LOCKED["n"]; time.sleep(0.001); LOCKED["n"] = v + 1
    return "ok"
@app.get("/counts")
def counts(): return jsonify(unlocked=COUNT["n"], locked=LOCKED["n"])
'''
d = mkapp('f143', {'app.py': APP})
def burst(port, path, n):
    def one(): c = hc.HTTPConnection('127.0.0.1', port, timeout=30); c.request('POST', path); c.getresponse().read(); c.close()
    ths = [threading.Thread(target=one) for _ in range(n)]; [t.start() for t in ths]; [t.join() for t in ths]
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '16', '-w', '1', 'app:app']) as s:
    time.sleep(0.8); burst(s.port, '/inc', 100); burst(s.port, '/inc-lock', 100); j = json.loads(s.get('/counts')[2]); print(f'  100 次并发 POST:不加锁的计数 = {j["unlocked"]}(期望 100),加锁的计数 = {j["locked"]}'); R['race'] = j
save('f143', R)
