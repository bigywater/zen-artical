import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d123'); R = {}
urls = "from django.urls import path\nfrom django.http import HttpResponse\nfrom django.middleware.csrf import get_token\ndef token(r): return HttpResponse(get_token(r))\ndef post(r): return HttpResponse('ok')\nurlpatterns = [path('token/', token), path('post/', post)]\n"
MW = ['django.middleware.csrf.CsrfViewMiddleware']
d = proj('d123', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=MW, settings_extra=ES)
CAP = """
import logging
logging.disable(logging.NOTSET)
REC = []
class H(logging.Handler):
    def emit(self, r): REC.append(r.getMessage())
lg = logging.getLogger('django.security.csrf'); lg.addHandler(H()); lg.propagate = False; lg.setLevel(logging.WARNING)
def attempt(label, headers=None, secure=True, host='app.example.com', token_ok=True):
    c = Client(enforce_csrf_checks=True, raise_request_exception=False)
    tok = c.get('/token/', HTTP_HOST=host, secure=secure).content.decode()
    REC.clear()
    data = {'csrfmiddlewaretoken': tok} if token_ok else {}
    r = c.post('/post/', data, HTTP_HOST=host, secure=secure, **(headers or {}))
    import re as _r; _m = _r.match(r'Forbidden \((.*)\): /post/', REC[0]) if REC else None; why = _m.group(1) if _m else (REC[0] if REC else '')
    print(f'  {label:<52} → {r.status_code}  {why[:100]}')
"""
print('== 一:HTTPS 请求(secure=True)的来源检查:Origin / 令牌')
o = srun(d, CAP + """
attempt('Origin 与 Host 同源 (https://app.example.com)', {'HTTP_ORIGIN': 'https://app.example.com'})
attempt('Origin: https://evil.example', {'HTTP_ORIGIN': 'https://evil.example'})
attempt('Origin 同源但缺少令牌', {'HTTP_ORIGIN': 'https://app.example.com'}, token_ok=False)
attempt('Origin: http://app.example.com(协议不同)', {'HTTP_ORIGIN': 'http://app.example.com'})
attempt('Origin: https://app.example.com:8443(端口不同)', {'HTTP_ORIGIN': 'https://app.example.com:8443'})
""", ALLOWED_HOSTS=['*'], DEBUG=False)
print(o); R['origin'] = o
print()
print('== 二:前端在另一个域(https://spa.example.org)调用本站的接口,Origin 不同源 → 需要 CSRF_TRUSTED_ORIGINS')
o = srun(d, CAP + "attempt('Origin: https://spa.example.org', {'HTTP_ORIGIN': 'https://spa.example.org'})", ALLOWED_HOSTS=['*'], DEBUG=False)
print('  [CSRF_TRUSTED_ORIGINS = []]'); print(o); R['trust_no'] = o
o = srun(d, CAP + "attempt('Origin: https://spa.example.org', {'HTTP_ORIGIN': 'https://spa.example.org'})\nattempt('Origin: https://other.example.org', {'HTTP_ORIGIN': 'https://other.example.org'})", ALLOWED_HOSTS=['*'], DEBUG=False, CSRF_TRUSTED_ORIGINS=['https://spa.example.org'])
print("  [CSRF_TRUSTED_ORIGINS = ['https://spa.example.org']]"); print(o); R['trust_yes'] = o
print()
print('== 三:通配符与写法')
o = srun(d, CAP + """
for org in ('https://a.example.org', 'https://a.b.example.org', 'https://example.org', 'http://a.example.org'):
    attempt(f'Origin: {org}', {'HTTP_ORIGIN': org})
""", ALLOWED_HOSTS=['*'], DEBUG=False, CSRF_TRUSTED_ORIGINS=['https://*.example.org'])
print("  [CSRF_TRUSTED_ORIGINS = ['https://*.example.org']]"); print(o); R['wild'] = o
rc, out = smanage(d, 'check', CSRF_TRUSTED_ORIGINS=['spa.example.org'], ALLOWED_HOSTS=['*'])
msg = [l.strip() for l in out.splitlines() if '4_0.E001' in l or 'CSRF_TRUSTED_ORIGINS' in l]
print("  写成不带协议的 'spa.example.org' 时 manage.py check:", msg[0][:150] if msg else out.strip()[:150]); R['noscheme'] = msg[0][:150] if msg else out.strip()[:150]
print()
print('== 四:没有 Origin 头的 HTTPS 请求:看 Referer')
o = srun(d, CAP + """
attempt('没有 Origin、没有 Referer', {})
attempt('Referer: https://app.example.com/form/', {'HTTP_REFERER': 'https://app.example.com/form/'})
attempt('Referer: https://evil.example/x', {'HTTP_REFERER': 'https://evil.example/x'})
""", ALLOWED_HOSTS=['*'], DEBUG=False)
print(o); R['referer'] = o
print()
print('== 五:放在 TLS 终止代理后面:Django 收到的是 http 请求,浏览器发的 Origin 是 https')
o = srun(d, CAP + "attempt('Django 看到 http,浏览器 Origin: https://app.example.com', {'HTTP_ORIGIN': 'https://app.example.com'}, secure=False)", ALLOWED_HOSTS=['*'], DEBUG=False)
print('  [没有设 SECURE_PROXY_SSL_HEADER]'); print(o); R['proxy_no'] = o
o = srun(d, CAP + "attempt('代理加了 X-Forwarded-Proto: https', {'HTTP_ORIGIN': 'https://app.example.com', 'HTTP_X_FORWARDED_PROTO': 'https'}, secure=False)", ALLOWED_HOSTS=['*'], DEBUG=False, SECURE_PROXY_SSL_HEADER=['HTTP_X_FORWARDED_PROTO', 'https'])
print("  [SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')]"); print(o); R['proxy_yes'] = o
save('d123', R)
