import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d11'); R = {}
LOG = "import os, time\ndef mark(s):\n    with open(os.environ['EV_LOG'], 'a') as f: f.write(f'{time.perf_counter():.6f} {os.getpid()} {s}\\n')\n"
d = proj('d11', files={
    'proj/mark.py': LOG,
    'lab/apps.py': "from django.apps import AppConfig\nfrom proj.mark import mark\nmark('import lab/apps.py(AppConfig 所在模块被导入)')\nclass LabConfig(AppConfig):\n    name = 'lab'\n    default_auto_field = 'django.db.models.BigAutoField'\n    def __init__(self, *a, **k):\n        mark('LabConfig.__init__(创建 AppConfig 实例)'); super().__init__(*a, **k)\n    def ready(self):\n        mark('LabConfig.ready()')\n",
    'lab/models.py': "from django.db import models\nfrom proj.mark import mark\nmark('import lab/models.py')\nclass Item(models.Model):\n    name = models.CharField(max_length=20)\n",
    'lab/views.py': "from django.http import HttpResponse\nfrom proj.mark import mark\nmark('import lab/views.py')\ndef hello(request):\n    mark('view: hello()')\n    return HttpResponse('hi')\n",
    'proj/urls.py': "from django.urls import path\nfrom proj.mark import mark\nmark('import proj/urls.py(ROOT_URLCONF)')\nfrom lab.views import hello\nurlpatterns = [path('hello/', hello)]\n",
    'proj/mw.py': "from proj.mark import mark\nmark('import proj/mw.py')\nclass MW:\n    def __init__(self, get_response):\n        mark('MW.__init__(中间件链在首次请求前构建)'); self.get_response = get_response\n    def __call__(self, request):\n        mark('MW.__call__ 进入'); r = self.get_response(request); mark('MW.__call__ 返回'); return r\n",
}, apps=['django.contrib.contenttypes', 'django.contrib.auth', 'lab.apps.LabConfig'], middleware=['proj.mw.MW'],
   settings_extra="\nfrom proj.mark import mark\nmark('import proj/settings.py(首次访问 settings 才会导入)')\n")
def events(log):
    L = [l.split(' ', 2) for l in open(log).read().splitlines()]
    t0 = float(L[0][0]); return [(float(a) - t0, b, c) for a, b, c in L]
print('== 一:用 python manage.py check 跑一次,按时间顺序看每个模块什么时候被导入、什么时候被调用')
log = str(DJ / 'd11' / 'ev1.log'); open(log, 'w').close()
t0 = time.perf_counter(); rc, out = manage(d, 'check', EV_LOG=log); wall = ms(t0)
print('  命令输出:', out.strip().splitlines()[-1] if out.strip() else '(无)', f' 整个进程 {wall:.0f} ms')
ev = events(log)
for t, pid, s in ev: print(f'  +{t*1000:7.1f} ms  {s}')
R['check_events'] = [(round(t * 1000, 1), s) for t, _, s in ev]
print()
print('== 二:同一个项目,处理一次请求(django.test.Client,进程内)的顺序')
log2 = str(DJ / 'd11' / 'ev2.log'); open(log2, 'w').close()
rc, out = pyscript(d, "from django.test import Client\nfrom proj.mark import mark\nmark('--- django.setup() 已完成 ---')\nc = Client()\nmark('--- 发出第 1 个请求 ---')\nr = c.get('/hello/')\nmark('--- 第 1 个请求结束 status=%d ---' % r.status_code)\nmark('--- 发出第 2 个请求 ---')\nc.get('/hello/')\nmark('--- 第 2 个请求结束 ---')\n", EV_LOG=log2)
ev2 = events(log2)
for t, pid, s in ev2: print(f'  +{t*1000:7.1f} ms  {s}')
R['req_events'] = [(round(t * 1000, 1), s) for t, _, s in ev2]
print()
print('== 三:django.setup() 本身的耗时随 INSTALLED_APPS 增多的变化(每种 5 次取中位)')
import statistics
rows = {}
for label, apps in (('只有 contenttypes', ['django.contrib.contenttypes']), ('contenttypes+auth+sessions+messages', ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'django.contrib.messages']), ('上面 + admin + staticfiles', ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.admin', 'django.contrib.staticfiles'])):
    d2 = proj('d11b', apps=apps, with_lab=False)
    ts = []
    for _ in range(5):
        rc, out = py(d2, "import time\nt=time.perf_counter()\nimport django\nt1=time.perf_counter()\ndjango.setup()\nt2=time.perf_counter()\nprint('%.2f %.2f' % ((t1-t)*1000,(t2-t1)*1000))")
        ts.append(float(out.split()[1]))
    rows[label] = statistics.median(ts); print(f'  {label:<44} django.setup() 中位 {rows[label]:.1f} ms')
R['setup_ms'] = rows
save('d11', R)
