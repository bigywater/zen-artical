import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d71'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
def whoami(request): return JsonResponse({'user': str(request.user), 'auth': request.user.is_authenticated})
def touch_nothing(request): return HttpResponse('no user access')
def do_login(request):
    u = authenticate(request, username=request.GET['u'], password=request.GET['p'])
    if u is None: return HttpResponse('bad', status=401)
    login(request, u); return HttpResponse('in')
urlpatterns = [path('whoami/', whoami), path('nothing/', touch_nothing), path('login/', do_login)]
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions']
mw = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware']
d = proj('d71', urls=urls, apps=apps, middleware=mw, with_lab=False); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom django.contrib.auth.models import User\nUser.objects.filter(username='u').delete(); User.objects.create_user('u', password='pw')\ndef sql(c): return [' '.join(q['sql'].split())[:95] for q in c.captured_queries]\n" + code); return out.rstrip()
print('== 一:request.user 是惰性的:视图不碰它,就不查会话也不查用户')
o = run("""
c = Client()
with CaptureQueriesContext(connection) as q: c.get('/nothing/')
print('匿名、视图没访问 request.user:查询', len(q))
c.get('/login/?u=u&p=pw')
with CaptureQueriesContext(connection) as q: c.get('/nothing/')
print('已登录、视图没访问 request.user:查询', len(q), sql(q))
with CaptureQueriesContext(connection) as q: r = c.get('/whoami/')
print('已登录、视图访问 request.user:查询', len(q)); [print('   ', s) for s in sql(q)]; print('   →', r.json())
with CaptureQueriesContext(connection) as q: c2 = Client(); c2.get('/whoami/')
print('匿名(没有 sessionid cookie)访问 request.user:查询', len(q))
""")
print(o); R['lazy'] = o
print()
print('== 二:authenticate() 内部:遍历 AUTHENTICATION_BACKENDS,第一个返回用户的胜出;失败发 user_login_failed 信号')
o = run("""
from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_login_failed, user_logged_in
ev = []
user_login_failed.connect(lambda sender, credentials, **k: ev.append(('failed', dict(credentials))), weak=False)
user_logged_in.connect(lambda sender, user, **k: ev.append(('logged_in', user.username)), weak=False)
with CaptureQueriesContext(connection) as q: u = authenticate(username='u', password='wrong')
print('密码错误:返回', u, ' 查询:', sql(q), ' 信号:', ev)
ev.clear(); u = authenticate(username='u', password='pw'); print('密码对:返回', u, ' 信号:', ev)
ev.clear(); u = authenticate(username='u', password='pw', foo='bar'); print('多余参数 foo=bar:返回', u, ' ← 不同后端接收不同参数,ModelBackend 收下多余的 **kwargs')
ev.clear(); u = authenticate(token='x'); print('不带 username/password(别的凭据):返回', u, ' 信号:', ev)
u.is_active if u else None
User.objects.filter(username='u').update(is_active=False); print('is_active=False 的用户密码正确:', authenticate(username='u', password='pw'), '(ModelBackend 拒绝不活跃用户)')
User.objects.filter(username='u').update(is_active=True)
""")
print(o); R['auth'] = o
print()
print('== 三:登录后 session 里存了什么')
o = run("""
c = Client(); c.get('/login/?u=u&p=pw')
from django.contrib.sessions.models import Session
s = Session.objects.get(session_key=c.cookies['sessionid'].value); d = s.get_decoded()
print('session 内容的键:', sorted(d)); print('_auth_user_id =', d['_auth_user_id'], ' _auth_user_backend =', d['_auth_user_backend']); print('_auth_user_hash 长度 =', len(d['_auth_user_hash']), '(来自密码哈希的派生值)')
""")
print(o); R['session'] = o
save('d71', R)
