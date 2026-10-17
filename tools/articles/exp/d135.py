import sys, os, time, json, re, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
import asrv
tee('d135'); R = {}
logs = '''
import contextvars, uuid, logging
RID = contextvars.ContextVar('rid', default='-')
class RequestIdFilter(logging.Filter):
    def filter(self, record): record.request_id = RID.get(); return True
class RequestIdMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        rid = uuid.uuid4().hex[:8]; RID.set(rid); response = self.get_response(request); response['X-Request-ID'] = rid; return response
'''
urls = '''
import logging
from django.urls import path
from django.http import HttpResponse
log = logging.getLogger('app')
def ping(r): return HttpResponse('ok')
def ok(r): log.info('处理 /ok/'); return HttpResponse('ok')
def boom(r): log.warning('即将出错'); raise RuntimeError('业务出错了')
urlpatterns = [path('ping/', ping), path('ok/', ok), path('boom/', boom)]
'''
d = proj('d135', files={'proj/logs.py': logs}, urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[], settings_extra=ES)
LOGGING = {'version': 1, 'disable_existing_loggers': False,
 'filters': {'rid': {'()': 'proj.logs.RequestIdFilter'}},
 'formatters': {'std': {'format': '%(levelname)s %(name)s rid=%(request_id)s %(message)s'}},
 'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'std', 'filters': ['rid']}},
 'loggers': {'django': {'handlers': ['console'], 'level': 'INFO'}, 'app': {'handlers': ['console'], 'level': 'INFO'}}}
def run_case(port, **st):
    open(d / 'srv.log', 'w').close()
    p = asrv.serve(d, 'gunicorn', port, EXTRA_SETTINGS=json.dumps(dict(ALLOWED_HOSTS=['example.com'], DEBUG=False, **st)))
    try:
        res = {}
        for label, path, host in (('/ok/', '/ok/', 'example.com'), ('/boom/', '/boom/', 'example.com'), ('/不存在/', '/nope/', 'example.com'), ('Host: evil.test', '/ok/', 'evil.test')):
            c = http.client.HTTPConnection('127.0.0.1', port, timeout=10); c.putrequest('GET', path, skip_host=True); c.putheader('Host', host); c.endheaders(); r = c.getresponse(); r.read(); res[label] = (r.status, r.getheader('X-Request-ID'))
        time.sleep(0.5)
    finally: asrv.stop(p)
    return res, open(d / 'srv.log').read()
def show(txt):
    lines = [l for l in txt.splitlines() if l.strip()]
    tb = sum(1 for l in lines if l.startswith('Traceback'))
    print(f'  日志共 {len(lines)} 行,其中 Traceback {tb} 段。非 traceback 的行:')
    for l in lines:
        if l.startswith(('  ', 'Traceback', 'RuntimeError', 'Http404', 'django.')) and not re.match(r'^(WARNING|ERROR|INFO|CRITICAL)', l): continue
        print('    ', l[:120])
print('== 一:没有 LOGGING 配置(Django 默认),DEBUG=False,gunicorn:请求 /ok/、/boom/(抛异常)、不存在的路径、非法 Host')
res, txt = run_case(9590, MIDDLEWARE=['django.middleware.common.CommonMiddleware']); print('  状态码:', {k: v[0] for k, v in res.items()}); show(txt); R['default'] = dict(codes={k: v[0] for k, v in res.items()}, n_lines=len([l for l in txt.splitlines() if l.strip()]), tb=txt.count('Traceback'))
print()
print('== 二:配置 LOGGING:django / app 两个 logger 输出到 stderr(gunicorn 会收集),并带 request_id')
res, txt = run_case(9591, LOGGING=LOGGING, MIDDLEWARE=['proj.logs.RequestIdMiddleware', 'django.middleware.common.CommonMiddleware'])
print('  状态码与响应头里的 X-Request-ID:', {k: v for k, v in res.items()}); show(txt)
rid = res['/boom/'][1]; print(f'  用 X-Request-ID={rid} 过滤:', [l[:90] for l in txt.splitlines() if f'rid={rid}' in l])
R['config'] = dict(codes={k: v[0] for k, v in res.items()}, n_lines=len([l for l in txt.splitlines() if l.strip()]), tb=txt.count('Traceback'), boom_lines=[l[:120] for l in txt.splitlines() if f'rid={rid}' in l])
print()
print('== 三:got_request_exception 信号:错误追踪工具(Sentry 之类)挂钩的位置,不依赖 logging 配置')
o = srun(d, """
from django.core.signals import got_request_exception
SEEN = []
got_request_exception.connect(lambda sender, request, **kw: SEEN.append((request.path, type(__import__('sys').exc_info()[1]).__name__)), weak=False)
c = Client(raise_request_exception=False)
for p in ('/ok/', '/boom/', '/nope/'): c.get(p, HTTP_HOST='example.com')
print('  触发 got_request_exception 的请求:', SEEN, '(/nope/ 是 404,不触发;/boom/ 触发)')
""", ALLOWED_HOSTS=['example.com'], DEBUG=False)
print(o); R['signal'] = o
save('d135', R)
