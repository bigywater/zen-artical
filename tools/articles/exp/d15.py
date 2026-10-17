import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d15'); R = {}
urls = '''
from django.urls import path, re_path, include
from django.http import HttpResponse
def v(name):
    def f(request, **kw): return HttpResponse(name)
    f.__name__ = name; return f
api = [path('users/', v('users_list'), name='users'), path('users/<int:pk>/', v('user_detail'), name='user')]
urlpatterns = [
    path('a/<int:pk>/', v('a_int')),
    path('a/new/', v('a_new')),
    path('a/<str:s>/', v('a_str')),
    path('b/<slug:s>/', v('b_slug')),
    path('c/<path:p>', v('c_path')),
    path('u/<uuid:u>/', v('u_uuid')),
    re_path(r'^r/(?P<year>[0-9]{4})/$', v('r_year')),
    path('api/v1/', include((api, 'api'), namespace='v1')),
    path('first/', v('first')), path('first/', v('first_shadowed')),
]
'''
d = proj('d15', urls=urls, middleware=['django.middleware.common.CommonMiddleware'], apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nDEBUG = False\n")
def run(code): rc, out = pyscript(d, code); return out.strip()
print('== 一:顺序决定一切:第一个匹配的模式胜出')
o = run("""
from django.urls import resolve, Resolver404
for u in ('/a/5/', '/a/new/', '/a/abc/', '/a/5', '/first/', '/b/my-slug_1/', '/b/has space/', '/c/x/y/z', '/c/x/y/z/', '/u/123e4567-e89b-12d3-a456-426614174000/', '/u/not-a-uuid/', '/r/2026/', '/r/26/', '/nothing/'):
    try:
        m = resolve(u); print(f'{u:<44} → {m.func.__name__:<14} kwargs={m.kwargs}')
    except Resolver404: print(f'{u:<44} → Resolver404')
""")
print(o); R['resolve'] = o
print()
print('== 二:ResolverMatch 与 include() 的命名空间')
o = run("""
from django.urls import resolve
m = resolve('/api/v1/users/7/')
print('func      =', m.func.__name__); print('route     =', m.route); print('url_name  =', m.url_name); print('namespace =', repr(m.namespace)); print('app_names =', m.app_names); print('kwargs    =', m.kwargs); print('view_name =', m.view_name)
""")
print(o); R['match'] = o
print()
print('== 三:结尾斜杠:APPEND_SLASH + CommonMiddleware')
o = run("""
import logging; logging.disable(logging.CRITICAL)
from django.test import Client
c = Client()
for u in ('/a/new/', '/a/new', '/a/new?x=1', '/first'):
    r = c.get(u); print(f'GET {u:<14} → {r.status_code}', ('Location: ' + r['Location']) if r.status_code in (301, 302) else '')
r = c.post('/a/new', {'x': 1}); print('POST /a/new       →', r.status_code)
""")
print(o); R['slash'] = o
d2 = proj('d15b', urls=urls, middleware=['django.middleware.common.CommonMiddleware'], apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nDEBUG = True\n")
rc, out = pyscript(d2, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nc = Client(raise_request_exception=False)\ntry:\n    r = c.post('/a/new', {'x': 1}); print('DEBUG=True 时 POST /a/new →', r.status_code)\nexcept Exception as e: print('DEBUG=True 时 POST /a/new 抛出', type(e).__name__)\n")
R['slash_post_debug'] = out.strip()
rc, out = pyscript(d2, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nc = Client()\ntry:\n    c.post('/a/new', {'x': 1})\nexcept Exception as e: print(type(e).__name__ + ':', str(e).splitlines()[0][:200])\n"); print('  DEBUG=True 时异常原文:', out.strip()); R['slash_post_err'] = out.strip()
print()
print('== 四:模式越多越慢吗?N 个 path() 的 urlconf,匹配第 1 个 / 中间 / 最后一个 / 完全不匹配(404)的耗时')
R['perf'] = {}
for N in (10, 100, 1000, 5000):
    body = "from django.urls import path\nfrom django.http import HttpResponse\ndef v(r, **k): return HttpResponse('x')\nurlpatterns = [path('p%d/', v) for i in range(N)]\n".replace('%d', '{i}').replace("'p{i}/'", "f'p{i}/'").replace('range(N)', f'range({N})')
    dd = proj('d15c', urls=body, apps=['django.contrib.contenttypes'], with_lab=False)
    rc, out = pyscript(dd, f"""
import time
from django.urls import resolve, Resolver404
N = {N}
resolve('/p0/')
def t(u, rep=300):
    best = 1e9
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(rep):
            try: resolve(u)
            except Resolver404: pass
        best = min(best, (time.perf_counter() - t0) / rep * 1e6)
    return best
print(t('/p0/'), t('/p%d/' % (N // 2)), t('/p%d/' % (N - 1)), t('/nomatch/'))
""")
    a, b, c_, e = map(float, out.split()); R['perf'][N] = [a, b, c_, e]
    print(f'  N={N:<5} 第 1 个 {a:8.1f} µs   中间 {b:8.1f} µs   最后 {c_:8.1f} µs   不匹配 {e:8.1f} µs')
save('d15', R)
