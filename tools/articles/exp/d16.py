import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d16'); R = {}
urls = '''
from django.urls import path, re_path, include, register_converter
from django.http import HttpResponse
def v(r, **k): return HttpResponse('x')
class YearConv:
    regex = '[0-9]{4}'
    def to_python(self, value): return int(value)
    def to_url(self, value): return '%04d' % value
register_converter(YearConv, 'yyyy')
api = [path('users/', v, name='users'), path('users/<int:pk>/', v, name='user')]
urlpatterns = [
    path('post/<int:pk>/', v, name='post'),
    path('post/<slug:slug>/edit/', v, name='post-edit'),
    path('arch/<yyyy:year>/', v, name='arch'),
    path('files/<path:p>', v, name='files'),
    path('opt/', v, name='opt'), path('opt/<int:page>/', v, name='opt'),
    path('dup/one/', v, name='dup'), path('dup/two/', v, name='dup'),
    re_path(r'^re/(?P<a>\\d+)/(?P<b>\\d+)/$', v, name='re'),
    path('api/', include((api, 'api'), namespace='v1')),
    path('api2/', include((api, 'api'), namespace='v2')),
]
'''
d = proj('d16', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False)
print('== 一:reverse() 的各种参数形式')
rc, out = pyscript(d, """
from django.urls import reverse, NoReverseMatch
def t(*a, **k):
    label = 'reverse(%s)' % ', '.join([repr(x) for x in a] + ['%s=%r' % kv for kv in k.items()])
    try: print(f'{label:<64} → {reverse(*a, **k)}')
    except NoReverseMatch as e: print(f'{label:<64} → NoReverseMatch: {str(e)[:170]}')
t('post', args=[5]); t('post', kwargs={'pk': 5}); t('post', args=['5']); t('post', args=['abc']); t('post'); t('post', args=[5, 6]); t('post', kwargs={'pk': 5, 'x': 1})
t('post-edit', kwargs={'slug': 'a b/é'}); t('post-edit', kwargs={'slug': 'ok-slug_1'})
t('arch', kwargs={'year': 7}); t('arch', kwargs={'year': 2026}); t('files', kwargs={'p': 'a b/c d.txt'})
t('re', args=['1', '2']); t('re', kwargs={'a': 1, 'b': 2})
t('nope')
""")
print(out.strip()); R['forms'] = out.strip()
print()
print('== 二:同名多个模式怎么选 / 命名空间')
rc, out = pyscript(d, """
from django.urls import reverse, NoReverseMatch
print('opt(无参数)        →', reverse('opt')); print('opt(page=3)        →', reverse('opt', kwargs={'page': 3}))
print('dup(两个同名同参数) →', reverse('dup'), '  (定义顺序: dup/one/ 在前, dup/two/ 在后)')
print('v1:users →', reverse('v1:users')); print('v2:user  →', reverse('v2:user', args=[3]))
try: reverse('api:users')
except NoReverseMatch as e: print("reverse('api:users') → NoReverseMatch:", str(e)[:120])
print("reverse('api:users', current_app='v2') →", reverse('api:users', current_app='v2'))
""")
print(out.strip()); R['names'] = out.strip()
print()
print('== 三:reverse 的代价:第一次要建反向字典,之后很快;urlconf 越大第一次越慢')
R['perf'] = {}
for N in (10, 1000, 5000):
    body = "from django.urls import path\nfrom django.http import HttpResponse\ndef v(r, **k): return HttpResponse('x')\nurlpatterns = [path(f'p{i}/<int:pk>/', v, name=f'n{i}') for i in range(%d)]\n" % N
    dd = proj('d16c', urls=body, apps=['django.contrib.contenttypes'], with_lab=False)
    rc, out = pyscript(dd, f"""
import time
from django.urls import reverse, get_resolver
t0 = time.perf_counter(); reverse('n0', args=[1]); first = (time.perf_counter() - t0) * 1e3
best = 1e9
for _ in range(5):
    t0 = time.perf_counter()
    for _ in range(2000): reverse('n{N // 2}', args=[1])
    best = min(best, (time.perf_counter() - t0) / 2000 * 1e6)
print(first, best)
""")
    f, b = map(float, out.split()); R['perf'][N] = [f, b]; print(f'  N={N:<5} 第一次 reverse {f:8.2f} ms   之后每次 {b:6.2f} µs')
save('d16', R)
