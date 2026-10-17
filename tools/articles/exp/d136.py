import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d136'); R = {}
pg = PG(9476).start()
hc = '''
from django.http import HttpResponse, JsonResponse
from django.db import connection
class HealthCheckMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.path == '/live/': return HttpResponse('ok')
        return self.get_response(request)
def ready(request):
    try:
        with connection.cursor() as c: c.execute('select 1'); c.fetchone()
    except Exception as e:
        return JsonResponse({'ready': False, 'error': type(e).__name__}, status=503)
    return JsonResponse({'ready': True})
def healthz(request): return HttpResponse('ok')
'''
urls = "from django.urls import path\nfrom proj import hc\nurlpatterns = [path('healthz/', hc.healthz), path('ready/', hc.ready)]\n"
d = proj('d136', files={'proj/hc.py': hc}, urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[], settings_extra=ES)
DB = pg.databases()
MWS = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware']
def run(code, **st): return srun(d, code, **dict(dict(ALLOWED_HOSTS=['example.com'], DEBUG=False, SECURE_SSL_REDIRECT=True), **st))
print('== 一:探针(kubelet / 负载均衡)用 Pod IP 作为 Host、走 http,访问一个普通视图 /healthz/:ALLOWED_HOSTS=["example.com"],SECURE_SSL_REDIRECT=True')
o = run("""
c = Client(raise_request_exception=False)
for label, kw in (('Host: 10.0.0.5(Pod IP),http', dict(HTTP_HOST='10.0.0.5')), ('Host: example.com,http', dict(HTTP_HOST='example.com')), ('Host: example.com,https', dict(HTTP_HOST='example.com', secure=True))):
    r = c.get('/healthz/', **kw); print(f'  {label:<32} → {r.status_code} {r.headers.get("Location", "")}')
""", MIDDLEWARE=MWS)
print(o); R['normal'] = o
print()
print('== 二:同一个探针,改成放在 MIDDLEWARE 最前面的 HealthCheckMiddleware(/live/):不检查 Host、不重定向、不碰会话与数据库')
o = run("""
from django.db import connection
from django.test.utils import CaptureQueriesContext
c = Client(raise_request_exception=False)
for label, kw in (('Host: 10.0.0.5,http', dict(HTTP_HOST='10.0.0.5')), ('Host: example.com,http', dict(HTTP_HOST='example.com'))):
    with CaptureQueriesContext(connection) as q: r = c.get('/live/', **kw)
    print(f'  {label:<26} → {r.status_code}  响应 {r.content!r}  数据库查询 {len(q)} 次  Set-Cookie: {"sessionid" in r.cookies}')
""", MIDDLEWARE=['proj.hc.HealthCheckMiddleware'] + MWS, DATABASES=json.loads(json.dumps({'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': pg.port}})))
print(o); R['mw'] = o
print()
print('== 三:就绪探针 /ready/ 检查数据库(select 1):数据库正常 / 数据库停掉之后;同时 /live/ 的表现')
dbs = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': pg.port, 'OPTIONS': {'connect_timeout': 2}}}
code = """
import time
c = Client(raise_request_exception=False)
for path in ('/ready/', '/live/'):
    t0 = time.perf_counter(); r = c.get(path, HTTP_HOST='example.com', secure=True); print(f'  {path:<8} → {r.status_code}  {r.content.decode()[:50]:<44} 用时 {(time.perf_counter() - t0) * 1000:7.1f} ms')
"""
print('  [数据库运行中]'); o = run(code, MIDDLEWARE=['proj.hc.HealthCheckMiddleware'] + MWS, DATABASES=dbs); print(o); R['up'] = o
pg.stop()
print('  [数据库已停止(端口拒绝连接)]'); o = run(code, MIDDLEWARE=['proj.hc.HealthCheckMiddleware'] + MWS, DATABASES=dbs); print(o); R['down'] = o
print()
print('== 四:数据库地址不可达(连接挂起)时,connect_timeout 的作用:连接 10.255.255.1(不会回应的地址),connect_timeout = 2 s')
dbs2 = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '10.255.255.1', 'PORT': 5432, 'OPTIONS': {'connect_timeout': 2}}}
o = run("""
import time
c = Client(raise_request_exception=False)
t0 = time.perf_counter(); r = c.get('/ready/', HTTP_HOST='example.com', secure=True); print(f'  /ready/ → {r.status_code}  {r.content.decode()[:60]}  用时 {(time.perf_counter() - t0) * 1000:.0f} ms')
""", MIDDLEWARE=MWS, DATABASES=dbs2)
print(o); R['blackhole'] = o
save('d136', R)
