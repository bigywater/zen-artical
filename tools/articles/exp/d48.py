import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d48'); R = {}
models = "from django.db import models\nclass Rec(models.Model):\n    tag = models.CharField(max_length=40)\n"
views = '''
from django.db import transaction
from django.http import HttpResponse, StreamingHttpResponse
from lab.models import Rec
def raise_after_write(request):
    Rec.objects.create(tag='view-write'); raise ValueError('boom')
def five_hundred_after_write(request):
    Rec.objects.create(tag='view-write'); return HttpResponse('nope', status=500)
def ok(request):
    Rec.objects.create(tag='view-write'); return HttpResponse('ok')
@transaction.non_atomic_requests
def non_atomic(request):
    Rec.objects.create(tag='view-write'); raise ValueError('boom')
def in_atomic(request): return HttpResponse('in_atomic_block=%s' % transaction.get_connection().in_atomic_block)
LOG = []
def with_on_commit(request):
    Rec.objects.create(tag='view-write'); transaction.on_commit(lambda: LOG.append('on_commit 回调'))
    LOG.append('视图即将返回响应'); return HttpResponse('x')
def streaming(request):
    def gen():
        yield b'a'; Rec.objects.create(tag='generator-write'); raise ValueError('boom in generator')
    Rec.objects.create(tag='view-write'); return StreamingHttpResponse(gen())
'''
urls = "from django.urls import path\nfrom lab import views\nurlpatterns = [path('raise/', views.raise_after_write), path('500/', views.five_hundred_after_write), path('ok/', views.ok), path('nonatomic/', views.non_atomic), path('inatomic/', views.in_atomic), path('oncommit/', views.with_on_commit), path('stream/', views.streaming)]\n"
mw = "from lab.models import Rec\nclass MW:\n    def __init__(self, g): self.g = g\n    def __call__(self, request):\n        Rec.objects.create(tag='middleware-before-view')\n        r = self.g(request)\n        Rec.objects.create(tag='middleware-after-view')\n        return r\n"
def build(atomic):
    return proj('d48', files={'lab/models.py': models, 'lab/views.py': views, 'proj/mw.py': mw}, urls=urls, apps=['django.contrib.contenttypes', 'lab'], middleware=['proj.mw.MW'], databases="{'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3', 'ATOMIC_REQUESTS': %s}}" % atomic)
code = """
import logging; logging.disable(logging.CRITICAL)
from django.test import Client
from lab.models import Rec
from lab import views
c = Client(raise_request_exception=False)
for url in ('/raise/', '/500/', '/ok/', '/nonatomic/'):
    Rec.objects.all().delete(); r = c.get(url)
    print(f'GET {url:<12} → status {r.status_code};表里留下:', sorted(Rec.objects.values_list('tag', flat=True)))
r = c.get('/inatomic/'); print('视图里 in_atomic_block →', r.content.decode())
Rec.objects.all().delete(); views.LOG.clear()
from django.db import connection
r = c.get('/oncommit/'); print('on_commit 回调是否已经执行(请求返回之后):', views.LOG)
Rec.objects.all().delete(); r = c.get('/stream/')
try: b''.join(r.streaming_content)
except Exception as e: print('遍历流式响应时抛出:', type(e).__name__)
print('流式响应:表里留下:', sorted(Rec.objects.values_list('tag', flat=True)))
"""
R['off'] = {}
for label, val in (('ATOMIC_REQUESTS = False(默认)', False), ('ATOMIC_REQUESTS = True', True)):
    d = build(val); manage(d, 'migrate', '--run-syncdb')
    rc, out = pyscript(d, code); print(f'== {label}'); print(out.rstrip()); R['off'][label] = out.rstrip()
save('d48', R)
