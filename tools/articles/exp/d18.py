import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d18'); R = {}
mw = '''
LOG = []
from django.http import HttpResponse
def make(name, view_returns=None, exc_returns=None, tpl_marks=True):
    class M:
        def __init__(self, get_response): self.get_response = get_response
        def __call__(self, request):
            LOG.append(f'{name}.__call__ 进入'); r = self.get_response(request); LOG.append(f'{name}.__call__ 返回 status={r.status_code}'); return r
        def process_view(self, request, view_func, view_args, view_kwargs):
            LOG.append(f'{name}.process_view(视图={view_func.__name__})')
            if view_returns: LOG.append(f'  {name}.process_view 直接返回响应'); return HttpResponse('from ' + name + '.process_view', status=203)
        def process_exception(self, request, exception):
            LOG.append(f'{name}.process_exception({type(exception).__name__})')
            if exc_returns: LOG.append(f'  {name}.process_exception 返回了响应'); return HttpResponse('handled by ' + name, status=200)
        def process_template_response(self, request, response):
            LOG.append(f'{name}.process_template_response(rendered={response.is_rendered})'); return response
    M.__name__ = name; return M
M1 = make('M1'); M2 = make('M2'); M3 = make('M3')
M2View = make('M2', view_returns=True); M2Exc = make('M2', exc_returns=True)
'''
views = "from django.template.response import TemplateResponse\nfrom django.http import HttpResponse\nfrom proj.mw import LOG\ndef ok(r): LOG.append('view 执行'); return HttpResponse('ok')\ndef bad(r): LOG.append('view 抛出 ValueError'); raise ValueError('x')\ndef tpl(r):\n    LOG.append('view 返回 TemplateResponse(还没渲染)'); return TemplateResponse(r, 'hello.html', {'n': 1})\n"
urls = "from django.urls import path\nfrom proj import views\nurlpatterns = [path('ok/', views.ok), path('bad/', views.bad), path('tpl/', views.tpl)]\n"
def case(title, mwlist, url):
    d = proj('d18', files={'proj/mw.py': mw, 'proj/views.py': views, 'templates/hello.html': "hello {{ n }}"}, urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=mwlist, settings_extra="\nDEBUG = False\n")
    rc, out = pyscript(d, f"import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom proj.mw import LOG\nc = Client(raise_request_exception=False)\nr = c.get('{url}')\nfor l in LOG: print('  ', l)\nprint('   ==> 客户端得到 status =', r.status_code, ' body =', r.content[:30])\n")
    print(f'  [{title}]'); print(out.rstrip()); return out.rstrip()
MW = ['proj.mw.M1', 'proj.mw.M2', 'proj.mw.M3']
print('== 一:三个钩子都不出场时的正常顺序,以及 process_view 的位置')
R['ok'] = case('普通视图', MW, '/ok/')
print()
print('== 二:视图返回 TemplateResponse:process_template_response 的位置与渲染时机')
R['tpl'] = case('TemplateResponse', MW, '/tpl/')
print()
print('== 三:process_view 直接返回响应:视图会不会执行、后面的中间件会不会经过')
R['pv'] = case('M2.process_view 返回响应', ['proj.mw.M1', 'proj.mw.M2View', 'proj.mw.M3'], '/ok/')
print()
print('== 四:视图抛异常:process_exception 的调用顺序,谁返回了响应谁就终止链')
R['exc_all_none'] = case('三个 process_exception 都返回 None', MW, '/bad/')
R['exc_m2'] = case('M2.process_exception 返回响应', ['proj.mw.M1', 'proj.mw.M2Exc', 'proj.mw.M3'], '/bad/')
save('d18', R)
