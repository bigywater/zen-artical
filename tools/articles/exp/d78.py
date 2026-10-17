import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d78'); R = {}
views = '''
from django.http import HttpResponse
from django.views import View
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
@login_required
def secret(request): return HttpResponse('secret')
@permission_required('auth.add_user')
def perm_redirect(request): return HttpResponse('perm ok')
@permission_required('auth.add_user', raise_exception=True)
def perm_403(request): return HttpResponse('perm ok')
@user_passes_test(lambda u: u.is_staff, login_url='/nostaff/')
def staff_only(request): return HttpResponse('staff ok')
class CBV(LoginRequiredMixin, View):
    def get(self, request): return HttpResponse('cbv ok')
class PCBV(PermissionRequiredMixin, View):
    permission_required = 'auth.add_user'
    def get(self, request): return HttpResponse('pcbv ok')
def login_page(request): return HttpResponse('login page next=%s' % request.GET.get('next'))
'''
urls = "from django.urls import path\nfrom lab import views\nurlpatterns = [path('secret/', views.secret), path('perm-redirect/', views.perm_redirect), path('perm-403/', views.perm_403), path('staff/', views.staff_only), path('cbv/', views.CBV.as_view()), path('pcbv/', views.PCBV.as_view()), path('accounts/login/', views.login_page)]\n"
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'lab']
d = proj('d78', files={'lab/views.py': views}, urls=urls, apps=apps, middleware=['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware'], settings_extra="\nLOGIN_URL = '/accounts/login/'\n"); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.contrib.auth.models import User\nfor n in ('u', 'p'): User.objects.filter(username=n).delete()\nUser.objects.create_user('u', password='x'); User.objects.create_superuser('p', password='x')\ndef show(c, url):\n    r = c.get(url); return f'GET {url:<26} → {r.status_code}' + (f'  Location: {r[\"Location\"]}' if r.status_code in (301, 302) else '')\n" + code); return out.rstrip()
print('== 一:匿名访问:login_required 重定向到 LOGIN_URL 并带 next 参数')
o = run("""
c = Client()
for url in ('/secret/', '/cbv/', '/perm-redirect/', '/perm-403/', '/staff/', '/secret/?x=1&y=2'): print(show(c, url))
""")
print(o); R['anon'] = o
print()
print('== 二:已登录但权限不足:permission_required 默认又重定向去登录页(循环感),raise_exception=True 才是 403')
o = run("""
c = Client(); c.login(username='u', password='x')
for url in ('/secret/', '/perm-redirect/', '/perm-403/', '/pcbv/', '/staff/'): print(show(c, url))
""")
print(o); R['noperm'] = o
print()
print('== 三:有权限的超级用户;登录页收到的 next 是什么')
o = run("""
c = Client(); c.login(username='p', password='x')
for url in ('/secret/', '/perm-redirect/', '/perm-403/', '/pcbv/', '/staff/'): print(show(c, url))
c2 = Client(); r = c2.get('/secret/?x=1&y=2', follow=True); print('follow=True 之后落在:', r.redirect_chain, r.content.decode())
""")
print(o); R['ok'] = o
print()
print('== 四:url_has_allowed_host_and_scheme 对各种 next 的判断(Django 的 LoginView 用它过滤 next;本文没有实测 LoginView 本身)')
o = run("""
from django.utils.http import url_has_allowed_host_and_scheme as ok
for nxt in ('/dashboard/', '//evil.com/', 'https://evil.com/x', 'https://testserver/x', 'javascript:alert(1)'):
    print(f'{nxt:<26} → 允许跳转: {ok(nxt, allowed_hosts={"testserver"})}')
""")
print(o); R['next'] = o
save('d78', R)
