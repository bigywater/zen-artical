import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d76'); R = {}
backends = '''
import os
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
def log(s):
    with open(os.environ['BE_LOG'], 'a') as f: f.write(s + '\\n')
class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kw):
        log(f'EmailBackend.authenticate(username={username!r})')
        U = get_user_model()
        try: user = U.objects.get(email__iexact=username)
        except U.DoesNotExist: return None
        return user if user.check_password(password) and self.user_can_authenticate(user) else None
class TokenBackend:
    def authenticate(self, request, token=None, **kw):
        log(f'TokenBackend.authenticate(token={token!r})')
        if token is None: return None
        if token == 'banned': raise PermissionDenied
        return get_user_model().objects.filter(username='tok').first() if token == 'good' else None
    def get_user(self, user_id): return get_user_model().objects.filter(pk=user_id).first()
class LoggingModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kw):
        log(f'ModelBackend.authenticate(username={username!r})'); return super().authenticate(request, username, password, **kw)
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions']
d = proj('d76', files={'proj/be.py': backends}, apps=apps, with_lab=False, settings_extra="\nAUTHENTICATION_BACKENDS = ['proj.be.TokenBackend', 'proj.be.LoggingModelBackend', 'proj.be.EmailBackend']\n")
manage(d, 'migrate'); LG = str(DJ / 'd76' / 'be.log')
def run(code): open(LG, 'w').close(); rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.contrib.auth import authenticate, login, get_user_model, load_backend\nfrom django.contrib.auth.models import User\nfor n, e in (('u', 'u@x.com'), ('tok', 't@x.com')):\n    User.objects.filter(username=n).delete(); User.objects.create_user(n, e, 'pw')\ndef L():\n    x = open(__import__('os').environ['BE_LOG']).read().splitlines(); open(__import__('os').environ['BE_LOG'], 'w').close(); return x\nL()\n" + code, BE_LOG=LG); return out.rstrip()
print('== 一:AUTHENTICATION_BACKENDS = [Token, Model, Email]:authenticate() 依次尝试;不匹配的参数签名会被跳过')
o = run("""
u = authenticate(username='u', password='pw'); print('username/password 登录 → ', u, ' 调用日志:', L())
u = authenticate(username='u@x.com', password='pw'); print('用邮箱 → ', u, ' 调用日志:', L())
u = authenticate(token='good'); print('token=good → ', u, ' 调用日志:', L())
u = authenticate(username='u', password='bad'); print('密码错 → ', u, ' 调用日志:', L())
""")
print(o); R['order'] = o
print()
print('== 二:某个后端抛 PermissionDenied 会立刻终止,不再试后面的')
o = run("""
u = authenticate(token='banned'); print('token=banned → ', u, ' 调用日志:', L())
""")
print(o); R['denied'] = o
print()
print('== 三:多个后端时 login() 需要知道用的是哪个:session 里记录后端路径')
o = run("""
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
rf = RequestFactory(); req = rf.get('/'); req.session = SessionStore()
user = User.objects.get(username='u')
try: login(req, user)
except ValueError as e: print('直接 login(user)(没有 backend 属性、没有 backend 参数):', type(e).__name__ + ':', str(e)[:120])
au = authenticate(username='u', password='pw'); print('authenticate 返回的 user.backend =', au.backend); login(req, au); print('session[_auth_user_backend] =', req.session['_auth_user_backend'])
req2 = rf.get('/'); req2.session = SessionStore(); login(req2, user, backend='proj.be.EmailBackend'); print('显式 backend 参数:', req2.session['_auth_user_backend'])
""")
print(o); R['login'] = o
print()
print('== 四:后端里 get_user() 的用途:每个请求用 session 里记录的后端取回用户')
o = run("""
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user
rf = RequestFactory(); req = rf.get('/'); req.session = SessionStore(); au = authenticate(username='u', password='pw'); login(req, au)
print('get_user(request) →', get_user(req), '(通过 session 里记录的后端 ModelBackend.get_user)')
req.session['_auth_user_backend'] = 'proj.be.TokenBackend'; print('把 session 里的后端改成 TokenBackend 后 get_user →', get_user(req), '(该后端的 get_user 也能取到,session hash 仍校验)')
req.session['_auth_user_backend'] = 'no.such.Backend'
try: print(get_user(req))
except Exception as e: print('后端路径不存在 →', type(e).__name__)
""")
print(o); R['get_user'] = o
save('d76', R)
