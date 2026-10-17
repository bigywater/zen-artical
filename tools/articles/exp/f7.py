import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f7'); R = {}
import inspect, timeit
import flask
from flask import Flask, request, session, g
app = Flask('life'); app.secret_key = 'k'
@app.before_request
def my_before(): session['seen'] = 1
@app.after_request
def my_after(r): r.headers['X-After'] = '1'; return r
@app.teardown_request
def my_teardown(e): pass
@app.get('/')
def index(): return 'ok'
print('== 一:一次 GET / 经过的 Flask 内部函数(用 sys.setprofile 记录,缩进 = 调用深度,只列出重要的函数;最后一列是自己写的钩子)')
KEEP = {'wsgi_app', 'request_context', 'push', 'match_request', 'open_session', 'full_dispatch_request', 'preprocess_request', 'my_before', 'dispatch_request', 'index', 'finalize_request', 'make_response', 'process_response', 'my_after', 'save_session', 'do_teardown_request', 'my_teardown', 'do_teardown_appcontext', 'pop', 'handle_user_exception', 'handle_exception', 'handle_http_exception', 'should_set_cookie', 'ensure_sync', 'url_adapter', 'create_url_adapter', 'app_context', 'make_default_options_response'}
ev = []; depth = [0]
def prof(frame, event, arg):
    n = frame.f_code.co_name; f = frame.f_code.co_filename
    if n in KEEP and ('/flask/' in f or f.endswith('f7.py')):
        if event == 'call': ev.append((depth[0], n)); depth[0] += 1
        elif event == 'return': depth[0] -= 1
c = app.test_client(); c.get('/'); ev.clear(); depth[0] = 0
sys.setprofile(prof); r = c.get('/'); sys.setprofile(None)
base = min(d for d, n in ev)
# 只保留 wsgi_app 之内的部分
i0 = [i for i, (d, n) in enumerate(ev) if n == 'wsgi_app'][0]; seq = ev[i0:]; b0 = seq[0][0]
lines = [f'{"  " * (d - b0)}{n}' for d, n in seq]
print('\n'.join('    ' + l for l in lines)); R['calls'] = lines
print('  响应:', r.status, '| X-After =', r.headers.get('X-After'), '| Set-Cookie 存在:', 'Set-Cookie' in r.headers)
print()
print('== 二:Flask.__call__ 与 wsgi_app:WSGI 入口的真实代码(取自本机安装的 Flask 3.1.3)')
s1 = inspect.getsource(Flask.__call__).split('\n'); s2 = inspect.getsource(Flask.wsgi_app).split('\n')
i1 = [i for i, l in enumerate(s1) if 'return' in l][0]; i2 = [i for i, l in enumerate(s2) if 'ctx = self.request_context(environ)' in l][0]
code = ['def __call__(self, environ, start_response):', s1[i1], '', 'def wsgi_app(self, environ, start_response):'] + [l[4:] if l.startswith('    ') else l for l in s2[i2:] if l.strip()]
print('\n'.join('    ' + l for l in code[:26])); R['wsgi_src'] = code[:26]
print()
print('== 三:钩子的成本:用 test_client 每组请求 3000 次(3 组取最小),0 / 10 / 100 个空的 before_request 钩子')
R['hooks'] = {}
print(f'  {"before_request 个数":>20} {"每个请求(µs)":>14}')
for nh in (0, 10, 100):
    a = Flask('h'); a.get('/')(lambda: 'ok')
    for _ in range(nh): a.before_request(lambda: None)
    cc = a.test_client(); cc.get('/'); ts = [timeit.timeit(lambda: cc.get('/'), number=3000) / 3000 * 1e6 for _ in range(3)]; R['hooks'][nh] = min(ts); print(f'  {nh:>20} {min(ts):>14.1f}')
print('  每增加 1 个空钩子约 %.2f µs' % ((R['hooks'][100] - R['hooks'][0]) / 100))
R['per_hook'] = (R['hooks'][100] - R['hooks'][0]) / 100
save('f7', R)
