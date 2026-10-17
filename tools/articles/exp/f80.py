import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f80'); R = {}
EXT = '''
from flask import current_app, g, has_app_context, request, jsonify
import click, threading, time

class FakeConn:
    opened = 0; closed = 0
    def __init__(self, dsn): FakeConn.opened += 1; self.dsn = dsn; self.open = True
    def close(self): FakeConn.closed += 1; self.open = False

class Hello:
    """一个遵守约定的最小扩展:构造不绑定 app、init_app 绑定、状态放 app.extensions、配置有默认值。"""
    def __init__(self, app=None, greeting=None):
        self._greeting = greeting
        if app is not None: self.init_app(app)
    def init_app(self, app):
        app.config.setdefault("HELLO_GREETING", "hello")
        app.config.setdefault("HELLO_DSN", "mem://default")
        if "hello" in app.extensions: raise RuntimeError("Hello 已经在这个应用上初始化过了")
        app.extensions["hello"] = {"inst": self, "greeting": self._greeting or app.config["HELLO_GREETING"]}
        app.teardown_appcontext(self._teardown)
        app.cli.add_command(hello_cmd)
        app.template_filter("shout")(lambda s: s.upper() + "!")
        app.after_request(self._after)
    @property
    def _state(self):
        if not has_app_context(): raise RuntimeError("Hello 需要应用上下文:请在 app.app_context() 里使用")
        try: return current_app.extensions["hello"]
        except KeyError: raise RuntimeError("这个应用没有 init_app(Hello)")
    def greet(self, name): return f"{self._state['greeting']}, {name}"
    @property
    def conn(self):
        c = g.get("_hello_conn")
        if c is None: c = g._hello_conn = FakeConn(current_app.config["HELLO_DSN"])
        return c
    def _teardown(self, exc):
        c = g.pop("_hello_conn", None)
        if c is not None: c.close()
    def _after(self, resp):
        resp.headers["X-Hello"] = self._state["greeting"]; return resp

@click.command("hello")
@click.argument("name")
def hello_cmd(name):
    from flask import current_app
    click.echo(f"{current_app.extensions['hello']['inst'].greet(name)} (cli)")
'''
import_ = lambda: None
d = mkapp('f80', {'hello_ext.py': EXT, 'app.py': '''
import os
from flask import Flask, render_template_string
from hello_ext import Hello, FakeConn
hello = Hello()
def create_app(**cfg):
    a = Flask(__name__); a.config.update(cfg); hello.init_app(a)
    @a.get("/")
    def index(): return hello.greet("world")
    @a.get("/db")
    def db(): return f"conn {hello.conn.dsn} open={hello.conn.open}"
    @a.get("/tpl")
    def tpl(): return render_template_string("{{ 'hey' | shout }}")
    @a.get("/stats")
    def stats(): return f"opened={FakeConn.opened} closed={FakeConn.closed}"
    return a
app = create_app()
'''})
sys.path.insert(0, str(d))
print('== 一:扩展骨架:构造时不绑定 app,init_app 绑定;配置默认值用 setdefault;状态放 app.extensions')
src('''
class Hello:
    def __init__(self, app=None, greeting=None):
        self._greeting = greeting
        if app is not None: self.init_app(app)
    def init_app(self, app):
        app.config.setdefault("HELLO_GREETING", "hello")
        app.extensions["hello"] = {"inst": self, "greeting": self._greeting or app.config["HELLO_GREETING"]}
        app.teardown_appcontext(self._teardown)
        ...''', '核心结构(节选)')
import importlib
import hello_ext, app as appmod
a1 = appmod.create_app(); a2 = appmod.create_app(HELLO_GREETING='你好'); a3 = appmod.create_app()
with a1.app_context(): print('  同一个 hello 对象,应用 1:', appmod.hello.greet('Ann'))
with a2.app_context(): print('  应用 2(HELLO_GREETING=你好):', appmod.hello.greet('Ann'))
print('  配置里被填入的默认值:', {k: v for k, v in a1.config.items() if k.startswith('HELLO')}); R['defaults'] = {k: v for k, v in a1.config.items() if k.startswith('HELLO')}
try: appmod.hello.init_app(a1)
except RuntimeError as e: print('  对同一个应用重复 init_app →', e); R['dup'] = str(e)
try: appmod.hello.greet('x')
except RuntimeError as e: print('  应用上下文之外使用 →', e); R['noctx'] = str(e)
from flask import Flask
bare = Flask('bare')
with bare.app_context():
    try: appmod.hello.greet('x')
    except RuntimeError as e: print('  没 init_app 的应用里使用 →', e); R['noinit'] = str(e)
