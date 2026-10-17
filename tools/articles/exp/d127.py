import sys, os, time, json, re, ssl, http.client, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
import asrv
tee('d127'); R = {}
urls = "from django.urls import path\nfrom django.http import HttpResponse\ndef home(r): return HttpResponse(f'is_secure={r.is_secure()} scheme={r.scheme}')\ndef ping(r): return HttpResponse('ok')\nurlpatterns = [path('', home), path('ping/', ping)]\n"
MW = ['django.middleware.security.SecurityMiddleware']
d = proj('d127', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=MW, settings_extra=ES)
print('== 一:SECURE_PROXY_SSL_HEADER:Django 如何判断「这是 HTTPS 请求」(模拟 TLS 在代理处终止,Django 只收到 http)')
o = srun(d, """
c = Client()
for label, kw in (('没有代理头', {}), ('X-Forwarded-Proto: https', {'HTTP_X_FORWARDED_PROTO': 'https'}), ('X-Forwarded-Proto: http', {'HTTP_X_FORWARDED_PROTO': 'http'})):
    print(f'  {label:<26} →', c.get('/', HTTP_HOST='localhost', **kw).content.decode())
""", ALLOWED_HOSTS=['*'])
print('  [没有配置 SECURE_PROXY_SSL_HEADER]'); print(o); R['proxy_off'] = o
o = srun(d, """
c = Client()
for label, kw in (('没有代理头', {}), ('X-Forwarded-Proto: https', {'HTTP_X_FORWARDED_PROTO': 'https'}), ('X-Forwarded-Proto: http', {'HTTP_X_FORWARDED_PROTO': 'http'})):
    print(f'  {label:<26} →', c.get('/', HTTP_HOST='localhost', **kw).content.decode())
""", ALLOWED_HOSTS=['*'], SECURE_PROXY_SSL_HEADER=['HTTP_X_FORWARDED_PROTO', 'https'])
print("  [SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')]"); print(o); R['proxy_on'] = o
print('  ↑ 注意第二行:头是谁发的 Django 不知道。如果客户端能直连 Django(或者代理不清除这个头),任何人都能自称 https。')
print()
print('== 二:SECURE_SSL_REDIRECT 放在 TLS 终止代理后面,但没有配置代理头 → 无限重定向')
o = srun(d, """
c = Client()
for hop in range(1, 6):
    r = c.get('/', HTTP_HOST='localhost', secure=False); print(f'  第 {hop} 次(代理每次都用 http 转发给 Django)→', r.status_code, r.headers.get('Location'))
print('  浏览器跟随 Location 再请求,代理仍然以 http 转给 Django,所以永远是 301:重定向循环')
""", ALLOWED_HOSTS=['*'], SECURE_SSL_REDIRECT=True)
print(o); R['loop'] = o
o = srun(d, """
c = Client()
r = c.get('/', HTTP_HOST='localhost', secure=False, HTTP_X_FORWARDED_PROTO='https'); print('  配置了代理头,代理带上 X-Forwarded-Proto: https →', r.status_code, r.content.decode())
""", ALLOWED_HOSTS=['*'], SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=['HTTP_X_FORWARDED_PROTO', 'https'])
print(o); R['loop_fix'] = o
print()
print('== 三:真实的 TLS:gunicorn 加载自签名证书,HTTPS 上有 HSTS 头;对同一端口发明文 HTTP 得不到正常响应')
cert = d / 'cert.pem'; key = d / 'key.pem'
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=localhost'], capture_output=True)
lf = open(d / 'g.log', 'w')
p = subprocess.Popen([str(asrv.BIN / 'gunicorn'), 'proj.wsgi:application', '-b', '127.0.0.1:9541', '--certfile', str(cert), '--keyfile', str(key), '--log-level', 'warning'], cwd=d, env=env(d, EXTRA_SETTINGS=json.dumps({'ALLOWED_HOSTS': ['*'], 'SECURE_HSTS_SECONDS': 31536000, 'SECURE_HSTS_INCLUDE_SUBDOMAINS': True})), stdout=lf, stderr=subprocess.STDOUT)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
for _ in range(100):
    try: c = http.client.HTTPSConnection('127.0.0.1', 9541, timeout=2, context=ctx); c.request('GET', '/ping/'); c.getresponse().read(); break
    except Exception: time.sleep(0.2)
try:
    c = http.client.HTTPSConnection('127.0.0.1', 9541, timeout=5, context=ctx); c.request('GET', '/'); r = c.getresponse(); b = r.read().decode()
    print('  HTTPS GET / →', r.status, b, ' | Strict-Transport-Security:', r.getheader('Strict-Transport-Security')); R['tls'] = dict(status=r.status, hsts=r.getheader('Strict-Transport-Security'), body=b)
    try:
        c = http.client.HTTPConnection('127.0.0.1', 9541, timeout=5); c.request('GET', '/'); r = c.getresponse(); print('  明文 HTTP 发到同一个端口 →', r.status)
    except Exception as e: print('  明文 HTTP 发到同一个 TLS 端口 →', type(e).__name__); R['plain'] = type(e).__name__
finally:
    p.terminate(); p.wait(10)
print()
print('  没有验证的事:浏览器收到 HSTS 之后的行为(记住 max-age、自动把 http 升级成 https、证书错误时不能点击继续),这些发生在浏览器里。')
save('d127', R)
