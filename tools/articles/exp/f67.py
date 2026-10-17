import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f67'); R = {}
import json, types
from flask import Flask
d = mkapp('f67', {'settings.py': '''
import os
DEBUG = True
SECRET_KEY = "from-module"
ITEMS = ["a", "b"]
_private = "x"
lower = "y"
class Nested: A = 1
def func(): return 1
''', 'settings_dir/__init__.py': '', 'settings_dir/base.py': 'class Base:\n    DEBUG = False\n    PAGE = 10\n    TAGS = ["t"]\nclass Dev(Base):\n    DEBUG = True\nclass Prod(Base):\n    PAGE = 100\n', 'dyn.cfg': 'import os\nHOME_SET = "HOME" in os.environ\nCOMPUTED = 6 * 7\nITEMS = [i * 2 for i in range(3)]\nprint("(from_pyfile 里的 print 也会执行)")\n', 'bad_syntax.cfg': 'X = (\n', 'cfg.toml': 'TITLE = "toml 标题"\nPORT = 8080\n[DB]\nHOST = "h"\n'})
sys.path.insert(0, str(d)); os.chdir(d)
def new(name='x'): return Flask(name, root_path=str(d))
print('== 一:from_object 的三种参数:模块名字符串、模块对象、类(或实例)')
a = new(); a.config.from_object('settings'); print('  from_object("settings"):', {k: a.config[k] for k in ('DEBUG', 'SECRET_KEY', 'ITEMS')}, '| 小写与下划线开头 lower/_private 在 config 里:', 'lower' in a.config, '_private' in a.config, '| 函数 func:', 'func' in a.config, '| 类 Nested:', 'Nested' in a.config); R['obj_str'] = [a.config['DEBUG'], 'lower' in a.config, 'Nested' in a.config]
import settings; a = new(); a.config.from_object(settings); print('  from_object(模块对象):SECRET_KEY =', a.config['SECRET_KEY'])
from settings_dir.base import Dev, Prod, Base
for lab, o in (('类 Dev(继承 Base)', Dev), ('类 Prod', Prod), ('实例 Dev()', Dev())): a = new(); a.config.from_object(o); print(f'  from_object({lab}):DEBUG={a.config["DEBUG"]} PAGE={a.config["PAGE"]} TAGS={a.config["TAGS"]}'); R.setdefault('cls', {})[lab] = [a.config['DEBUG'], a.config['PAGE']]
a = new(); a.config.from_object('settings_dir.base.Dev'); print('  from_object("settings_dir.base.Dev")(带点的路径指向类):DEBUG =', a.config['DEBUG'], 'PAGE =', a.config['PAGE']); R['dotted'] = [a.config['DEBUG'], a.config['PAGE']]
print()
print('== 二:从对象加载时,可变值是同一个对象:改一个 app 的列表会影响所有 app(与类本身)')
a1, a2 = new('m1'), new('m2'); a1.config.from_object(Base); a2.config.from_object(Base); a1.config['TAGS'].append('polluted'); print('  a1 改了 TAGS 后,a2 的 TAGS =', a2.config['TAGS'], '| Base.TAGS =', Base.TAGS, '| 同一个对象:', a1.config['TAGS'] is a2.config['TAGS']); R['shared'] = [a2.config['TAGS'], a1.config['TAGS'] is a2.config['TAGS']]
Base.TAGS.remove('polluted')
print()
print('== 三:from_pyfile:文件被当作 Python 代码执行(可以写计算、条件、循环,也能执行任意代码)')
a = new(); a.config.from_pyfile('dyn.cfg'); print('  加载 dyn.cfg 之后:', {k: a.config[k] for k in ('HOME_SET', 'COMPUTED', 'ITEMS')}); R['pyfile'] = {k: a.config[k] for k in ('HOME_SET', 'COMPUTED', 'ITEMS')}
for label, call in (('文件不存在', lambda: a.config.from_pyfile('nope.cfg')), ('文件不存在 + silent=True', lambda: a.config.from_pyfile('nope.cfg', silent=True)), ('语法错误', lambda: a.config.from_pyfile('bad_syntax.cfg'))):
    try: r = call(); print(f'  {label}:返回 {r!r}'); R.setdefault('pyerr', {})[label] = repr(r)
    except Exception as e: msg = str(e).replace(str(d), '<项目>'); print(f'  {label}:{type(e).__name__}: {msg[:110]}'); R.setdefault('pyerr', {})[label] = f'{type(e).__name__}: {msg[:110]}'
print()
print('== 四:from_envvar:环境变量里存的是「配置文件的路径」,不是配置值')
a = new()
try: a.config.from_envvar('APP_SETTINGS')
except RuntimeError as e: print('  环境变量没设置 →', 'RuntimeError:', str(e)[:200]); R['envvar_missing'] = str(e)[:200]
print('  silent=True →', a.config.from_envvar('APP_SETTINGS', silent=True))
os.environ['APP_SETTINGS'] = str(d / 'dyn.cfg'); print('  设置 APP_SETTINGS=<路径> 后 →', a.config.from_envvar('APP_SETTINGS'), '| COMPUTED =', a.config['COMPUTED']); R['envvar_ok'] = a.config['COMPUTED']
print()
print('== 五:from_file:用任何解析器(json.load、tomllib.load)加载;toml 要用二进制模式 text=False')
import tomllib; a = new(); a.config.from_file('cfg.toml', load=tomllib.load, text=False); print('  tomllib:', {k: a.config[k] for k in ('TITLE', 'PORT', 'DB')}); R['toml'] = {k: a.config[k] for k in ('TITLE', 'PORT', 'DB')}
(d / 'lower.json').write_text(json.dumps({'title': 'lower', 'UP': 1})); a = new(); a.config.from_file('lower.json', load=json.load); print('  json 里的小写键 title:', 'title' in a.config, '| 大写 UP:', 'UP' in a.config, '(from_file 内部调用 from_mapping,同样只收大写键)'); R['file_lower'] = ['title' in a.config, 'UP' in a.config]
a = new(); a.config.from_file('lower.json', load=json.load, silent=False); a2 = new(); a2.config.from_mapping(json.load(open(d / 'lower.json'))); print('  from_mapping 同一份 json:', {k: a2.config[k] for k in ('UP',)}, '| title 在吗:', 'title' in a2.config); R['mapping'] = ['title' in a2.config]
print()
print('== 六:from_mapping 与 update 与直接赋值:from_mapping 接受字典与关键字参数,同样只收大写键')
a = new(); a.config.from_mapping({'A': 1, 'b': 2}, C=3, d=4); print('  from_mapping({"A": 1, "b": 2}, C=3, d=4) →', {k: a.config.get(k) for k in ('A', 'b', 'C', 'd')}); R['from_mapping'] = {k: a.config.get(k) for k in ('A', 'b', 'C', 'd')}
a.config.update({'b': 2}); a.config['d'] = 4; print('  update / 赋值 不过滤大小写:', {k: a.config.get(k) for k in ('b', 'd')}); R['update'] = {k: a.config.get(k) for k in ('b', 'd')}
save('f67', R)
