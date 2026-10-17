import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d73'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
def cart(request): request.session['cart'] = [1, 2]; request.session.save(); return JsonResponse({'key': request.session.session_key})
def do_login(request):
    before = request.session.session_key
    u = authenticate(request, username=request.GET['u'], password='pw'); login(request, u)
    return JsonResponse({'before': before, 'after': request.session.session_key, 'cart': request.session.get('cart')})
def do_logout(request):
    before = request.session.session_key; logout(request); return JsonResponse({'before': before, 'after': request.session.session_key, 'cart': request.session.get('cart')})
urlpatterns = [path('cart/', cart), path('login/', do_login), path('logout/', do_logout)]
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions']
d = proj('d73', urls=urls, apps=apps, middleware=['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware'], with_lab=False); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom django.contrib.auth.models import User\nfrom django.contrib.sessions.models import Session\nfor n in ('u', 'v'):\n    User.objects.filter(username=n).delete(); User.objects.create_user(n, password='pw')\ndef sql(c): return [' '.join(q['sql'].split())[:100] for q in c.captured_queries]\n" + code); return out.rstrip()
print('== 一:匿名时放了购物车 → 登录:session_key 换新,数据保留(cycle_key);老 key 的行被删除')
o = run("""
Session.objects.all().delete(); c = Client(); k0 = c.get('/cart/').json()['key']
with CaptureQueriesContext(connection) as q: r = c.get('/login/?u=u').json()
print('登录前 key =', k0[:8] + '…', ' 登录后 key =', r['after'][:8] + '…', ' key 变了:', k0 != r['after'], ' cart 保留:', r['cart'])
print('session 表现在的 key:', [s.session_key[:8] + '…' for s in Session.objects.all()], ' (老 key 已删除:', not Session.objects.filter(session_key=k0).exists(), ')')
print('登录发出的 SQL:'); [print('   ', s) for s in sql(q)]
""")
print(o); R['cycle'] = o
print()
print('== 二:已经以用户 u 登录时再以另一个用户 v 登录:整个 session 被清空(flush),而不是保留数据')
o = run("""
Session.objects.all().delete(); c = Client(); c.get('/cart/'); c.get('/login/?u=u')
r = c.get('/login/?u=v').json(); print('u → v:cart =', r['cart'], ' key 变了:', r['before'] != r['after'])
r = c.get('/login/?u=v').json(); print('v → v(同一用户再登录):cart 与 key:', r['cart'], r['before'] == r['after'])
""")
print(o); R['switch'] = o
print()
print('== 三:logout():整个 session 被 flush(行删除、数据清空)')
o = run("""
Session.objects.all().delete(); c = Client(); c.get('/cart/'); c.get('/login/?u=u'); n0 = Session.objects.count()
with CaptureQueriesContext(connection) as q: r = c.get('/logout/').json()
print('登出前 session 行数 =', n0, ' 登出后 =', Session.objects.count(), ' 登出后 cart =', r['cart'], ' key 变了:', r['before'] != r['after'])
print('SQL:'); [print('   ', s) for s in sql(q)]
print('用旧 cookie 之外的新会话重新访问 /cart/:', c.get('/cart/').json()['key'][:8] + '…')
""")
print(o); R['logout'] = o
print()
print('== 四:login() 更新 last_login 并发出 user_logged_in 信号;可以用 update_last_login 断开以减少写')
o = run("""
u = User.objects.get(username='u'); print('登录前 last_login =', u.last_login)
c = Client(); c.get('/login/?u=u'); print('登录后 last_login =', str(User.objects.get(username='u').last_login)[:19])
from django.contrib.auth.models import update_last_login
from django.contrib.auth.signals import user_logged_in
user_logged_in.disconnect(update_last_login, dispatch_uid='update_last_login')
User.objects.filter(username='v').update(last_login=None); c2 = Client(); c2.get('/login/?u=v'); print('断开 update_last_login 之后登录 v:last_login =', User.objects.get(username='v').last_login)
""")
print(o); R['lastlogin'] = o
save('d73', R)
