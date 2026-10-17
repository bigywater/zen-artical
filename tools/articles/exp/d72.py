import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d72'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse, JsonResponse
def setv(request): request.session['cart'] = [1, 2, 3]; return HttpResponse('set')
def read(request): return JsonResponse({'cart': request.session.get('cart')})
def nothing(request): return HttpResponse('nothing')
def readonly_key(request): request.session.get('x'); return HttpResponse('read only')
urlpatterns = [path('set/', setv), path('read/', read), path('nothing/', nothing), path('ro/', readonly_key)]
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions']
d = proj('d72', urls=urls, apps=apps, middleware=['django.contrib.sessions.middleware.SessionMiddleware'], with_lab=False); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom django.contrib.sessions.models import Session\ndef sql(c): return [' '.join(q['sql'].split())[:100] for q in c.captured_queries]\n" + code); return out.rstrip()
print('== 一:什么时候才会创建 session 行、发 Set-Cookie')
o = run("""
Session.objects.all().delete(); c = Client()
for url in ('/nothing/', '/ro/', '/read/', '/set/'):
    r = c.get(url); print(f'GET {url:<10} Set-Cookie: {"sessionid" in r.cookies!s:<5} session 表行数: {Session.objects.count()}')
""")
print(o); R['create'] = o
print()
print('== 二:session 表里存的是什么;cookie 的属性')
o = run("""
Session.objects.all().delete(); c = Client(); r = c.get('/set/'); s = Session.objects.get()
print('session_key 长度 =', len(s.session_key), ' expire_date 距现在 =', round((s.expire_date - __import__('django.utils.timezone', fromlist=['now']).now()).total_seconds() / 86400, 1), '天')
print('session_data(前 60 字符)=', s.session_data[:60], '…')
print('解码后:', s.get_decoded())
ck = r.cookies['sessionid']; print('Cookie 属性:', {k: ck[k] for k in ('httponly', 'samesite', 'max-age', 'path', 'secure') if ck[k] != ''})
""")
print(o); R['data'] = o
print()
print('== 三:每个请求的查询:读一次 = 1 次 SELECT;有修改才 UPDATE/INSERT')
o = run("""
Session.objects.all().delete(); c = Client(); c.get('/set/')
with CaptureQueriesContext(connection) as q: c.get('/read/')
print('/read/(只读):查询 =', len(q)); [print('   ', s) for s in sql(q)]
with CaptureQueriesContext(connection) as q: c.get('/set/')
print('/set/(修改):查询 =', len(q)); [print('   ', s) for s in sql(q)]
with CaptureQueriesContext(connection) as q: c.get('/nothing/')
print('/nothing/(不访问 session):查询 =', len(q))
""")
print(o); R['queries'] = o
print()
print('== 四:SESSION_SAVE_EVERY_REQUEST 与 SESSION_COOKIE_AGE 的默认值')
o = run("""
from django.conf import settings
print('SESSION_COOKIE_AGE =', settings.SESSION_COOKIE_AGE, '秒 =', settings.SESSION_COOKIE_AGE // 86400, '天;SESSION_SAVE_EVERY_REQUEST =', settings.SESSION_SAVE_EVERY_REQUEST, ';SESSION_COOKIE_HTTPONLY =', settings.SESSION_COOKIE_HTTPONLY, ';SESSION_COOKIE_SAMESITE =', settings.SESSION_COOKIE_SAMESITE, ';SESSION_EXPIRE_AT_BROWSER_CLOSE =', settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
""")
print(o); R['defaults'] = o
print()
print('== 五:过期的 session 不会自动从表里删除;clearsessions')
o = run("""
from django.utils import timezone; import datetime
Session.objects.all().delete(); c = Client(); c.get('/set/'); Session.objects.update(expire_date=timezone.now() - datetime.timedelta(days=1))
print('过期后表里行数:', Session.objects.count(), '; 用该 cookie 读取:', c.get('/read/').json())
""")
print(o); R['expired'] = o
rc, out = manage(d, 'clearsessions'); rc, o2 = pyscript(d, "from django.contrib.sessions.models import Session\nprint('clearsessions 之后表里行数:', Session.objects.count())"); print(o2.strip()); R['cleared'] = o2.strip()
save('d72', R)