print()
print('== 二:扩展顺手注册的东西:模板过滤器、after_request 头、CLI 命令、teardown')
c = a1.test_client(); r = c.get('/tpl'); print('  模板过滤器 shout:', r.get_data(as_text=True)); R['filter'] = r.get_data(as_text=True)
r = c.get('/'); print('  after_request 加的头 X-Hello:', r.headers.get('X-Hello'), '| 正文:', r.get_data(as_text=True)); R['hdr'] = r.headers.get('X-Hello')
import subprocess as sp
p = sp.run([str(BIN / 'flask'), '--app', 'app', 'hello', 'Bob'], cwd=d, env=env(d), capture_output=True, text=True); print('  flask hello Bob →', p.stdout.strip(), '(退出码', p.returncode, ')'); R['cli'] = p.stdout.strip()
p = sp.run([str(BIN / 'flask'), '--app', 'app', '--help'], cwd=d, env=env(d), capture_output=True, text=True); cmds = [l.split()[0] for l in p.stdout.split('Commands:')[1].splitlines() if l.startswith('  ')]; print('  flask --help 的 Commands:', cmds); R['help'] = cmds
print()
print('== 三:每个请求一个连接:懒创建、请求结束时在 teardown 里关闭')
from hello_ext import FakeConn
FakeConn.opened = FakeConn.closed = 0; c = a3.test_client()
for p_ in ('/', '/', '/db', '/db', '/db'): c.get(p_)
print(f'  5 个请求(2 个不用连接、3 个用):opened={FakeConn.opened} closed={FakeConn.closed}'); R['conn'] = [FakeConn.opened, FakeConn.closed]
FakeConn.opened = FakeConn.closed = 0
a4 = appmod.create_app(); a4.logger.disabled = True
@a4.get('/boom')
def boom4(): appmod.hello.conn; raise ValueError('x')
a4.config['PROPAGATE_EXCEPTIONS'] = False; r = a4.test_client().get('/boom'); print(f'  视图抛异常(HTTP {r.status_code})之后:opened={FakeConn.opened} closed={FakeConn.closed}(teardown 照样执行)'); R['conn_err'] = [r.status_code, FakeConn.opened, FakeConn.closed]
print()
print('== 四:状态放哪里:放在扩展对象上(实例属性)会被并发请求互相覆盖;放在 g(应用上下文)里不会')
APP2 = '''
import time, threading
from flask import Flask, g, request
app = Flask(__name__)
class Bad:
    def begin(self, who): self.current = who
    def whoami(self): return self.current
class Good:
    def begin(self, who): g.current = who
    def whoami(self): return g.current
bad, good = Bad(), Good()
@app.get("/<kind>/<who>")
def v(kind, who):
    ext = bad if kind == "bad" else good
    ext.begin(who); time.sleep(0.2); return ext.whoami()
'''
d2 = mkapp('f80b', {'app.py': APP2})
with Server(d2, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '16', 'app:app']) as s:
    for kind in ('bad', 'good'):
        res = {}
        def one(i): res[i] = s.get(f'/{kind}/u{i}')[2].decode()
        ths = [threading.Thread(target=one, args=(i,)) for i in range(8)]; [t.start() for t in ths]; [t.join() for t in ths]
        wrong = [i for i in range(8) if res[i] != f'u{i}']
        print(f'  {kind:<4} 8 个并发请求(各睡 0.2 秒再读自己写的值):读到别人的值的请求 {len(wrong)} 个'); R.setdefault('conc', {})[kind] = len(wrong)
print()
print('== 五:配置优先级:扩展默认值 < app.config < 构造参数(自己约定的)')
a5 = Flask('p5'); a5.config['HELLO_GREETING'] = 'cfg'
h = hello_ext.Hello(greeting='ctor'); h.init_app(a5)
with a5.app_context(): print('  构造参数 greeting="ctor" + HELLO_GREETING="cfg" →', h.greet('x')); R['prio1'] = h.greet('x')
a6 = Flask('p6'); a6.config['HELLO_GREETING'] = 'cfg'; h2 = hello_ext.Hello(); h2.init_app(a6)
with a6.app_context(): print('  只有 HELLO_GREETING="cfg" →', h2.greet('x')); R['prio2'] = h2.greet('x')
a7 = Flask('p7'); h3 = hello_ext.Hello(); h3.init_app(a7)
with a7.app_context(): print('  都没设 →', h3.greet('x')); R['prio3'] = h3.greet('x')
print()
print('== 六:测试一个扩展:用工厂给每个用例一个全新的应用,断言 app.extensions 与行为')
res = []
for i in range(3):
    a = appmod.create_app(HELLO_GREETING=f'g{i}'); res.append(a.test_client().get('/').get_data(as_text=True))
print('  3 个互相独立的应用的响应:', res); R['iso'] = res
print('  FakeConn 是类属性计数器——共享的状态会让测试互相污染:各用例开始前要手动清零 →', end=' '); FakeConn.opened = 0; print('opened =', FakeConn.opened)
save('f80', R)
