import sys, os, time, json, re, subprocess, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d126'); R = {}
urls = '''
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt, xframe_options_sameorigin, xframe_options_deny
from django.views.decorators.csp import csp_override
from django.utils.csp import CSP
def page(name): return HttpResponse(f'<html><body style="background:#cfe"><h3>{name} 页面内容</h3></body></html>')
def default(r): return page('default')
@xframe_options_sameorigin
def same(r): return page('sameorigin')
@xframe_options_exempt
def exempt(r): return page('exempt')
@xframe_options_exempt
@csp_override({'frame-ancestors': [CSP.SELF]})
def csp_self(r): return page('exempt + CSP frame-ancestors self')
@xframe_options_exempt
@csp_override({'frame-ancestors': [CSP.NONE]})
def csp_none(r): return page('exempt + CSP frame-ancestors none')
def parent(r):
    items = [('default', 'X-Frame-Options: DENY(全局默认)'), ('same', '@xframe_options_sameorigin'), ('exempt', '@xframe_options_exempt'), ('csp_self', "exempt + CSP frame-ancestors 'self'"), ('csp_none', "exempt + CSP frame-ancestors 'none'")]
    host = r.get_host()
    other = 'localhost:%s' % r.get_port() if host.startswith('127.') else '127.0.0.1:%s' % r.get_port()
    html = '<html><body><h2>父页面 ' + host + '</h2>'
    for n, label in items:
        html += f'<p>{label}</p><p>同源 iframe:<br><iframe id="same_{n}" src="/{n}/" width="320" height="60"></iframe> 跨源 iframe({other}):<br><iframe id="cross_{n}" src="http://{other}/{n}/" width="320" height="60"></iframe></p>'
    return HttpResponse(html + '</body></html>')
def ping(r): return HttpResponse('ok')
urlpatterns = [path('default/', default), path('same/', same), path('exempt/', exempt), path('csp_self/', csp_self), path('csp_none/', csp_none), path('parent/', parent), path('ping/', ping)]
'''
MW = ['django.middleware.security.SecurityMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware', 'django.middleware.csp.ContentSecurityPolicyMiddleware']
d = proj('d126', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=MW, settings_extra=ES)
print('== 一:服务端发出的头(Client,未在浏览器里)')
o = srun(d, """
c = Client()
for p in ('default', 'same', 'exempt', 'csp_self', 'csp_none'):
    r = c.get(f'/{p}/', HTTP_HOST='localhost'); print(f'  /{p + "/":<11} X-Frame-Options: {r.headers.get("X-Frame-Options", "(没有)"):<12} Content-Security-Policy: {r.headers.get("Content-Security-Policy", "(没有)")}')
""", ALLOWED_HOSTS=['*'])
print(o); R['headers'] = o
print()
print('== 二:X_FRAME_OPTIONS 的取值')
o = srun(d, """
c = Client()
for v in ('DENY', 'SAMEORIGIN'):
    from django.test import override_settings
    with override_settings(X_FRAME_OPTIONS=v): print(f'  X_FRAME_OPTIONS = {v:<10} → 响应头', c.get('/default/', HTTP_HOST='localhost').headers.get('X-Frame-Options'))
""", ALLOWED_HOSTS=['*'])
print(o); R['values'] = o
print()
print('== 三:起 runserver(9540)供浏览器检查 /parent/')
p = subprocess.Popen([PY, 'manage.py', 'runserver', '127.0.0.1:9540', '--noreload'], cwd=d, env=env(d, EXTRA_SETTINGS=json.dumps({'ALLOWED_HOSTS': ['*']})), stdout=open(d / 'rs.log', 'w'), stderr=subprocess.STDOUT)
for _ in range(100):
    try: c = http.client.HTTPConnection('127.0.0.1', 9540, timeout=1); c.request('GET', '/ping/'); c.getresponse().read(); break
    except Exception: time.sleep(0.2)
print('  runserver 已启动,pid', p.pid)
open(d / 'pid.txt', 'w').write(str(p.pid))
save('d126', R)
