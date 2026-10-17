import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d122'); R = {}
urls = "from django.urls import path\nfrom django.http import HttpResponse\ndef home(r): return HttpResponse('host=' + r.get_host() + ' abs=' + r.build_absolute_uri('/reset/abc/'))\nurlpatterns = [path('', home)]\n"
d = proj('d122', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[], settings_extra=ES)
T = "def t(hosts, **kw):\n    c = Client(raise_request_exception=False)\n    for h in hosts:\n        r = c.get('/', HTTP_HOST=h, **kw); import re as _re; _m = _re.search(r'<title>(.*?)</title>', r.content.decode(), _re.S); body = ('[页面标题: ' + _m.group(1).strip() + ']') if _m else r.content.decode()[:70].replace(chr(10), ' ')\n        print(f'  Host: {h:<26} → {r.status_code}  {body}')\n"
print("== 一:DEBUG=False,ALLOWED_HOSTS=['example.com']:各种 Host 头")
o = srun(d, T + "t(['example.com', 'example.com:8000', 'EXAMPLE.com', 'www.example.com', 'example.com.evil.com', 'evil.com'])", DEBUG=False, ALLOWED_HOSTS=['example.com'])
print(o); R['exact'] = o
print()
print("== 二:子域名写法 '.example.com'(匹配 example.com 及任意层子域名)")
o = srun(d, T + "t(['example.com', 'a.example.com', 'a.b.example.com', 'evilexample.com', 'example.com.evil.com'])", DEBUG=False, ALLOWED_HOSTS=['.example.com'])
print(o); R['dot'] = o
print()
print('== 三:ALLOWED_HOSTS 为空:DEBUG=True 与 DEBUG=False')
o = srun(d, "print('DEBUG =', settings.DEBUG)\n" + T + "t(['localhost', '127.0.0.1', '[::1]', 'testserver', 'evil.com'])", DEBUG=True, ALLOWED_HOSTS=[])
print(o); R['empty_dbg'] = o
o = srun(d, "print('DEBUG =', settings.DEBUG)\n" + T + "t(['localhost', '127.0.0.1', 'evil.com'])", DEBUG=False, ALLOWED_HOSTS=[])
print(o); R['empty_prod'] = o
print()
print('== 四:格式不合法的 Host')
o = srun(d, T + "t(['exa mple.com', 'example.com/evil', 'example.com@evil.com', 'example.com:abc', ''])", DEBUG=False, ALLOWED_HOSTS=['*'])
print(o); R['bad'] = o
print()
print('== 五:X-Forwarded-Host:USE_X_FORWARDED_HOST 默认 False 时被忽略;打开后被用作主机名(仍要通过 ALLOWED_HOSTS)')
o = srun(d, "c = Client(raise_request_exception=False)\nfor label, extra in (('只有 Host', {}), ('Host + X-Forwarded-Host: proxy.example.com', {'HTTP_X_FORWARDED_HOST': 'proxy.example.com'}), ('Host + X-Forwarded-Host: evil.com', {'HTTP_X_FORWARDED_HOST': 'evil.com'})):\n    r = c.get('/', HTTP_HOST='example.com', **extra); print(f'  {label:<46} → {r.status_code}  {(r.content.decode()[:60] if r.status_code == 200 else '(400 页面)')}')\n", DEBUG=False, ALLOWED_HOSTS=['example.com', 'proxy.example.com'], USE_X_FORWARDED_HOST=False)
print('  [USE_X_FORWARDED_HOST = False]'); print(o); R['xfh_off'] = o
o = srun(d, "c = Client(raise_request_exception=False)\nfor label, extra in (('只有 Host', {}), ('Host + X-Forwarded-Host: proxy.example.com', {'HTTP_X_FORWARDED_HOST': 'proxy.example.com'}), ('Host + X-Forwarded-Host: evil.com', {'HTTP_X_FORWARDED_HOST': 'evil.com'})):\n    r = c.get('/', HTTP_HOST='example.com', **extra); print(f'  {label:<46} → {r.status_code}  {(r.content.decode()[:60] if r.status_code == 200 else '(400 页面)')}')\n", DEBUG=False, ALLOWED_HOSTS=['example.com', 'proxy.example.com'], USE_X_FORWARDED_HOST=True)
print('  [USE_X_FORWARDED_HOST = True]'); print(o); R['xfh_on'] = o
print()
print("== 六:为什么要校验:ALLOWED_HOSTS=['*'] 时,build_absolute_uri()(比如密码重置邮件里的链接)会用攻击者给的 Host")
o = srun(d, "c = Client()\nr = c.get('/', HTTP_HOST='evil.example'); print('  ALLOWED_HOSTS=[\"*\"]      Host: evil.example →', r.status_code, r.content.decode())\n", DEBUG=False, ALLOWED_HOSTS=['*'])
print(o); R['poison'] = o
o = srun(d, "r = Client(raise_request_exception=False).get('/', HTTP_HOST='evil.example'); print('  ALLOWED_HOSTS=[\"example.com\"] Host: evil.example →', r.status_code)\n", DEBUG=False, ALLOWED_HOSTS=['example.com'])
print(o); R['poison2'] = o
save('d122', R)
