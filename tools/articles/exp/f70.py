import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f70'); R = {}
import timeit
d = mkapp('f70', {
 'bad/__init__.py': '', 'bad/app.py': 'from flask import Flask\nfrom bad import views\napp = Flask(__name__)\napp.config["NAME"] = "全局唯一"\n', 'bad/views.py': 'from bad.app import app\n@app.get("/")\ndef idx(): return "hi"\n', 'bad2/__init__.py': '', 'bad2/app.py': 'from flask import Flask\napp = Flask(__name__)\napp.config["NAME"] = "全局唯一"\nfrom bad2 import views  # 放在文件末尾,绕开循环导入\n', 'bad2/views.py': 'from bad2.app import app\n@app.get("/")\ndef idx(): return "hi"\n',
 'good/__init__.py': 'from flask import Flask\nfrom good.extensions import db_like\ndef create_app(config=None):\n    app = Flask(__name__)\n    app.config["NAME"] = "default"\n    app.config.update(config or {})\n    db_like.init_app(app)\n    from good.views import bp\n    app.register_blueprint(bp)\n    return app\n',
 'good/extensions.py': 'class DbLike:\n    def __init__(self): self.inited_for = []\n    def init_app(self, app):\n        self.inited_for.append(app.config["NAME"]); app.extensions["db_like"] = {"name": app.config["NAME"]}\ndb_like = DbLike()\n',
 'good/views.py': 'from flask import Blueprint, current_app\nfrom good.extensions import db_like\nbp = Blueprint("main", __name__)\n@bp.get("/")\ndef idx(): return {"name": current_app.config["NAME"], "ext": current_app.extensions["db_like"]}\n',
 'mod_app.py': 'from flask import Flask\napp = Flask(__name__)\n@app.get("/")\ndef idx(): return "module app"\ndef make_app(): return Flask("made")\n',
})
sys.path.insert(0, str(d)); os.chdir(d)
print('== 一:没有工厂:模块级的 app 在导入时就创建;视图模块要反过来导入 app(循环导入的温床),配置只能是全局唯一的')
try: import bad.app
except ImportError as e: print('  视图模块在顶部写 from bad.app import app,应用模块又在顶部 from bad import views →', type(e).__name__ + ':', str(e).split(' (')[0]); R['circular'] = str(e).split(' (')[0]
import bad2.app as bapp
print('  常见的绕法:把 from bad2 import views 放到 app.py 的末尾。导入 bad2.app 时路由已注册:', [str(r) for r in bapp.app.url_map.iter_rules() if r.endpoint != 'static']); R['bad_rules'] = [str(r) for r in bapp.app.url_map.iter_rules() if r.endpoint != 'static']
print('  整个进程里只有一个 app 实例,config["NAME"] =', bapp.app.config['NAME'], '| 再导入一次得到的是同一个对象:', __import__('importlib').import_module('bad2.app').app is bapp.app, '(想要两套不同配置的实例:做不到)'); R['bad_same'] = True
print()
print('== 二:用工厂创建多个相互隔离的实例(测试里每个用例一个全新的应用)')
from good import create_app
from good.extensions import db_like
a1 = create_app({'NAME': 'app-one'}); a2 = create_app({'NAME': 'app-two', 'EXTRA': 1}); a3 = create_app()
print('  三个实例:', [a.config['NAME'] for a in (a1, a2, a3)], '| 互不相同:', len({id(a1), id(a2), id(a3)}) == 3); R['names'] = [a.config['NAME'] for a in (a1, a2, a3)]
print('  各自的响应:', [a.test_client().get('/').get_json() for a in (a1, a2)]); R['resp'] = [a.test_client().get('/').get_json() for a in (a1, a2)]
print('  EXTRA 只在 a2 的配置里:', ['EXTRA' in a.config for a in (a1, a2, a3)]); R['extra'] = ['EXTRA' in a.config for a in (a1, a2, a3)]
print('  各自的路由表独立:', [len(list(a.url_map.iter_rules())) for a in (a1, a2, a3)])
print()
print('== 三:扩展对象在模块级创建一次(db_like = DbLike()),在工厂里 init_app(app) 绑定到具体的应用')
print('  同一个 db_like 对象先后被绑定到的应用:', db_like.inited_for); R['inited'] = db_like.inited_for
print('  每个应用自己的 extensions 字典:', [a.extensions['db_like'] for a in (a1, a2, a3)])
print()
print('== 四:视图里用 current_app 而不是导入 app(工厂模式里没有全局 app 可导入)')
print('  views.py 里 import 了 app 吗?', 'bad.app' in open(d / 'good' / 'views.py').read(), '| 用 current_app:', 'current_app' in open(d / 'good' / 'views.py').read())
try:
    from good.views import bp as _; from flask import current_app; current_app.config
except RuntimeError as e: print('  在应用上下文之外访问 current_app →', 'RuntimeError:', str(e).split('\n')[0]); R['no_ctx'] = str(e).split('\n')[0]
with a2.app_context(): print('  with a2.app_context(): current_app.config["NAME"] =', current_app.config['NAME']); R['ctx'] = current_app.config['NAME']
print()
print('== 五:flask 命令与 gunicorn 怎么找到工厂')
for label, args in (('--app good(自动发现 create_app)', ['--app', 'good', 'routes']), ('--app "good:create_app()"', ['--app', 'good:create_app()', 'routes']), ('--app "good:create_app({\'NAME\': \'cli\'})"', ['--app', "good:create_app({'NAME': 'cli'})", 'routes']), ('--app mod_app(模块里有 app 变量)', ['--app', 'mod_app', 'routes']), ('--app mod_app:make_app', ['--app', 'mod_app:make_app', 'routes']), ('--app nope', ['--app', 'nope', 'routes'])):
    r = subprocess.run([str(BIN / 'flask'), *args], cwd=d, env=env(d), capture_output=True, text=True); out = (r.stdout + r.stderr).strip().split('\n'); R.setdefault('cli', {})[label] = [r.returncode, out[-1][:100] if r.returncode else 'ok']; print(f'  flask {label:<42} → 退出码 {r.returncode} {"" if r.returncode == 0 else out[-1][:100]}')
port = free_port()
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'good:create_app()'], port=port) as s: print('  gunicorn "good:create_app()" → GET / →', s.get('/')[2].decode().strip()); R['gun'] = s.get('/')[2].decode().strip()
print()
print('== 六:创建一个应用的耗时:带 1 个蓝图与 1 个扩展 init_app 的工厂(timeit,500 次一组取最小)')
t = min(timeit.timeit(lambda: create_app({'NAME': 'x'}), number=500) / 500 * 1e6 for _ in range(3)); print(f'  create_app(...) 每次 {t:.0f} µs'); R['cost'] = t
save('f70', R)
