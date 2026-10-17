import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f69'); R = {}
d = mkapp('f69', {'config.py': '''
import os
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = False
    PAGE_SIZE = 20
class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = Config.SECRET_KEY or "dev-only-secret"
class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    @classmethod
    def validate(cls):
        missing = [k for k in ("SECRET_KEY",) if not getattr(cls, k)]
        if missing: raise RuntimeError(f"生产配置缺少: {missing}")
CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}
''', 'app.py': '''
import os
from flask import Flask
from config import CONFIGS
def create_app(name=None):
    name = name or os.environ.get("APP_ENV", "development")
    app = Flask(__name__)
    cfg = CONFIGS[name]
    if hasattr(cfg, "validate"): cfg.validate()
    app.config.from_object(cfg)
    app.config["ENV_NAME"] = name
    @app.get("/cfg")
    def cfg_view(): return {k: app.config.get(k) for k in ("ENV_NAME", "DEBUG", "TESTING", "SECRET_KEY", "SESSION_COOKIE_SECURE", "PAGE_SIZE", "SQLALCHEMY_DATABASE_URI")}
    @app.get("/boom")
    def boom(): raise ValueError("boom")
    @app.get("/set")
    def set_(): 
        from flask import session; session["x"] = 1; return "ok"
    return app
'''})
sys.path.insert(0, str(d)); os.chdir(d)
from app import create_app
print('== 一:三套配置(类继承)选出来后的实际值')
os.environ.pop('SECRET_KEY', None)
R['cfgs'] = {}
for n in ('development', 'testing'):
    a = create_app(n); R['cfgs'][n] = a.test_client().get('/cfg').get_json(); print(f'  {n:<12}', R['cfgs'][n])
os.environ['SECRET_KEY'] = 'prod-secret-from-env'; import importlib, config; importlib.reload(config); import app as app_mod; importlib.reload(app_mod)
a = app_mod.create_app('production'); R['cfgs']['production'] = a.test_client().get('/cfg').get_json(); print('  production  ', R['cfgs']['production'])
print()
print('== 二:生产配置缺少关键项时启动就失败(fail fast),不要等到第一个请求')
os.environ.pop('SECRET_KEY'); importlib.reload(config); importlib.reload(app_mod)
try: app_mod.create_app('production')
except RuntimeError as e: print('  没有 SECRET_KEY 的 production →', type(e).__name__ + ':', e); R['failfast'] = str(e)
a = app_mod.create_app('development'); print('  development 在没有环境变量时用 dev-only-secret:', a.config['SECRET_KEY']); R['dev_secret'] = a.config['SECRET_KEY']
print('  没有 SECRET_KEY 也不报错的默认行为(没有 validate):', end=' ')
from flask import Flask; b = Flask('nosk'); b.add_url_rule('/set', 'set', lambda: (__import__('flask').session.__setitem__('x', 1), 'ok')[1]); b.testing = False; b.logger.disabled = True
r = b.test_client().get('/set'); print('访问写 session 的视图 →', r.status_code, '(没有 SECRET_KEY 时写 session 抛 RuntimeError,在生产里就是 500)'); R['nosk'] = r.status_code
print()
print('== 三:TESTING=True 带来的变化:异常会传出来(而不是 500 页);同一个 /boom 在两种配置下的行为')
os.environ['SECRET_KEY'] = 'x'; importlib.reload(config); importlib.reload(app_mod)
for n in ('production', 'testing'):
    a = app_mod.create_app(n); a.logger.disabled = True
    try: r = a.test_client().get('/boom'); print(f'  {n:<11} GET /boom → {r.status_code}'); R.setdefault('boom', {})[n] = r.status_code
    except ValueError as e: print(f'  {n:<11} GET /boom → 异常传出 ValueError({e})'); R.setdefault('boom', {})[n] = 'ValueError 传出'
print('  app.testing 属性与 config["TESTING"] 是同一个:', create_app('testing').testing, create_app('testing').config['TESTING'])
print()
print('== 四:会话 cookie 的 Secure 标志随配置变化(只在 HTTPS 下才会被浏览器带回)')
for n in ('development', 'production'):
    a = app_mod.create_app(n); r = a.test_client().get('/set', base_url='https://localhost'); sc = r.headers.get('Set-Cookie', ''); R.setdefault('secure', {})[n] = 'Secure' in sc; print(f'  {n:<12} Set-Cookie 带 Secure: {"Secure" in sc} | {sc[:70]}')
print()
print('== 五:用环境变量选择配置(APP_ENV)而不是改代码;flask 命令与 gunicorn 里的写法')
for env_name in ('development', 'production'):
    os.environ['SECRET_KEY'] = 's'
    port = free_port()
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:create_app()'], port=port, APP_ENV=env_name, SECRET_KEY='s') as s:
        st, h, b, dt = s.get('/cfg'); j = __import__('json').loads(b); R.setdefault('gun', {})[env_name] = [j['ENV_NAME'], j['DEBUG'], j['SESSION_COOKIE_SECURE']]; print(f'  APP_ENV={env_name:<12} gunicorn "app:create_app()" → ENV_NAME={j["ENV_NAME"]} DEBUG={j["DEBUG"]} SESSION_COOKIE_SECURE={j["SESSION_COOKIE_SECURE"]}')
port = free_port()
with Server(d, ['flask', '--app', 'app:create_app("testing")', 'run', '--port', str(port)], port=port) as s:
    time.sleep(0.4); st, h, b, dt = s.get('/cfg'); j = __import__('json').loads(b); print(f'  flask --app \'app:create_app("testing")\' run → ENV_NAME={j["ENV_NAME"]} TESTING={j["TESTING"]}'); R['flask_arg'] = [j['ENV_NAME'], j['TESTING']]
print()
print('== 六:常见错误:在生产环境留着 DEBUG=True——用启动检查拦住')
class BadProd: DEBUG = True; SECRET_KEY = 'x'
def check(cfg):
    if cfg.get('DEBUG'): raise RuntimeError('生产环境不允许 DEBUG=True')
a = Flask('bad'); a.config.from_object(BadProd)
try: check(a.config)
except RuntimeError as e: print('  检查结果:', e); R['check'] = str(e)
save('f69', R)
