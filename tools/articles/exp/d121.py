import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d121'); R = {}
urls = "from django.urls import path\nfrom django.http import HttpResponse\nurlpatterns = [path('', lambda r: HttpResponse('hello'))]\n"
MW = ['django.middleware.security.SecurityMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
d = proj('d121', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=MW, settings_extra=ES)
SH = "SHOW = ['X-Content-Type-Options', 'Referrer-Policy', 'Cross-Origin-Opener-Policy', 'X-Frame-Options', 'Strict-Transport-Security', 'Content-Security-Policy', 'Content-Security-Policy-Report-Only']\ndef show(r):\n    for h in SHOW: print(f'  {h:<34} {r.headers.get(h, \"(没有)\")}')\n"
print('== 一:默认设置(SecurityMiddleware + XFrameOptionsMiddleware)的响应头')
o = srun(d, SH + "show(Client().get('/', HTTP_HOST='localhost'))", ALLOWED_HOSTS=['*'])
print(o); R['default'] = o
print()
print('== 二:HSTS:只在 HTTPS 响应上才有这个头(SECURE_HSTS_SECONDS=31536000,include_subdomains,preload)')
o = srun(d, "c = Client()\nfor label, kw in (('https 请求', dict(secure=True)), ('http 请求', dict(secure=False))):\n    r = c.get('/', HTTP_HOST='localhost', **kw); print(f'  {label:<10} status {r.status_code}  Strict-Transport-Security: {r.headers.get(\"Strict-Transport-Security\", \"(没有)\")}')\n", ALLOWED_HOSTS=['*'], SECURE_HSTS_SECONDS=31536000, SECURE_HSTS_INCLUDE_SUBDOMAINS=True, SECURE_HSTS_PRELOAD=True)
print(o); R['hsts'] = o
print()
print('== 三:SECURE_SSL_REDIRECT:http 请求被 301 到 https;SECURE_REDIRECT_EXEMPT 可以豁免路径')
o = srun(d, "c = Client()\nfor path in ('/', '/healthz/'):\n    r = c.get(path, HTTP_HOST='localhost', secure=False); print(f'  http GET {path:<10} → {r.status_code}  Location: {r.headers.get(\"Location\", \"(无)\")}')\n", ALLOWED_HOSTS=['*'], SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r'^healthz/$'])
print(o); R['redirect'] = o
print()
print('== 四:manage.py check --deploy:默认设置(DEBUG=False,密钥是实验用的短密钥)vs 加固之后')
def ids(out): return sorted(set(re.findall(r'security\.W\d+', out)))
rc, out1 = smanage(d, 'check', '--deploy', DEBUG=False, ALLOWED_HOSTS=['example.com'])
rc, out2 = smanage(d, 'check', '--deploy', DEBUG=False, ALLOWED_HOSTS=['example.com'], SECRET_KEY='k' * 60 + '7Zq#p9!xv$2LmN8@rT5&wY', SECURE_HSTS_SECONDS=31536000, SECURE_HSTS_INCLUDE_SUBDOMAINS=True, SECURE_HSTS_PRELOAD=True, SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
print('  默认:', len(ids(out1)), '条警告', ids(out1)); print('  加固后:', len(ids(out2)), '条警告', ids(out2))
R['check'] = [ids(out1), ids(out2)]
print('  默认时各警告的含义(每条第一行):')
for m in re.finditer(r'\?: \((security\.W\d+)\) (.+)', out1): print(f'    {m.group(1)}  {m.group(2)[:95]}')
print()
print('== 五:Django 6 内置的 CSP 中间件:SECURE_CSP 与 SECURE_CSP_REPORT_ONLY')
mw = MW + ['django.middleware.csp.ContentSecurityPolicyMiddleware']
o = srun(d, SH + "show(Client().get('/', HTTP_HOST='localhost'))", ALLOWED_HOSTS=['*'], MIDDLEWARE=mw, SECURE_CSP={'default-src': ["'self'"], 'frame-ancestors': ["'none'"]}, SECURE_CSP_REPORT_ONLY={'default-src': ["'self'"], 'img-src': ['https:']})
print(o); R['csp'] = o
save('d121', R)
