import sys, os, time, json, signal, socket, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d14'); R = {}
LOGM = "import os, time\ndef mark(s):\n    with open(os.environ['EV_LOG'], 'a') as f: f.write(f'{os.getpid()} {s}\\n')\n"
files = {
    'proj/mark.py': LOGM,
    'a/__init__.py': '', 'a/apps.py': "from django.apps import AppConfig, apps\nfrom proj.mark import mark\nclass AConfig(AppConfig):\n    name = 'a'\n    def ready(self):\n        mark('a.ready()  b 的模型已加载?%s  apps.ready=%s' % (apps.models_ready, apps.ready))\n",
    'a/models.py': "from django.db import models\nclass A1(models.Model):\n    pass\n",
    'b/__init__.py': '', 'b/apps.py': "from django.apps import AppConfig\nfrom proj.mark import mark\nclass BConfig(AppConfig):\n    name = 'b'\n    def ready(self):\n        mark('b.ready()')\n",
    'b/models.py': "from django.db import models\nclass B1(models.Model):\n    pass\n",
    'proj/urls.py': "from django.urls import path\nfrom django.http import HttpResponse\nfrom proj.mark import mark\nmark('urls 被导入')\nurlpatterns = [path('', lambda r: HttpResponse('ok'))]\n",
}
d = proj('d14', files=files, apps=['django.contrib.contenttypes', 'a.apps.AConfig', 'b.apps.BConfig'], with_lab=False)
def lines(log): return open(log).read().splitlines() if os.path.exists(log) else []
def fresh(name): p = str(DJ / 'd14' / name); open(p, 'w').close(); return p
print('== 一:ready() 的时机与顺序:按 INSTALLED_APPS 的顺序调用,调用时所有模型都已加载')
lg = fresh('l1.log'); manage(d, 'check', EV_LOG=lg); R['order'] = lines(lg); [print('  ', l.split(' ', 1)[1]) for l in R['order']]
print()
print('== 二:哪些命令会触发 ready()(每条命令新进程,数 ready 调用次数)')
R['cmds'] = {}
for cmd in (['check'], ['showmigrations'], ['makemigrations', '--check', '--dry-run'], ['test', '--noinput'], ['help']):
    lg = fresh('l2.log'); rc, out = manage(d, *cmd, EV_LOG=lg); n = sum('a.ready()' in l for l in lines(lg)); R['cmds'][' '.join(cmd)] = n; print(f'  manage.py {" ".join(cmd):<34} a.ready() 调用 {n} 次')
print()
print('== 三:runserver 默认带自动重载,进程会启动两次;--noreload 只启动一次')
R['runserver'] = {}
for label, extra in (('runserver(默认,自动重载)', []), ('runserver --noreload', ['--noreload'])):
    lg = fresh('l3.log'); port = 9310
    p = subprocess.Popen([PY, 'manage.py', 'runserver', f'127.0.0.1:{port}', *extra], cwd=d, env=env(d, EV_LOG=lg), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1).read(); break
        except Exception: time.sleep(0.1)
    time.sleep(0.5); L = lines(lg); pids = sorted(set(l.split(' ')[0] for l in L if 'a.ready()' in l))
    R['runserver'][label] = dict(ready=sum('a.ready()' in l for l in L), pids=len(pids), urls=sum('urls' in l for l in L))
    print(f'  {label:<28} a.ready() {R["runserver"][label]["ready"]} 次,来自 {len(pids)} 个不同进程;urls 导入 {R["runserver"][label]["urls"]} 次(pid: {", ".join(pids)})')
    p.send_signal(signal.SIGINT); 
    try: p.wait(10)
    except Exception: p.kill()
    subprocess.run(['pkill', '-f', f'runserver 127.0.0.1:{port}'], capture_output=True); time.sleep(0.5)
print()
print('== 四:在 ready() 里查数据库:全新数据库上 migrate 会怎样')
d2 = proj('d14b', files={'lab/models.py': "from django.db import models\nclass Item(models.Model):\n    n = models.IntegerField(default=0)\n", 'lab/apps.py': "from django.apps import AppConfig\nclass LabConfig(AppConfig):\n    name = 'lab'\n    def ready(self):\n        from lab.models import Item\n        print('ready() 里 Item 数量 =', Item.objects.count())\n"}, apps=['django.contrib.contenttypes', 'lab'])
manage(d2, 'makemigrations', 'lab')
rc, out = manage(d2, 'migrate', '-v', '0', '-W', 'always')  if False else manage(d2, 'migrate')
ol = [l for l in out.strip().splitlines() if l.strip()]; print('  全新库上 python manage.py migrate(rc=%d),最后一行:' % rc, ol[-1]); R['ready_query'] = dict(rc=rc, last=ol[-1])
rc, out = manage(d2, 'check', '-W', 'error') if False else manage(d2, 'check'); R['ready_query']['check_last'] = out.strip().splitlines()[-1]; print('  同一个库上 check(表还不存在),最后一行:', R['ready_query']['check_last'])
save('d14', R)
