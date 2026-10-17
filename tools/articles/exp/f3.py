import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f3'); R = {}
import flask
from flask import Flask, current_app, g, request, has_app_context, has_request_context, appcontext_pushed, appcontext_popped, request_started, request_finished, got_request_exception
print('== 一:没有应用上下文时访问 current_app / g:报什么错')
R['err'] = {}
for nm, f in (('current_app.name', lambda: current_app.name), ('g.x', lambda: g.x), ('url_for', lambda: flask.url_for('x'))):
    try: f()
    except Exception as e: print(f'  {nm:<18} → {type(e).__name__}: {" ".join(str(e).split())[:260]}'); R['err'][nm] = [type(e).__name__, " ".join(str(e).split())]
print('  has_app_context():', has_app_context(), '| has_request_context():', has_request_context())
print()
print('== 二:with app.app_context():里面 current_app 可用;current_app 是代理,真实对象要 _get_current_object()')
app = Flask('demo')
src('''
    app = Flask("demo")
    with app.app_context():
        print(current_app.name, has_app_context())
        print(current_app is app, current_app._get_current_object() is app, type(current_app).__name__)
    print(has_app_context())
''')
with app.app_context():
    print(' ', current_app.name, has_app_context()); print(' ', current_app is app, current_app._get_current_object() is app, type(current_app).__name__); R['proxy'] = [current_app is app, current_app._get_current_object() is app, type(current_app).__name__]
print(' ', has_app_context())
print()
print('== 三:每个请求有自己的应用上下文,g 不会跨请求;模块级变量会')
app = Flask('demo3'); counter = {'n': 0}
@app.get('/')
def idx():
    g.hits = getattr(g, 'hits', 0) + 1; counter['n'] += 1; return f'g.hits={g.hits} 模块变量={counter["n"]} g 的 id={id(g._get_current_object()) % 100000}'
c = app.test_client(); R['g'] = []
for i in range(3):
    t = c.get('/').get_data(as_text=True); print(' ', t); R['g'].append(t)
print()
print('== 四:一次请求里各个信号与回调的先后顺序(appcontext_pushed / request_started / before_request / 视图 / after_request / request_finished / teardown_request / teardown_appcontext / appcontext_popped)')
app = Flask('demo4'); ev = []
appcontext_pushed.connect(lambda s, **k: ev.append('appcontext_pushed'), app, weak=False); request_started.connect(lambda s, **k: ev.append('request_started'), app, weak=False)
request_finished.connect(lambda s, **k: ev.append('request_finished'), app, weak=False); appcontext_popped.connect(lambda s, **k: ev.append('appcontext_popped'), app, weak=False)
@app.before_request
def br(): ev.append('before_request')
@app.after_request
def ar(r): ev.append('after_request'); return r
@app.teardown_request
def tr(e): ev.append(f'teardown_request(exc={e})')
@app.teardown_appcontext
def ta(e): ev.append(f'teardown_appcontext(exc={e})')
@app.get('/')
def idx4(): ev.append('视图函数'); return 'ok'
app.test_client().get('/'); print('  ' + ' → '.join(ev)); R['order'] = list(ev)
print()
print('== 五:视图抛异常时 teardown 拿到异常;请求上下文会自动带上应用上下文,反过来不会')
app = Flask('demo5'); ev = []; app.logger.disabled = True
@app.teardown_appcontext
def ta5(e): ev.append(f'teardown_appcontext 收到:{type(e).__name__ if e else None}')
@app.get('/boom')
def boom(): raise ValueError('boom')
r = app.test_client().get('/boom'); print(f'  GET /boom → {r.status_code};', ev); R['boom'] = [r.status_code, list(ev)]
with app.test_request_context('/x'):
    print('  test_request_context 内:has_app_context =', has_app_context(), ', has_request_context =', has_request_context(), ', request.path =', request.path)
with app.app_context():
    print('  app_context 内:has_app_context =', has_app_context(), ', has_request_context =', has_request_context())
    try: request.path
    except RuntimeError as e: print('  在应用上下文里访问 request.path →', ' '.join(str(e).split())[:200]); R['req_in_app'] = ' '.join(str(e).split())
print()
print('== 六:嵌套:两个应用的上下文叠在一起,current_app 指向最内层;退出内层后恢复外层')
a1, a2 = Flask('outer'), Flask('inner'); seen = []
with a1.app_context():
    seen.append(current_app.name)
    with a2.app_context(): seen.append(current_app.name)
    seen.append(current_app.name)
print('  ', seen); R['nest'] = seen
print()
print('== 七:命令行里的应用上下文:@app.cli.command() 里不需要自己 push,flask 命令已经推好了')
d = app_ = None
d = __import__('fl').app('f3cli', {'cliapp.py': '''
import click
from flask import Flask, current_app, has_app_context, g
app = Flask("cliapp")
@app.cli.command("hello")
def hello():
    click.echo(f"has_app_context={has_app_context()} current_app.name={current_app.name}")
'''})
r = subprocess.run([str(BIN / 'flask'), '--app', 'cliapp', 'hello'], cwd=d, env=env(d), capture_output=True, text=True); print('  flask --app cliapp hello →', r.stdout.strip() or r.stderr.strip()); R['cli'] = r.stdout.strip()
rc, o = py(d, '''
    from cliapp import app
    r = app.test_cli_runner().invoke(args=["hello"]); print("test_cli_runner:", r.output.strip())
    from flask import has_app_context
    print("手动调用函数(没有 flask 命令):", end=" ")
    try:
        from cliapp import hello; hello.callback()
    except Exception as e: print(type(e).__name__, str(e)[:120])
'''); pr(o, 6); R['cli2'] = o
save('f3', R)
