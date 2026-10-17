import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d95'); R = {}
views = '''
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page, never_cache, cache_control
from django.views.decorators.vary import vary_on_headers, vary_on_cookie
from django.core.cache import cache
CALLS = {'n': 0}
@cache_page(60)
def page(request): CALLS['n'] += 1; return HttpResponse('page %d q=%s' % (CALLS['n'], request.GET.get('q')))
@cache_page(60)
@vary_on_headers('Accept-Language')
def lang(request): CALLS['n'] += 1; return HttpResponse('lang %d %s' % (CALLS['n'], request.headers.get('Accept-Language')))
@cache_page(60)
@vary_on_headers('X-Device')
def device(request): CALLS['n'] += 1; return HttpResponse('device %d %s' % (CALLS['n'], request.headers.get('X-Device')))
@cache_page(60)
def setcookie(request):
    CALLS['n'] += 1; r = HttpResponse('cookie %d' % CALLS['n']); r.set_cookie('sid', 'abc'); return r
@cache_page(60)
def err(request): CALLS['n'] += 1; return HttpResponse('boom', status=500)
@cache_page(60)
def post_ok(request): CALLS['n'] += 1; return HttpResponse('m=%s' % request.method)
def low(request):
    key = 'expensive:' + request.GET.get('id', '0')
    val = cache.get(key)
    if val is None: CALLS['n'] += 1; val = 'computed-%s' % CALLS['n']; cache.set(key, val, 60)
    return HttpResponse(val)
def calls(request): return JsonResponse(CALLS)
urlpatterns = []
'''
urls = "from django.urls import path\nfrom lab import views\nurlpatterns = [path('page/', views.page), path('lang/', views.lang), path('device/', views.device), path('cookie/', views.setcookie), path('err/', views.err), path('post/', views.post_ok), path('low/', views.low), path('calls/', views.calls)]\n"
d = proj('d95', files={'lab/views.py': views}, urls=urls, apps=['django.contrib.contenttypes', 'lab'], settings_extra="\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}\n")
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.core.cache import cache\nfrom lab import views\ncache.clear(); views.CALLS['n'] = 0\nc = Client()\n" + code); return out.rstrip()
print('== 一:cache_page:同一个 URL 第二次命中缓存(视图不执行);查询串不同 = 不同 key;响应头')
o = run("""
r1 = c.get('/page/?q=1'); r2 = c.get('/page/?q=1'); r3 = c.get('/page/?q=2')
print('第 1 次:', r1.content.decode(), ' 第 2 次(同 URL):', r2.content.decode(), ' 换 ?q=2:', r3.content.decode(), ' 视图执行次数:', views.CALLS['n'])
print('响应头 Cache-Control:', r1.headers.get('Cache-Control'), ' Expires:', 'Expires' in r1.headers, ' Vary:', r1.headers.get('Vary'))
print('Cache-Control 里的 max-age 与 cache_page(60) 一致:', 'max-age=60' in r1.headers.get('Cache-Control', ''))
""")
print(o); R['page'] = o
print()
print('== 二:Vary:按请求头区分缓存。自定义头 X-Device 有效;Accept-Language 在 USE_I18N=True 时被忽略(改用当前语言做 key 后缀)')
o = run("""
views.CALLS['n'] = 0
a = c.get('/device/', HTTP_X_DEVICE='phone').content.decode(); b = c.get('/device/', HTTP_X_DEVICE='desktop').content.decode(); a2 = c.get('/device/', HTTP_X_DEVICE='phone').content.decode()
print('X-Device: phone →', a, '| desktop →', b, '| 再 phone →', a2, '| 视图执行次数:', views.CALLS['n'], '(phone 命中缓存,desktop 是另一份)')
views.CALLS['n'] = 0
a = c.get('/lang/', HTTP_ACCEPT_LANGUAGE='en').content.decode(); b = c.get('/lang/', HTTP_ACCEPT_LANGUAGE='zh').content.decode()
print('Accept-Language: en →', a, '| zh →', b, '| 视图执行次数:', views.CALLS['n'], '(zh 拿到了 en 的缓存!因为没有 LocaleMiddleware 切换语言)')
from django.conf import settings; print('USE_I18N =', settings.USE_I18N)
""")
print(o); R['vary'] = o
print()
print('== 三:哪些响应不会被缓存:非 GET/HEAD、状态码不是 200/304、响应带 Set-Cookie(Vary: Cookie 时按 cookie 区分)')
o = run("""
views.CALLS['n'] = 0
c.post('/post/'); c.post('/post/'); print('POST 两次,视图执行次数:', views.CALLS['n'])
views.CALLS['n'] = 0; c.get('/err/'); c.get('/err/'); print('500 响应两次,视图执行次数:', views.CALLS['n'], '(错误响应不缓存)')
views.CALLS['n'] = 0; r = c.get('/cookie/'); r2 = c.get('/cookie/'); print('视图 set_cookie 两次,视图执行次数:', views.CALLS['n'], ' 响应 Vary:', r.headers.get('Vary'), ' 第二次仍带 Set-Cookie:', 'sid' in r2.cookies)
""")
print(o); R['nocache'] = o
print()
print('== 四:低级缓存:自己决定 key 和超时;命中时视图里的计算被跳过')
o = run("""
views.CALLS['n'] = 0
for i in (1, 1, 2, 1): print('id=%d →' % i, c.get('/low/?id=%d' % i).content.decode())
print('计算次数:', views.CALLS['n'])
""")
print(o); R['low'] = o
print()
print('== 五:模板片段缓存 {% cache %}')
d2 = proj('d95b', files={'templates/frag.html': '{% load cache %}{% cache 60 sidebar user_id %}[计算 {{ counter }}]{% endcache %}'}, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}\n")
rc, out = pyscript(d2, """
import logging; logging.disable(logging.CRITICAL)
from django.template.loader import render_to_string
from django.core.cache import cache
cache.clear()
print('user 1, counter=1:', render_to_string('frag.html', {'user_id': 1, 'counter': 1}))
print('user 1, counter=2(命中缓存):', render_to_string('frag.html', {'user_id': 1, 'counter': 2}))
print('user 2, counter=3(另一个 key):', render_to_string('frag.html', {'user_id': 2, 'counter': 3}))
from django.core.cache.utils import make_template_fragment_key
print('片段的 key:', make_template_fragment_key('sidebar', [1]))
""")
print('  ' + out.strip().replace('\n', '\n  ')); R['frag'] = out.strip()
save('d95', R)
