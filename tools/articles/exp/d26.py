import sys, os, time, json, signal, urllib.request; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d26'); R = {}
checks = '''
from django.core.checks import register, Error, Warning, Info, Tags
@register(Tags.models)
def my_error(app_configs, **kw): return [Error('自定义检查:发现一个错误', hint='把它修好', id='lab.E001')] if __import__('os').environ.get('LAB_ERR') else []
@register('lab_tag')
def my_warn(app_configs, **kw): return [Warning('自定义检查:这只是个警告', id='lab.W001')] if __import__('os').environ.get('LAB_WARN') else []
@register(Tags.database, deploy=True)
def my_deploy(app_configs, **kw): return [Info('只在 --deploy 时运行的检查', id='lab.I001')]
'''
d = proj('d26', files={'lab/checks.py': checks, 'lab/apps.py': "from django.apps import AppConfig\nclass LabConfig(AppConfig):\n    name = 'lab'\n    def ready(self): from . import checks\n"}, apps=['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'django.contrib.messages', 'lab.apps.LabConfig'], middleware=['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware'])
def m(*a, **e): rc, out = manage(d, *a, **e); return rc, out.strip()
print('== 一:没有问题时 check 的输出与退出码')
rc, out = m('check'); print(f'  rc={rc}  {out}'); R['ok'] = (rc, out)
print()
print('== 二:自定义 Error:check 失败、runserver 拒绝启动、migrate 也不运行')
rc, out = m('check', LAB_ERR=1); print(f'  check → rc={rc}'); [print('   ', l) for l in out.splitlines()]; R['err'] = (rc, out)
rc, out = manage(d, 'migrate', LAB_ERR=1); print(f'  migrate → rc={rc}  最后一行:', out.strip().splitlines()[-1]); R['err_migrate'] = (rc, out.strip().splitlines()[-1])
PORT = 9340
pr_ = subprocess.Popen([PY, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload'], cwd=d, env=env(d, LAB_ERR=1), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try: o, _ = pr_.communicate(timeout=15)
except Exception: pr_.kill(); o = '(未退出)'
print(f'  runserver → rc={pr_.returncode}  最后一行:', o.strip().splitlines()[-1] if o.strip() else '')
R['err_run'] = (pr_.returncode, o.strip().splitlines()[-1] if o.strip() else '')
print()
print('== 三:自定义 Warning:check 通过(rc=0)但提示;--fail-on-level 可以让它失败')
rc, out = m('check', LAB_WARN=1); print(f'  check → rc={rc}'); [print('   ', l) for l in out.splitlines()]; R['warn'] = (rc, out)
rc, out = m('check', '--fail-level', 'WARNING', LAB_WARN=1); print(f'  check --fail-level WARNING → rc={rc}'); R['warn_fail'] = rc
rc, out = manage(d, 'check', '--tag', 'lab_tag', LAB_WARN=1); print(f'  check --tag lab_tag → rc={rc}'); R['tag'] = rc
rc, out = m('check', '--tag', 'models', LAB_WARN=1); print(f'  check --tag models(不含 lab_tag) → rc={rc}  {out}')
print()
print('== 四:SILENCED_SYSTEM_CHECKS 可以静音某个 id')
d2 = proj('d26b', files={'lab/checks.py': checks, 'lab/apps.py': "from django.apps import AppConfig\nclass LabConfig(AppConfig):\n    name = 'lab'\n    def ready(self): from . import checks\n"}, apps=['django.contrib.contenttypes', 'lab.apps.LabConfig'], settings_extra="\nSILENCED_SYSTEM_CHECKS = ['lab.W001']\n")
rc, out = manage(d2, 'check', LAB_WARN=1); print(f'  SILENCED_SYSTEM_CHECKS=[lab.W001] → rc={rc}', out.strip()); R['silenced'] = out.strip()
print()
print('== 五:check --deploy 对当前(开发向)设置报出的问题')
rc, out = m('check', '--deploy'); L = out.splitlines(); ids = [l.split(':')[1].strip() if ':' in l else '' for l in L if l.startswith('?:') or 'security.' in l]
import re
ids = re.findall(r'\((security\.[WE]\d+|[a-z_]+\.[WEI]\d+)\)', out)
print(f'  rc={rc};报出的检查 id:', ids); R['deploy_ids'] = ids
for l in L: 
    if l.startswith('?') or l.startswith('System check') or l.startswith('WARNINGS'): pass
print('  最后一行:', L[-1] if L else ''); R['deploy_last'] = L[-1]
print()
print('== 六:哪些命令会自动跑检查?')
res = {}
for cmd in (['check'], ['migrate', '--check'], ['showmigrations'], ['makemigrations', '--check', '--dry-run'], ['test', '--noinput'], ['help'], ['shell', '-c', 'pass']):
    rc, out = manage(d, *cmd, LAB_ERR=1); res[' '.join(cmd)] = rc; print(f'  manage.py {" ".join(cmd):<34} LAB_ERR=1 时 rc={rc}  {"被检查拦下" if "SystemCheckError" in out or "System check identified" in out else "没有被拦"}')
R['auto'] = {k: v for k, v in res.items()}
save('d26', R)
