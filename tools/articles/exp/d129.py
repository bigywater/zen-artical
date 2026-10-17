import sys, os, time, json, re, subprocess, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d129'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from django.db import connection
def ping(r): return HttpResponse('ok')
def boom(r):
    card_number = '4111-1111-1111-1111'
    raise RuntimeError('后台出错了')
@sensitive_variables('card_number')
def boom_sensitive(r):
    card_number = '4111-1111-1111-1111'
    raise RuntimeError('后台出错了')
def q(r):
    from django.contrib.contenttypes.models import ContentType
    for _ in range(50): ContentType.objects.count()
    return HttpResponse(str(len(connection.queries)))
urlpatterns = [path('ping/', ping), path('boom/', boom), path('boom_sensitive/', boom_sensitive), path('q/', q)]
'''
d = proj('d129', urls=urls, apps=['django.contrib.contenttypes', 'django.contrib.staticfiles'], with_lab=False, middleware=[], settings_extra=ES + "\nSTATICFILES_DIRS = [BASE_DIR / 'static']\n", files={'static/hello.txt': 'static file content\n'})
manage(d, 'migrate')
print('== 一:同一个出错的 / 不存在的页面,DEBUG=True vs False')
o = srun(d, """
c = Client(raise_request_exception=False)
def title(b):
    m = re.search(r'<title>(.*?)</title>', b, re.S); return re.sub(r'\\s+', ' ', m.group(1)).strip() if m else b[:40].replace(chr(10), ' ')
import re
for path, label in (('/nope/', '不存在的路径'), ('/boom/', '视图抛异常(局部变量 card_number)'), ('/boom_sensitive/', '同上,@sensitive_variables("card_number")')):
    r = c.get(path, HTTP_HOST='x'); b = r.content.decode()
    print(f'  DEBUG={settings.DEBUG!s:<5} {label:<40} → {r.status_code}  页面 {len(b):>6} 字节  标题: {title(b)[:50]}  含 card_number 的值: {"4111-1111" in b}  含异常文本: {"后台出错了" in b}')
""", ALLOWED_HOSTS=['*'], DEBUG=True)
print(o); R['pages_on'] = o
o = srun(d, """
import re
c = Client(raise_request_exception=False)
def title(b):
    m = re.search(r'<title>(.*?)</title>', b, re.S); return re.sub(r'\\s+', ' ', m.group(1)).strip() if m else b[:40].replace(chr(10), ' ')
for path, label in (('/nope/', '不存在的路径'), ('/boom/', '视图抛异常(局部变量 card_number)'), ('/boom_sensitive/', '同上,@sensitive_variables("card_number")')):
    r = c.get(path, HTTP_HOST='x'); b = r.content.decode()
    print(f'  DEBUG={settings.DEBUG!s:<5} {label:<40} → {r.status_code}  页面 {len(b):>6} 字节  标题: {title(b)[:50]}  含 card_number 的值: {"4111-1111" in b}  含异常文本: {"后台出错了" in b}')
""", ALLOWED_HOSTS=['*'], DEBUG=False)
print(o); R['pages_off'] = o
print()
print('== 二:DEBUG=True 的 500 页面里有没有 SECRET_KEY 原文?(设置页的脱敏)')
o = srun(d, """
c = Client(raise_request_exception=False)
b = c.get('/boom/', HTTP_HOST='x').content.decode()
print('  页面里有 SECRET_KEY 这个名字:', 'SECRET_KEY' in b, ' | 含密钥原文:', settings.SECRET_KEY in b, ' | 含 ********************:', '********************' in b)
print('  页面里有「Settings」表:', 'Settings' in b, ' | 含 ALLOWED_HOSTS 原值:', '&#x27;*&#x27;' in b or \"'*'\" in b, ' | 含数据库文件路径:', 'db.sqlite3' in b)
""", ALLOWED_HOSTS=['*'], DEBUG=True)
print(o); R['leak'] = o
print()
print('== 三:DEBUG=True 时每条 SQL 会被记进 connection.queries;DEBUG=False 不记')
for dbg in (True, False):
    o = srun(d, "r = Client().get('/q/', HTTP_HOST='x'); print(f'  DEBUG={settings.DEBUG!s:<5} 视图里做 50 次查询后 len(connection.queries) =', r.content.decode())", ALLOWED_HOSTS=['*'], DEBUG=dbg)
    print(o); R['q_' + str(dbg)] = o
print()
print('== 四:出错时给 ADMINS 发邮件(locmem 邮件后端):DEBUG=True 不发;DEBUG=False 发,并看邮件正文里有没有局部变量的值')
for dbg in (True, False):
    o = srun(d, """
from django.test.utils import setup_test_environment; setup_test_environment()
from django.core import mail
import logging; logging.disable(logging.NOTSET)
c = Client(raise_request_exception=False)
for path in ('/boom/', '/boom_sensitive/'):
    mail.outbox.clear(); c.get(path, HTTP_HOST='x')
    body = ' '.join(m.body for m in mail.outbox)
    print(f'  DEBUG={settings.DEBUG!s:<5} {path:<18} 邮件数 {len(mail.outbox)}  主题 {[m.subject[:48] for m in mail.outbox]}  正文含 card_number 的值: {"4111-1111" in body}')
""", ALLOWED_HOSTS=['*'], DEBUG=dbg, ADMINS=[['ops', 'ops@example.com']], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    o = '\n'.join(l for l in o.splitlines() if l.startswith('  DEBUG=')); print(o); R['mail_' + str(dbg)] = o
print()
print('== 五:runserver 与静态文件(真实起 runserver:9543)')
def rs(dbg, *extra):
    p = subprocess.Popen([PY, 'manage.py', 'runserver', '127.0.0.1:9543', '--noreload', *extra], cwd=d, env=env(d, EXTRA_SETTINGS=json.dumps({'ALLOWED_HOSTS': ['*'], 'DEBUG': dbg})), stdout=open(d / 'rs.log', 'w'), stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            try: c = http.client.HTTPConnection('127.0.0.1', 9543, timeout=1); c.request('GET', '/ping/'); c.getresponse().read(); break
            except Exception: time.sleep(0.2)
        c = http.client.HTTPConnection('127.0.0.1', 9543, timeout=5); c.request('GET', '/static/hello.txt'); r = c.getresponse(); return r.status
    finally: p.terminate(); p.wait(10)
R['static'] = {}
for label, dbg, extra in (('DEBUG=True', True, ()), ('DEBUG=False', False, ()), ('DEBUG=False + --insecure', False, ('--insecure',))):
    st = rs(dbg, *extra); R['static'][label] = st; print(f'  runserver {label:<26} GET /static/hello.txt → {st}')
print()
print('== 六:manage.py check --deploy 对 DEBUG=True 的提示')
rc, out = smanage(d, 'check', '--deploy', DEBUG=True, ALLOWED_HOSTS=['example.com'])
ws = [(m.group(1), m.group(2)[:80]) for m in re.finditer(r'\?: \((security\.W018)\) (.+)', out)]
print('  ', ws or '没有 W018'); R['w018'] = ws
save('d129', R)
