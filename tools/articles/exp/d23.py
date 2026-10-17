import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d23'); R = {}
urls = '''
import datetime
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.http import condition, etag, last_modified
CALLS = {'n': 0}
LM = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
def expensive(request):
    CALLS['n'] += 1; return HttpResponse('X' * 5000)
def get_etag(request): return '"v1"'
def get_lm(request): return LM
@condition(etag_func=get_etag)
def cond_etag(request): CALLS['n'] += 1; return HttpResponse('X' * 5000)
@condition(last_modified_func=get_lm)
def cond_lm(request): CALLS['n'] += 1; return HttpResponse('X' * 5000)
@condition(etag_func=get_etag, last_modified_func=get_lm)
def cond_both(request): CALLS['n'] += 1; return HttpResponse('X' * 5000)
def calls(request): return HttpResponse(str(CALLS['n']))
urlpatterns = [path('plain/', expensive), path('etag/', cond_etag), path('lm/', cond_lm), path('both/', cond_both), path('calls/', calls)]
'''
d = proj('d23', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=['django.middleware.http.ConditionalGetMiddleware'])
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nc = Client()\ndef calls(): return int(c.get('/calls/').content)\n" + code); return out.rstrip()
print('== 一:ConditionalGetMiddleware 自动生成 ETag,但视图仍然执行')
o = run("""
r = c.get('/plain/'); et = r['ETag']; print('第 1 次: status', r.status_code, ' ETag =', et, ' 体', len(r.content), '字节  视图调用次数', calls())
r = c.get('/plain/', HTTP_IF_NONE_MATCH=et); print('带 If-None-Match:', r.status_code, ' 体', len(r.content), '字节  视图调用次数', calls(), '(视图还是执行了)')
""")
print(o); R['auto'] = o
print()
print('== 二:@condition:提前判断,命中就不执行视图')
o = run("""
r = c.get('/etag/'); print('第 1 次 GET /etag/:', r.status_code, r.headers.get('ETag'), ' 视图调用', calls())
r = c.get('/etag/', HTTP_IF_NONE_MATCH='"v1"'); print('If-None-Match: "v1" →', r.status_code, ' 体', len(r.content), '字节  视图调用', calls(), ' 304 响应头:', dict(r.headers))
r = c.get('/etag/', HTTP_IF_NONE_MATCH='"v2"'); print('If-None-Match: "v2" →', r.status_code, ' 视图调用', calls())
r = c.get('/etag/', HTTP_IF_NONE_MATCH='W/"v1"'); print('If-None-Match: W/"v1"(弱校验器) →', r.status_code)
r = c.get('/etag/', HTTP_IF_NONE_MATCH='*'); print('If-None-Match: * →', r.status_code)
""")
print(o); R['cond'] = o
print()
print('== 三:Last-Modified 与 If-Modified-Since')
o = run("""
r = c.get('/lm/'); print('第 1 次:', r.status_code, ' Last-Modified =', r.headers.get('Last-Modified'), ' 视图调用', calls())
for ims in ('Thu, 01 Jan 2026 12:00:00 GMT', 'Thu, 01 Jan 2026 11:59:59 GMT', 'Thu, 01 Jan 2026 12:00:01 GMT', 'garbage'):
    r = c.get('/lm/', HTTP_IF_MODIFIED_SINCE=ims); print(f'If-Modified-Since: {ims:<32} → {r.status_code}')
print('视图累计调用', calls())
""")
print(o); R['lm'] = o
print()
print('== 四:同时给 ETag 和 Last-Modified:两个条件头同时带,谁说了算')
o = run("""
LMS = 'Thu, 01 Jan 2026 12:00:00 GMT'
for etag, ims in (('"v1"', LMS), ('"v2"', LMS), ('"v1"', 'Thu, 01 Jan 2026 11:00:00 GMT')):
    r = c.get('/both/', HTTP_IF_NONE_MATCH=etag, HTTP_IF_MODIFIED_SINCE=ims); print(f'If-None-Match {etag}  If-Modified-Since {ims[-25:-4]}… → {r.status_code}')
r = c.post('/both/', HTTP_IF_NONE_MATCH='"v1"'); print('POST 带 If-None-Match: "v1" →', r.status_code)
""")
print(o); R['both'] = o
save('d23', R)
