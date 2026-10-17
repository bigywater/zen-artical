import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d24'); R = {}
LOG = "import os, time\ndef mark(s):\n    with open(os.environ['EV_LOG'], 'a') as f: f.write(f'{s}\\n')\n"
files = {
    'proj/mark.py': LOG,
    'proj/mw.py': "from proj.mark import mark\nclass MW:\n    def __init__(self, get_response):\n        mark('MW.__init__(中间件链在构建 handler 时创建)'); self.get_response = get_response\n    def __call__(self, request): return self.get_response(request)\n",
    'lab/apps.py': "from django.apps import AppConfig\nfrom proj.mark import mark\nclass LabConfig(AppConfig):\n    name = 'lab'\n    def ready(self): mark('LabConfig.ready()')\n",
    'lab/views.py': "import threading\nfrom django.http import HttpResponse\ndef hello(request):\n    return HttpResponse('thread=%s main=%s' % (threading.current_thread().name, threading.current_thread() is threading.main_thread()))\nasync def ahello(request):\n    return HttpResponse('async thread=%s main=%s' % (threading.current_thread().name, threading.current_thread() is threading.main_thread()))\n",
    'proj/urls.py': "from django.urls import path\nfrom lab import views\nurlpatterns = [path('hello/', views.hello), path('ahello/', views.ahello)]\n",
}
d = proj('d24', files=files, apps=['django.contrib.contenttypes', 'lab.apps.LabConfig'], middleware=['proj.mw.MW'])
def fresh(): p = str(DJ / 'd24' / 'ev.log'); open(p, 'w').close(); return p
def L(p): return open(p).read().splitlines()
print('== 一:导入 wsgi.py / asgi.py 时发生了什么(不发任何请求)')
R['import'] = {}
for kind, mod, fn in (('WSGI', 'proj.wsgi', 'application'), ('ASGI', 'proj.asgi', 'application')):
    lg = fresh(); rc, out = py(d, f"import importlib\nfrom django.apps import apps\nm = importlib.import_module('{mod}')\napp = m.application\nprint(type(app).__module__ + '.' + type(app).__name__)\nprint('apps.ready =', apps.ready)\n", EV_LOG=lg)
    R['import'][kind] = dict(cls=out.strip().splitlines()[0], ready=out.strip().splitlines()[1], events=L(lg))
    print(f'  {kind}:import {mod} 之后 →', out.strip().splitlines()[0], '|', out.strip().splitlines()[1], '| 事件:', L(lg))
print()
print('== 二:调用约定:WSGI 是 (environ, start_response),ASGI 是 (scope, receive, send)')
rc, out = py(d, EV_LOG=fresh(), code="""
import inspect, asyncio
from proj.wsgi import application as w
from proj.asgi import application as a
print('WSGIHandler.__call__ 签名  :', inspect.signature(type(w).__call__))
print('ASGIHandler.__call__ 签名  :', inspect.signature(type(a).__call__), ' 是协程函数:', inspect.iscoroutinefunction(type(a).__call__))
""")
print('  ' + out.strip().replace('\n', '\n  ')); R['sig'] = out.strip()
print()
print('== 三:同一个同步视图和一个 async 视图,分别在 WSGI / ASGI 下执行时所在的线程')
rc, out = py(d, EV_LOG=fresh(), code="""
import io, asyncio, sys
from wsgiref.util import setup_testing_defaults
from proj.wsgi import application as w
from proj.asgi import application as a
def call_wsgi(path):
    env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': path, 'wsgi.input': io.BytesIO(b'')}; setup_testing_defaults(env); env['PATH_INFO'] = path
    got = {}
    def sr(status, headers, exc_info=None): got['status'] = status
    body = b''.join(w(env, sr)); return got['status'], body.decode()
async def call_asgi(path):
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET', 'path': path, 'raw_path': path.encode(), 'query_string': b'', 'headers': [(b'host', b'testserver')], 'server': ('testserver', 80), 'client': ('127.0.0.1', 1), 'scheme': 'http', 'root_path': ''}
    msgs = []
    n = [0]
    async def receive():
        n[0] += 1
        if n[0] == 1: return {'type': 'http.request', 'body': b'', 'more_body': False}
        await asyncio.sleep(3600)
    async def send(m): msgs.append(m)
    await a(scope, receive, send)
    return msgs[0]['status'], b''.join(m.get('body', b'') for m in msgs[1:]).decode()
print('WSGI  同步视图 →', call_wsgi('/hello/'))
print('WSGI  async 视图 →', call_wsgi('/ahello/'))
print('ASGI  同步视图 →', asyncio.run(call_asgi('/hello/')))
print('ASGI  async 视图 →', asyncio.run(call_asgi('/ahello/')))
""")
print('  ' + out.strip().replace('\n', '\n  ')); R['threads'] = out.strip()
print()
print('== 四:ASGI 服务器会发 lifespan 事件,Django 自带的 ASGIHandler 怎么处理')
rc, out = py(d, EV_LOG=fresh(), code="""
import asyncio
from proj.asgi import application as a
async def go():
    async def receive(): return {'type': 'lifespan.startup'}
    async def send(m): print('send', m)
    try: await a({'type': 'lifespan', 'asgi': {'version': '3.0'}}, receive, send)
    except Exception as e: print(type(e).__name__ + ':', e)
asyncio.run(go())
""")
print('  ' + out.strip().replace('\n', '\n  ')); R['lifespan'] = out.strip()
save('d24', R)
