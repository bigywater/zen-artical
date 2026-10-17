import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d13'); R = {}
def run(d, title, code, **kw):
    rc, out = pyscript(d, code, **kw) if kw.pop('setup', True) else py(d, code, **kw)
    ls = out.strip().splitlines(); print(f'  [{title}]'); [print('   ', l) for l in (ls if len(ls) <= 8 else ls[-1:])]; return '\n'.join(ls if len(ls) <= 8 else ls[-1:])
d = proj('d13', files={
    'lab/models.py': "from django.db import models\nfrom django.apps import apps\nprint('  (lab/models.py 导入时) apps_ready=%s models_ready=%s ready=%s' % (apps.apps_ready, apps.models_ready, apps.ready))\nclass Item(models.Model):\n    n = models.IntegerField()\n",
    'lab/apps.py': "from django.apps import AppConfig, apps\nclass LabConfig(AppConfig):\n    name = 'lab'\n    def ready(self):\n        print('  (LabConfig.ready() 里) apps_ready=%s models_ready=%s ready=%s' % (apps.apps_ready, apps.models_ready, apps.ready))\n",
    'other/__init__.py': '', 'other/models.py': "from django.db import models\nclass Thing(models.Model):\n    pass\n",
}, apps=['django.contrib.contenttypes', 'django.contrib.auth', 'lab', 'other'])
print('== 一:三个阶段:apps_ready → models_ready → ready(在 setup() 里依次完成)')
R['phases'] = run(d, '导入模型与 ready() 时各标志的值', "from django.apps import apps\nprint('  (setup() 结束后) apps_ready=%s models_ready=%s ready=%s' % (apps.apps_ready, apps.models_ready, apps.ready))\nprint('  app_configs 顺序:', list(apps.app_configs))\nprint('  get_models() 共 %d 个,前几个:' % len(apps.get_models()), [m.__name__ for m in apps.get_models()][:6])\nprint('  Item 的 app_label:', apps.get_model('lab', 'Item')._meta.app_label)\n")
print()
print('== 二:setup() 之前使用注册表 / 模型')
R['notready1'] = run(d, '未 setup 就 get_model', "from django.apps import apps\ntry: apps.get_model('lab', 'Item')\nexcept Exception as e: print(type(e).__name__ + ':', e)", setup=False)
R['notready2'] = run(d, '未 setup 就导入模型', "from lab.models import Item\n", setup=False)
print()
print('== 三:配置错误的报错原文')
def bad(title, apps_, files=None):
    dd = proj('d13x', files=files, apps=apps_)
    rc, out = py(dd, "import django\ndjango.setup()")
    last = [l for l in out.strip().splitlines() if l.strip()][-1]; print(f'  [{title}] {last}'); return last
R['bad'] = {}
R['bad']['dup_name'] = bad('同一个 app 写两次', ['django.contrib.contenttypes', 'lab', 'lab'])
R['bad']['dup_cfg'] = bad("'lab' 与 'lab.apps.LabConfig' 同时写", ['django.contrib.contenttypes', 'lab', 'lab.apps.LabConfig'], {'lab/apps.py': "from django.apps import AppConfig\nclass LabConfig(AppConfig):\n    name = 'lab'\n"})
R['bad']['dup_label'] = bad('两个 app 的 label 相同', ['django.contrib.contenttypes', 'x.lab', 'y.lab'], {'x/__init__.py': '', 'x/lab/__init__.py': '', 'y/__init__.py': '', 'y/lab/__init__.py': ''})
R['bad']['missing'] = bad('INSTALLED_APPS 里写了不存在的 app', ['django.contrib.contenttypes', 'nonexistent_app'])
R['bad']['nolabel'] = None
dd = proj('d13y', files={'stray/__init__.py': '', 'stray/models.py': "from django.db import models\nclass Stray(models.Model):\n    pass\n"}, apps=['django.contrib.contenttypes'])
rc, out = pyscript(dd, "import stray.models"); last = out.strip().splitlines()[-1]; print('  [模型所在的包不在 INSTALLED_APPS]', last); R['bad']['stray'] = last
print()
print('== 四:AppConfig 自动发现:apps.py 里有多个 AppConfig 子类时选哪个')
dd = proj('d13z', files={'lab/apps.py': "from django.apps import AppConfig\nclass AConfig(AppConfig):\n    name = 'lab'\n    verbose_name = 'A(第一个定义)'\nclass BConfig(AppConfig):\n    name = 'lab'\n    default = True\n    verbose_name = 'B(default = True)'\n"}, apps=['django.contrib.contenttypes', 'lab'])
R['auto1'] = run(dd, "两个子类,B 标了 default = True", "from django.apps import apps\nprint(type(apps.get_app_config('lab')).__name__, apps.get_app_config('lab').verbose_name)")
dd = proj('d13w', files={'lab/apps.py': "from django.apps import AppConfig\nclass AConfig(AppConfig):\n    name = 'lab'\nclass BConfig(AppConfig):\n    name = 'lab'\n"}, apps=['django.contrib.contenttypes', 'lab'])
rc, out = pyscript(dd, "from django.apps import apps\nprint(type(apps.get_app_config('lab')).__name__)"); R['auto2'] = out.strip().splitlines()[-1]; print('  [两个子类都没标 default]', R['auto2'])
dd = proj('d13v', apps=['django.contrib.contenttypes', 'lab']); rc, out = pyscript(dd, "from django.apps import apps\nprint(type(apps.get_app_config('lab')).__name__)"); R['auto3'] = out.strip().splitlines()[-1]; print('  [没有 apps.py]', R['auto3'])
save('d13', R)
