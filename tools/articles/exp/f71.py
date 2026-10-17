import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f71'); R = {}
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_login import LoginManager
print('== 一:扩展的两种初始化:构造时传 app,或者先构造再 init_app(app)')
db1 = SQLAlchemy(); print('  SQLAlchemy() 先不带 app 创建:此时还没有绑定任何应用')
a = Flask('a'); a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
try: db1.engine
except RuntimeError as e: print('  init_app 之前访问 db.engine →', 'RuntimeError:', str(e).split('\n')[0][:110]); R['before'] = str(e).split('\n')[0]
db1.init_app(a)
with a.app_context(): print('  init_app 之后,应用上下文里 db.engine =', type(db1.engine).__name__); R['after'] = type(db1.engine).__name__
try:
    with Flask('noctx').app_context(): db1.engine
except Exception as e: print('  用别的(没有 init_app 的)应用的上下文访问 →', type(e).__name__ + ':', str(e).split('\n')[0][:120]); R['other_app'] = f'{type(e).__name__}: {str(e).split(chr(10))[0][:120]}'
print('  app.extensions 里登记了:', sorted(a.extensions)); R['ext'] = sorted(a.extensions)
print()
print('== 二:扩展什么时候读配置?init_app 时读一次,之后改配置不生效(以 SQLAlchemy 为例)')
b = Flask('b'); b.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'; db2 = SQLAlchemy(); db2.init_app(b); b.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///other.db'
with b.app_context(): print('  init_app 之后再把 URI 改成 other.db,引擎实际指向:', str(db2.engine.url)); R['late_cfg'] = str(db2.engine.url)
c = Flask('c')
try: SQLAlchemy().init_app(c)
except Exception as e: print('  init_app 时没有配置 URI →', type(e).__name__ + ':', str(e)[:130]); R['nocfg'] = f'{type(e).__name__}: {str(e)[:130]}'
print()
print('== 三:有的配置在 init_app 时读,有的在用到时才读:Flask-Caching 与 Flask-Login 对比')
d_ = Flask('d'); d_.config['CACHE_TYPE'] = 'SimpleCache'; cache = Cache(); cache.init_app(d_); d_.config['CACHE_TYPE'] = 'NullCache'
with d_.app_context(): cache.set('k', 1); print('  Flask-Caching:init_app 后把 CACHE_TYPE 改成 NullCache,cache.get 仍是', cache.get('k'), '(用的是 init_app 时的 SimpleCache)'); R['cache_late'] = cache.get('k')
e_ = Flask('e'); e_.secret_key = 'k'; lm = LoginManager(); lm.init_app(e_); lm.login_view = 'late_login'; print('  Flask-Login:init_app 之后设置 login_view 仍然有效:', lm.login_view); R['lm_late'] = lm.login_view
print()
print('== 四:一个扩展对象服务多个应用:状态存在各自的 app.extensions 里,不是扩展对象上')
db3 = SQLAlchemy(); x, y = Flask('x'), Flask('y'); x.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'; y.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'; db3.init_app(x); db3.init_app(y)
with x.app_context(): ex = db3.engine
with y.app_context(): ey = db3.engine
print('  同一个 db 对象,在 x、y 两个应用上下文里得到的引擎不同:', ex is not ey); R['multi'] = ex is not ey
print()
print('== 五:应用工厂里 init_app 的位置:先配置,再 init_app,最后注册蓝图;顺序错了会读不到配置')
def create_bad():
    app = Flask('bad'); db = SQLAlchemy(); db.init_app(app); app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'; return app
try: create_bad()
except Exception as e: print('  先 init_app 再设配置 →', type(e).__name__ + ':', str(e)[:110]); R['order_bad'] = f'{type(e).__name__}: {str(e)[:110]}'
def create_good():
    app = Flask('good'); app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'; db = SQLAlchemy(); db.init_app(app); return app
create_good(); print('  先设配置再 init_app → 成功')
print()
print('== 六:用到时才读配置的写法(推荐给自己写的扩展):在方法里用 current_app.config,而不是缓存在 init_app 里')
class LazyExt:
    def init_app(self, app): app.config.setdefault('LAZY_GREETING', 'hello'); app.extensions['lazy'] = self
    def greet(self): return current_app.config['LAZY_GREETING']
class EagerExt:
    def init_app(self, app): self.greeting = app.config.setdefault('EAGER_GREETING', 'hello'); app.extensions['eager'] = self
    def greet(self): return self.greeting
f_ = Flask('f'); lz, eg = LazyExt(), EagerExt(); lz.init_app(f_); eg.init_app(f_); f_.config['LAZY_GREETING'] = '改后(lazy)'; f_.config['EAGER_GREETING'] = '改后(eager)'
with f_.app_context(): print('  init_app 之后改配置:LazyExt.greet() =', lz.greet(), '| EagerExt.greet() =', eg.greet()); R['lazy_eager'] = [lz.greet(), eg.greet()]
g_ = Flask('g'); g_.config['EAGER_GREETING'] = 'g 的值'; g2 = Flask('g2'); g2.config['EAGER_GREETING'] = 'g2 的值'; e2 = EagerExt(); e2.init_app(g_); e2.init_app(g2)
with g_.app_context(): print('  EagerExt 对象被两个应用共用时(把值存在 self 上):g_ 的上下文里 greet() =', e2.greet(), '(被第二次 init_app 覆盖了)'); R['eager_shared'] = e2.greet()
save('f71', R)
