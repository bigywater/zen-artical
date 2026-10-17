import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f1'); R = {}
import flask
from flask import Flask
print('== 一:Flask(__name__) 之后,应用对象上有什么(新建一个文件 appmod.py 里的应用,打印它的属性)')
d = app('f1a', {'appmod.py': 'from flask import Flask\napp = Flask(__name__)\n', 'pkg/__init__.py': 'from flask import Flask\napp = Flask(__name__)\n', 'pkg/sub.py': 'from flask import Flask\napp = Flask(__name__)\n'})
src('''
    from flask import Flask
    app = Flask(__name__)
    print(app.name, app.import_name)
    print('root_path     ', app.root_path)
    print('instance_path ', app.instance_path)
    print('static_folder ', app.static_folder, '| static_url_path', app.static_url_path)
    print('template_folder', app.template_folder)
    print('url_map 规则  ', [str(r) for r in app.url_map.iter_rules()])
    print('view_functions', list(app.view_functions))
    print('config 键数   ', len(app.config))
    print('blueprints    ', app.blueprints, '| extensions', app.extensions)
    print('session 接口  ', type(app.session_interface).__name__, '| json provider', type(app.json).__name__)
    print('jinja_env 是否已创建', 'jinja_env' in app.__dict__)
''', 'appmod.py 里的代码')
rc, o = py(d, '''
    from appmod import app
    print(app.name, app.import_name)
    print('root_path     ', app.root_path)
    print('instance_path ', app.instance_path)
    print('static_folder ', app.static_folder, '| static_url_path', app.static_url_path)
    print('template_folder', app.template_folder)
    print('url_map 规则  ', [str(r) for r in app.url_map.iter_rules()])
    print('view_functions', list(app.view_functions))
    print('config 键数   ', len(app.config))
    print('blueprints    ', app.blueprints, '| extensions', app.extensions)
    print('session 接口  ', type(app.session_interface).__name__, '| json provider', type(app.json).__name__)
    print('jinja_env 是否已创建', 'jinja_env' in app.__dict__)
''')
pr(o); R['attrs'] = o.split('\n')
print()
print('== 二:默认配置:没有任何设置时 app.config 里是什么')
rc, o = py(d, '''
    from appmod import app
    keys = ['DEBUG', 'TESTING', 'SECRET_KEY', 'SERVER_NAME', 'APPLICATION_ROOT', 'PREFERRED_URL_SCHEME', 'MAX_CONTENT_LENGTH', 'SESSION_COOKIE_NAME', 'SESSION_COOKIE_HTTPONLY', 'SESSION_COOKIE_SECURE', 'SESSION_COOKIE_SAMESITE', 'PERMANENT_SESSION_LIFETIME', 'TRAP_HTTP_EXCEPTIONS', 'PROPAGATE_EXCEPTIONS', 'JSON_SORT_KEYS', 'TEMPLATES_AUTO_RELOAD']
    print('全部键:', len(app.config))
    for k in keys: print(f'  {k:<28} {app.config.get(k, "(没有这个键)")!r}')
    print('全部键名:', sorted(app.config))
''')
pr(o, 30, w=230); R['config'] = o.split('\n')
print()
print('== 三:构造时就注册好的东西:静态文件路由、默认的上下文处理器、默认的 URL 转换器')
rc, o = py(d, '''
    from appmod import app
    from flask import Flask
    for r in app.url_map.iter_rules(): print('规则', r.rule, '| endpoint', r.endpoint, '| methods', sorted(r.methods), '| 转换器', {k: type(v).__name__ for k, v in r._converters.items()})
    print('url_map.converters:', sorted(app.url_map.converters))
    print('模板上下文处理器(None 键 = 所有蓝图):', {k: [f.__name__ for f in v] for k, v in app.template_context_processors.items()})
    print('before_request_funcs:', dict(app.before_request_funcs), '| error_handler_spec:', dict(app.error_handler_spec))
    print('app.cli 里额外注册的命令:', list(app.cli.commands))
    a2 = Flask(__name__, static_folder=None)
    print('static_folder=None 时的规则:', [str(r) for r in a2.url_map.iter_rules()])
''')
pr(o, 30, w=230); R['reg'] = o.split('\n')
r_ = subprocess.run([str(BIN / 'flask'), '--app', 'appmod', '--help'], cwd=d, env=env(d), capture_output=True, text=True); cmds = re.findall(r'^  (\w+)\s', r_.stdout.split('Commands:')[1], re.M); print('    flask --app appmod --help 列出的内置命令:', cmds); R['cmds'] = cmds
print()
print('== 四:惰性创建:jinja_env 与 logger 在第一次访问时才创建')
rc, o = py(d, '''
    import time
    from appmod import app
    d0 = set(app.__dict__)
    print('刚构造完 __dict__ 里的 jinja_env / logger:', 'jinja_env' in app.__dict__, 'logger' in app.__dict__)
    t = time.perf_counter(); env = app.jinja_env; t1 = (time.perf_counter() - t) * 1000
    print(f'访问 app.jinja_env(第一次):{t1:.2f} ms,之后 __dict__ 里有:', 'jinja_env' in app.__dict__)
    t = time.perf_counter(); env = app.jinja_env; t2 = (time.perf_counter() - t) * 1000
    print(f'第二次访问:{t2:.4f} ms')
    t = time.perf_counter(); lg = app.logger; t3 = (time.perf_counter() - t) * 1000
    print(f'访问 app.logger(第一次):{t3:.2f} ms,logger 名 =', lg.name, ',处理器数', len(lg.handlers))
    print('访问这两项之后新增的 __dict__ 键:', sorted(set(app.__dict__) - d0))
''')
pr(o); R['lazy'] = o.split('\n')
print()
print('== 五:root_path 与 instance_path 怎么来:同样写 Flask(__name__),放在模块里、包里、子模块里、直接 python 运行(__name__ == "__main__")')
rc, o = py(d, '''
    import appmod, pkg, pkg.sub
    for m in (appmod, pkg, pkg.sub):
        a = m.app; print(f'{m.__name__:<8} import_name={a.import_name:<8} root_path={a.root_path.replace(__import__("os").getcwd(), "<项目>")}  instance_path={a.instance_path.replace(__import__("os").getcwd(), "<项目>")}')
''')
pr(o); R['paths'] = o.split('\n')
d2 = app('f1b', {'run.py': 'from flask import Flask\napp = Flask(__name__)\nprint("__name__ =", __name__, "| import_name =", app.import_name, "| root_path =", app.root_path)\n'})
rc, o = pyfile(d2, 'run.py'); print('  直接 python run.py:'); pr(o.replace(str(d2), '<项目>'), 3); R['main'] = o
rc, o = py(d2, 'from flask import Flask\na = Flask("totally.different.name")\nprint(a.import_name, "| root_path =", a.root_path)\n'); print('  Flask("totally.different.name")(这个模块不存在):'); pr(o.replace(str(d2), '<项目>'), 3); R['bad'] = o
print()
print('== 六:构造一个 Flask 对象要多久(2000 次,取中位数 / 最大值)')
ts = []
for _ in range(2000):
    t = time.perf_counter(); Flask(__name__); ts.append((time.perf_counter() - t) * 1e6)
print(f'  Flask(__name__) 构造:中位数 {median(ts):.0f} µs,最大 {max(ts):.0f} µs(含首次)'); R['ctor'] = [median(ts), max(ts)]
save('f1', R)
