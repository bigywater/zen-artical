import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d12'); R = {}
d = proj('d12', files={'proj/extra.py': "from django.conf import settings\nSTALE = settings.DEBUG   # 模块导入时读一次\ndef fresh(): return settings.DEBUG\n"}, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nmy_lower = 1\nMY_UPPER = 2\nclass Nested: X = 1\nNESTED = Nested()\n")
def show(title, code, **kw):
    rc, out = py(d, code, **kw); print(f'  [{title}]'); [print('   ', l) for l in out.strip().splitlines()]; return out.strip()
print('== 一:settings 是惰性的:import settings 时并不导入 proj.settings,第一次读属性才导入')
o = show('导入与读取', """
import sys
from django.conf import settings
print('from django.conf import settings 之后,proj.settings 已导入?', 'proj.settings' in sys.modules)
print('settings._wrapped 类型:', type(settings._wrapped).__name__)
settings.DEBUG
print('读取 settings.DEBUG 之后,proj.settings 已导入?', 'proj.settings' in sys.modules)
print('settings._wrapped 类型:', type(settings._wrapped).__name__)
print('settings.SETTINGS_MODULE =', settings.SETTINGS_MODULE)
""")
R['lazy'] = o
print()
print('== 二:没有 DJANGO_SETTINGS_MODULE、写错模块名时的报错')
def bare(code, **e):
    ee = os.environ.copy(); ee.pop('DJANGO_SETTINGS_MODULE', None); ee['PYTHONPATH'] = str(d); ee.update(e)
    r = subprocess.run([PY, '-c', code], cwd=d, env=ee, capture_output=True, text=True); return (r.stdout + r.stderr).strip().splitlines()[-1]
R['nomod'] = bare("from django.conf import settings\nsettings.DEBUG")
print('  未设置环境变量:', R['nomod'])
R['badmod'] = bare("from django.conf import settings\nsettings.DEBUG", DJANGO_SETTINGS_MODULE='nope.settings')
print('  DJANGO_SETTINGS_MODULE=nope.settings:', R['badmod'])
print()
print('== 三:只有全大写的名字算设置;默认值来自 global_settings')
o = show('大小写与默认值', """
from django.conf import settings, global_settings
print('settings.MY_UPPER =', settings.MY_UPPER)
print('hasattr(settings, "my_lower") =', hasattr(settings, 'my_lower'))
try: settings.my_lower
except AttributeError as e: print('settings.my_lower →', type(e).__name__, e)
print('全局默认设置个数(global_settings 里全大写的名字):', len([n for n in dir(global_settings) if n.isupper()]))
print('proj.settings 里显式写了的设置个数:', len([n for n in dir(settings._wrapped.default_settings) if False]) if False else len([n for n in vars(__import__('proj.settings', fromlist=['x'])) if n.isupper()]))
print('DEFAULT_CHARSET(没写,取默认) =', settings.DEFAULT_CHARSET, '  DEBUG(写了 True) =', settings.DEBUG)
""")
R['case'] = o
rc, out = manage(d, 'diffsettings'); lines = [l for l in out.splitlines() if l.strip()]; print(f'  manage.py diffsettings 输出 {len(lines)} 行,前 6 行:'); [print('   ', l) for l in lines[:6]]; R['diffsettings_lines'] = len(lines)
print()
print('== 四:运行时改 settings 与 override_settings;模块导入时读过一次的值不会跟着变')
o = show('改写与覆盖', """
from django.conf import settings
from django.test import override_settings
import proj.extra as extra
print('导入 proj.extra 时读到的 STALE =', extra.STALE, ',fresh() =', extra.fresh())
with override_settings(DEBUG=False):
    print('override_settings(DEBUG=False) 内: settings.DEBUG =', settings.DEBUG, ' extra.STALE =', extra.STALE, ' extra.fresh() =', extra.fresh())
print('退出 with 之后: settings.DEBUG =', settings.DEBUG)
settings.DEBUG = False
print('直接赋值 settings.DEBUG = False 之后: fresh() =', extra.fresh(), '(进程内一直生效,没有还原)')
""")
R['override'] = o
print()
print('== 五:settings.configure() 只能调用一次;类型检查')
rc, out = py(d, "import os\nos.environ.pop('DJANGO_SETTINGS_MODULE', None)\nfrom django.conf import settings\nsettings.configure(DEBUG=True)\nprint('第一次 configure OK, DEBUG =', settings.DEBUG)\ntry: settings.configure(DEBUG=False)\nexcept RuntimeError as e: print('第二次 configure →', type(e).__name__ + ':', e)\nimport django\nfrom django.core.exceptions import ImproperlyConfigured\n")
print('\n'.join('    ' + l for l in out.strip().splitlines())); R['configure'] = out.strip()
d2 = proj('d12b', apps=None, with_lab=False, settings_extra="\nINSTALLED_APPS = 'django.contrib.contenttypes'\n")
rc, out = py(d2, "import django\ndjango.setup()"); R['strapps'] = out.strip().splitlines()[-1]; print('  INSTALLED_APPS 写成字符串:', R['strapps'])
save('d12', R)
