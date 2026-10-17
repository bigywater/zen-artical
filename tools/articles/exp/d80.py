import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d80'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
def me(request): return JsonResponse({'user': str(request.user)})
def change(request):
    u = request.user; u.set_password(request.GET['p']); u.save()
    if request.GET.get('keep') == '1': update_session_auth_hash(request, u)
    return HttpResponse('changed')
urlpatterns = [path('me/', me), path('change/', change)]
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions']
d = proj('d80', urls=urls, apps=apps, middleware=['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware'], with_lab=False); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.contrib.auth.models import User\nfrom django.contrib.sessions.models import Session\nUser.objects.filter(username='u').delete(); User.objects.create_user('u', password='old')\n" + code); return out.rstrip()
print('== 一:session 里存的 _auth_user_hash 是从密码哈希派生的;改密码后它变了')
o = run("""
c = Client(); c.login(username='u', password='old'); d = Session.objects.get(session_key=c.cookies['sessionid'].value).get_decoded(); h1 = d['_auth_user_hash']
u = User.objects.get(username='u'); print('session 里的 hash =', h1[:16] + '…  用户密码哈希 =', u.password[:24] + '…')
print('u.get_session_auth_hash() 与 session 里一致:', u.get_session_auth_hash() == h1)
u.set_password('new'); u.save(); print('改密码后 get_session_auth_hash() 与旧 session 里的一致:', User.objects.get(username='u').get_session_auth_hash() == h1)
""")
print(o); R['hash'] = o
print()
print('== 二:两台设备都登录着,在设备 A 上改密码:B 被踢下线;A 如果不调用 update_session_auth_hash 也会下线')
o = run("""
a = Client(); b = Client(); a.login(username='u', password='old'); b.login(username='u', password='old')
print('改密码前 A:', a.get('/me/').json(), ' B:', b.get('/me/').json())
a.get('/change/?p=new1')
print('A 上改密码(不调用 update_session_auth_hash)之后 A:', a.get('/me/').json(), ' B:', b.get('/me/').json())
""")
print(o); R['nokeep'] = o
o = run("""
a = Client(); b = Client(); a.login(username='u', password='old'); b.login(username='u', password='old')
a.get('/change/?p=new2&keep=1')
print('A 上改密码并调用 update_session_auth_hash(request, user) 之后 A:', a.get('/me/').json(), ' B:', b.get('/me/').json())
""")
print(o); R['keep'] = o
print()
print('== 三:每次请求怎么校验:用户表里的密码哈希 vs session 里存的 hash(get_user 里的 constant_time_compare)')
o = run("""
from django.db import connection
from django.test.utils import CaptureQueriesContext
c = Client(); c.login(username='u', password='old')
with CaptureQueriesContext(connection) as q: c.get('/me/')
print('一个已登录请求的查询:', len(q), '次(session + user);校验 hash 不额外查询')
""")
print(o); R['queries'] = o
print()
print('== 四:管理员重置密码 / 直接改库里的 password 字段,同样会让所有 session 失效;而只改 last_login 等字段不会')
o = run("""
c = Client(); c.login(username='u', password='old')
User.objects.filter(username='u').update(last_login=None); print('只改 last_login 之后:', c.get('/me/').json())
from django.contrib.auth.hashers import make_password
User.objects.filter(username='u').update(password=make_password('old')); print('重新哈希同一个密码('+'盐不同'+')之后:', c.get('/me/').json())
""")
print(o); R['reset'] = o
print()
print('== 五:登出所有设备:改变 session hash 的另一个办法——最直接的是删除该用户所有 session')
o = run("""
a = Client(); b = Client(); a.login(username='u', password='old'); b.login(username='u', password='old')
n = 0
for s in Session.objects.all():
    if s.get_decoded().get('_auth_user_id') == str(User.objects.get(username='u').pk): s.delete(); n += 1
print('删除了', n, '个 session;A:', a.get('/me/').json(), ' B:', b.get('/me/').json())
""")
print(o); R['purge'] = o
save('d80', R)
