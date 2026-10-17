import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f14'); R = {}
import flask, werkzeug, jinja2, itsdangerous, click, markupsafe, importlib.metadata as md
from flask import Flask
print('== 一:Flask 的依赖:Flask 3.1.3 在安装时要求哪些包')
req = md.requires('flask'); core = [r for r in req if 'extra' not in r]; print('  Requires-Dist(不含可选的 extra):'); [print('    ' + r) for r in core]; R['requires'] = core
print('  本机实际安装的版本:', {n: md.version(n) for n in ('flask', 'werkzeug', 'jinja2', 'itsdangerous', 'click', 'markupsafe', 'blinker')}); R['versions'] = {n: md.version(n) for n in ('flask', 'werkzeug', 'jinja2', 'itsdangerous', 'click', 'markupsafe', 'blinker')}
print()
print('== 二:Flask 里哪些类直接继承或使用 Werkzeug(用 __mro__ 与 __module__ 看)')
rows = [('Flask.request_class', flask.Flask.request_class), ('Flask.response_class', flask.Flask.response_class), ('Flask.url_map_class', flask.Flask.url_map_class), ('Flask.url_rule_class', flask.Flask.url_rule_class)]
R['mro'] = {}
for nm, c in rows:
    chain = [f'{k.__module__}.{k.__name__}' for k in c.__mro__ if k is not object][:4]; R['mro'][nm] = chain; print(f'  {nm:<22} {" → ".join(chain)}')
app = Flask('x')
print('  应用上的对象来自:', {nm: type(o).__module__ + '.' + type(o).__name__ for nm, o in (('app.url_map', app.url_map), ('app.jinja_env', app.jinja_env), ('app.config', app.config), ('app.session_interface', app.session_interface), ('app.json', app.json), ('app.aborter', app.aborter))})
R['objs'] = {nm: type(o).__module__ + '.' + type(o).__name__ for nm, o in (('app.url_map', app.url_map), ('app.jinja_env', app.jinja_env), ('app.config', app.config), ('app.session_interface', app.session_interface), ('app.json', app.json), ('app.aborter', app.aborter))}
print()
print('== 三:只用 Werkzeug(不用 Flask)写一个 WSGI 应用:路由、Request、Response、异常、测试客户端都有')
SRC = '''
    from werkzeug.wrappers import Request, Response
    from werkzeug.routing import Map, Rule
    from werkzeug.exceptions import HTTPException
    url_map = Map([Rule("/hello/<name>", endpoint="hello"), Rule("/", endpoint="index")])
    @Request.application
    def application(request):
        adapter = url_map.bind_to_environ(request.environ)
        try:
            endpoint, args = adapter.match()
            return Response(f"{endpoint}: {args or ''} q={request.args.get('q')}")
        except HTTPException as e:
            return e
'''
src(SRC, '纯 Werkzeug 应用')
ns = {}; exec(textwrap.dedent(SRC), ns)
from werkzeug.test import Client
wc = Client(ns['application'])
for p in ('/', '/hello/ann?q=1', '/nope'): r = wc.get(p); print(f'  GET {p:<16} → {r.status} | {r.get_data(as_text=True).strip()[:60]}')
R['wz'] = {p: [wc.get(p).status, wc.get(p).get_data(as_text=True)[:50]] for p in ('/', '/hello/ann?q=1', '/nope')}
print()
print('== 四:Flask 在 Werkzeug 之上多了什么:同样的 /hello/<name> 路由,Flask 版 vs 纯 Werkzeug 版每个请求的耗时(test client,各 5000 次取最小)')
import timeit
fa = Flask('cmp'); fa.get('/hello/<name>')(lambda name: f'hello: {name}')
fc = fa.test_client(); wcc = Client(ns['application']); fc.get('/hello/ann'); wcc.get('/hello/ann')
tf = min(timeit.timeit(lambda: fc.get('/hello/ann'), number=5000) / 5000 * 1e6 for _ in range(3)); tw = min(timeit.timeit(lambda: wcc.get('/hello/ann'), number=5000) / 5000 * 1e6 for _ in range(3))
print(f'  纯 Werkzeug {tw:.1f} µs/请求;Flask {tf:.1f} µs/请求;Flask 多出 {tf - tw:.1f} µs(约 {tf / tw:.2f} 倍)——多出来的是上下文推入弹出、会话、钩子、响应转换等'); R['cost'] = [tw, tf]
print('  Flask 里有、纯 Werkzeug 里没有的功能(从属性存在性验证):')
ws = {'config': hasattr(wc.application, 'config'), 'session': False, 'before_request': False}
print(f'    app.config / 钩子 / 蓝图 / 模板渲染 / session:Flask 对象有 {all(hasattr(fa, n) for n in ("config", "before_request", "register_blueprint", "jinja_env", "session_interface"))};纯 Werkzeug 函数有 {hasattr(ns["application"], "config")}')
save('f14', R)
