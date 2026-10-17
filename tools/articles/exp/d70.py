import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d70'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.template import engines
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
def form(request): return HttpResponse(engines['django'].from_string('<form method="post">{% csrf_token %}</form>').render({}, request))
def tok(request): return HttpResponse(get_token(request))
def post(request): return HttpResponse('ok')
from django.contrib.auth import authenticate, login, logout
def login_view(request):
    u = authenticate(username='u', password='p'); login(request, u); return HttpResponse('in')
def logout_view(request):
    logout(request); return HttpResponse('out')
urlpatterns = [path('form/', form), path('tok/', tok), path('post/', post), path('login/', login_view), path('logout/', logout_view)]
'''
d = proj('d70', urls=urls, apps=['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions'], with_lab=False, middleware=['django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware'])
manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.conf import settings\ndef tok_from(html): return re.search(r'value=\"([^\"]+)\"', html).group(1)\n" + code); return out.rstrip()
print('== 一:token 的长度与「每次都不同」:cookie 里存的是 secret,表单里的 token 是每次重新掩码的')
o = run("""
c = Client(enforce_csrf_checks=True)
r1 = c.get('/form/'); t1 = tok_from(r1.content.decode()); ck = c.cookies['csrftoken'].value
r2 = c.get('/form/'); t2 = tok_from(r2.content.decode()); ck2 = c.cookies['csrftoken'].value
print('cookie csrftoken 长度 =', len(ck), ' 两次请求的 cookie 相同:', ck == ck2)
print('表单 token 长度 =', len(t1), ' 两次请求的表单 token 相同:', t1 == t2)
print('CSRF_COOKIE_NAME =', settings.CSRF_COOKIE_NAME, ' CSRF_HEADER_NAME =', settings.CSRF_HEADER_NAME, ' CSRF_USE_SESSIONS =', settings.CSRF_USE_SESSIONS)
""")
print(o); R['token'] = o
print()
print('== 二:两个不同的 token 都能通过校验;POST 缺 token / 错 token 的 403 原因')
o = run("""
c = Client(enforce_csrf_checks=True)
t1 = tok_from(c.get('/form/').content.decode()); t2 = tok_from(c.get('/form/').content.decode())
print('token 不同但都有效:', t1 != t2, [c.post('/post/', {'csrfmiddlewaretoken': t}).status_code for t in (t1, t2)])
r = c.post('/post/', {}); print('没带 token → status', r.status_code, '|', re.sub(r'\\s+', ' ', re.search(r'<p>(.*?)</p>', r.content.decode(), re.S).group(1))[:100] if b'<p>' in r.content else r.content[:100])
r = c.post('/post/', {'csrfmiddlewaretoken': 'x' * 64}); print('错误的 token → status', r.status_code, '|', re.sub(r'\\s+', ' ', re.search(r'<p>(.*?)</p>', r.content.decode(), re.S).group(1))[:100])
c2 = Client(enforce_csrf_checks=True); r = c2.post('/post/', {'csrfmiddlewaretoken': t1}); print('没有 cookie(新会话)但带了别人的 token → status', r.status_code)
r = c.post('/post/', {}, HTTP_X_CSRFTOKEN=t1); print('用请求头 X-CSRFToken 传 token → status', r.status_code)
""")
print(o); R['verify'] = o
print()
print('== 三:GET 不检查;登录 / 退出时 token 会轮换(django.contrib.auth.login 调用 rotate_token)')
o = run("""
from django.contrib.auth.models import User
User.objects.filter(username='u').delete(); User.objects.create_user('u', password='p')
c = Client(enforce_csrf_checks=True)
print('GET 不检查 CSRF:', c.get('/tok/').status_code)
t = tok_from(c.get('/form/').content.decode()); c1 = c.cookies['csrftoken'].value
r = c.post('/login/', {'csrfmiddlewaretoken': t}); c2 = c.cookies['csrftoken'].value
print('POST /login/ →', r.status_code, r.content.decode(), ' 登录前后 csrftoken cookie 相同:', c1 == c2, ' 前:', c1[:8] + '…', ' 后:', c2[:8] + '…')
print('登录前拿到的旧表单 token 还能用吗:', c.post('/post/', {'csrfmiddlewaretoken': t}).status_code)
t2 = tok_from(c.get('/form/').content.decode()); print('用登录后的新 token:', c.post('/post/', {'csrfmiddlewaretoken': t2}).status_code)
r = c.post('/logout/', {'csrfmiddlewaretoken': t2}); c3 = c.cookies['csrftoken'].value; print('POST /logout/ →', r.status_code, ' 退出前后 cookie 相同:', c2 == c3)
""")
print(o); R['rotate'] = o
save('d70', R)
