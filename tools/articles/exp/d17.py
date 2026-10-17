import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d17'); R = {}
mw = '''
LOG = []
def make(name, mode=None):
    class M:
        def __init__(self, get_response): self.get_response = get_response
        def __call__(self, request):
            LOG.append(f'{name} 进入')
            if mode == 'short':
                from django.http import HttpResponse
                LOG.append(f'{name} 直接返回响应(短路)'); return HttpResponse('short-circuit by ' + name, status=202)
            if mode == 'boom': LOG.append(f'{name} 抛出 ValueError'); raise ValueError('boom in ' + name)
            r = self.get_response(request)
            LOG.append(f'{name} 收到响应 status={r.status_code}'); return r
    M.__name__ = name; return M
M1 = make('M1'); M2 = make('M2'); M3 = make('M3')
M2Short = make('M2', 'short'); M2Boom = make('M2', 'boom')
'''
views = "from django.http import HttpResponse, Http404\nfrom proj.mw import LOG\ndef ok(r): LOG.append('view 执行'); return HttpResponse('ok')\ndef bad(r): LOG.append('view 抛出 ValueError'); raise ValueError('boom in view')\ndef nf(r): LOG.append('view 抛出 Http404'); raise Http404('nope')\n"
urls = "from django.urls import path\nfrom proj import views\nurlpatterns = [path('ok/', views.ok), path('bad/', views.bad), path('nf/', views.nf)]\n"
def case(title, mwlist, url, debug=False):
    d = proj('d17', files={'proj/mw.py': mw, 'proj/views.py': views}, urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=mwlist, settings_extra=f"\nDEBUG = {debug}\n")
    rc, out = pyscript(d, f"""
import logging; logging.disable(logging.CRITICAL)
from django.test import Client
from proj.mw import LOG
c = Client(raise_request_exception=False)
r = c.get('{url}')
for l in LOG: print('  ', l)
print('   ==> 客户端得到 status =', r.status_code, ' body 前 40 字节 =', r.content[:40])
""")
    print(f'  [{title}]'); print(out.rstrip()); return out.rstrip()
MW = ['proj.mw.M1', 'proj.mw.M2', 'proj.mw.M3']
print('== 一:正常请求,以及某一层短路')
R['normal'] = case('三层都放行', MW, '/ok/')
R['short'] = case('M2 直接返回响应(短路)', ['proj.mw.M1', 'proj.mw.M2Short', 'proj.mw.M3'], '/ok/')
print()
print('== 二:视图抛出异常:中间件看到的是异常还是响应?')
R['viewbad'] = case('视图抛 ValueError(DEBUG=False)', MW, '/bad/')
R['nf'] = case('视图抛 Http404', MW, '/nf/')
print()
print('== 三:中间件自己抛出异常')
R['mwboom'] = case('M2 在调用 get_response 之前抛出 ValueError', ['proj.mw.M1', 'proj.mw.M2Boom', 'proj.mw.M3'], '/ok/')
print()
print('== 四:DEBUG=True 时,同样的视图异常')
R['debug'] = case('视图抛 ValueError(DEBUG=True)', MW, '/bad/', debug=True)
save('d17', R)
