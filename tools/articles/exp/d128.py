import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d128'); R = {}
urls = "from django.urls import path\nfrom django.http import HttpResponse\nfrom django.middleware.csrf import get_token\ndef who(r): return HttpResponse('user=' + (r.user.username if r.user.is_authenticated else 'anonymous'))\ndef token(r): return HttpResponse(get_token(r))\ndef post(r): return HttpResponse('posted')\nurlpatterns = [path('who/', who), path('token/', token), path('post/', post)]\n"
MW = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware']
d = proj('d128', urls=urls, apps=['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions'], with_lab=False, middleware=MW, settings_extra=ES)
manage(d, 'migrate')
PRE = "from django.test import override_settings\nfrom django.contrib.auth import get_user_model\nU = get_user_model(); U.objects.filter(username='ann').delete(); user = U.objects.create_user('ann', password='pw-12345')\nA, B = 'key-A-' + 'a' * 50, 'key-B-' + 'b' * 50\n"
def run(code, **st): return srun(d, PRE + code, **st)
print('== 一:signing(签名数据):用密钥 A 签名,用密钥 B / B + fallback A 校验')
o = run("""
from django.core import signing
with override_settings(SECRET_KEY=A): s = signing.dumps({'order': 7})
print('  签名串(前 40 字符):', s[:40] + '…')
for label, st in (('同一个密钥 A', dict(SECRET_KEY=A)), ('换成密钥 B', dict(SECRET_KEY=B)), ('密钥 B + SECRET_KEY_FALLBACKS=[A]', dict(SECRET_KEY=B, SECRET_KEY_FALLBACKS=[A]))):
    with override_settings(**st):
        try: print(f'  {label:<34} → loads 得到', signing.loads(s))
        except signing.BadSignature as e: print(f'  {label:<34} → BadSignature:', str(e)[:50])
""", ALLOWED_HOSTS=['*'])
print(o); R['signing'] = o
print()
print('== 二:已登录用户的会话(数据库会话后端):换密钥之后还登录着吗?')
o = run("""
c = Client()
with override_settings(SECRET_KEY=A):
    print('  登录(密钥 A):', c.login(username='ann', password='pw-12345'), ' /who/ →', c.get('/who/', HTTP_HOST='x').content.decode())
for label, st in (('换成密钥 B', dict(SECRET_KEY=B)), ('密钥 B + fallback A', dict(SECRET_KEY=B, SECRET_KEY_FALLBACKS=[A]))):
    with override_settings(**st): print(f'  {label:<22} → /who/ →', c.get('/who/', HTTP_HOST='x').content.decode())
from django.contrib.sessions.models import Session
print('  数据库里的会话行数(换密钥没有删除它们):', Session.objects.count())
""", ALLOWED_HOSTS=['*'])
print(o); R['session'] = o
print()
print('== 三:密码重置令牌')
o = run("""
from django.contrib.auth.tokens import default_token_generator as g
with override_settings(SECRET_KEY=A): tok = g.make_token(user)
for label, st in (('密钥 A', dict(SECRET_KEY=A)), ('密钥 B', dict(SECRET_KEY=B)), ('密钥 B + fallback A', dict(SECRET_KEY=B, SECRET_KEY_FALLBACKS=[A]))):
    with override_settings(**st): print(f'  {label:<22} → check_token =', g.check_token(user, tok))
""", ALLOWED_HOSTS=['*'])
print(o); R['reset'] = o
print()
print('== 四:不受 SECRET_KEY 影响的东西:密码哈希、CSRF 令牌')
o = run("""
with override_settings(SECRET_KEY=A): user.set_password('pw-new'); user.save()
with override_settings(SECRET_KEY=B): print('  换密钥 B 后用密码登录:', Client().login(username='ann', password='pw-new'))
c = Client(enforce_csrf_checks=True)
with override_settings(SECRET_KEY=A): tok = c.get('/token/', HTTP_HOST='x').content.decode()
with override_settings(SECRET_KEY=B): r = c.post('/post/', {'csrfmiddlewaretoken': tok}, HTTP_HOST='x'); print('  密钥 A 下拿到的 CSRF 令牌,在密钥 B 下 POST →', r.status_code)
""", ALLOWED_HOSTS=['*'])
print(o); R['unaffected'] = o
print()
print('== 五:signed_cookies 会话后端:整个会话内容就在 cookie 里,靠密钥签名')
o = run("""
c = Client()
with override_settings(SECRET_KEY=A):
    print('  登录:', c.login(username='ann', password='pw-12345')); print('  密钥 A:/who/ →', c.get('/who/', HTTP_HOST='x').content.decode(), ' cookie 长度', len(c.cookies['sessionid'].value))
with override_settings(SECRET_KEY=B): print('  密钥 B:/who/ →', c.get('/who/', HTTP_HOST='x').content.decode())
""", ALLOWED_HOSTS=['*'], SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
print(o); R['signed_cookie'] = o
print()
print('== 六:SECRET_KEY 为空')
o = run("""
from django.core.exceptions import ImproperlyConfigured
with override_settings(SECRET_KEY=''):
    try: print(settings.SECRET_KEY)
    except ImproperlyConfigured as e: print('  读取空的 SECRET_KEY →', type(e).__name__ + ':', str(e))
""", ALLOWED_HOSTS=['*'])
print(o); R['empty'] = o
save('d128', R)
