import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d21'); R = {}
d = proj('d21', apps=['django.contrib.contenttypes'], with_lab=False, middleware=['django.middleware.common.CommonMiddleware'], urls="""
import datetime, decimal, uuid
from django.urls import path
from django.http import HttpResponse, JsonResponse
def plain(r): return HttpResponse('hello')
def hdr(r):
    resp = HttpResponse('x'); resp['X-Custom'] = 'a'; resp['x-custom'] = 'b'; resp.headers['X-Other'] = '1'; resp.set_cookie('sid', 'abc', httponly=True, samesite='Lax', max_age=60); return resp
def js(r): return JsonResponse({'when': datetime.datetime(2026, 1, 2, 3, 4, 5), 'price': decimal.Decimal('9.90'), 'id': uuid.UUID(int=1)})
def jlist(r): return JsonResponse([1, 2, 3], safe=False)
def inject(r):
    resp = HttpResponse('x')
    try: resp['X-Evil'] = 'a\\r\\nSet-Cookie: pwned=1'
    except Exception as e: return HttpResponse(type(e).__name__ + ': ' + str(e)[:100])
urlpatterns = [path('plain/', plain), path('hdr/', hdr), path('js/', js), path('jlist/', jlist), path('inject/', inject)]
""")
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nc = Client()\n" + code); return out.rstrip()
print('== 一:一个最普通的 HttpResponse 带哪些响应头')
o = run("r = c.get('/plain/')\nprint('status', r.status_code)\nfor k, v in r.headers.items(): print(f'  {k}: {v}')\nprint('charset =', r.charset)"); print(o); R['plain'] = o
print()
print('== 二:响应头大小写不敏感;赋值覆盖;Cookie 是 Set-Cookie 头')
o = run("r = c.get('/hdr/')\nprint(dict(r.headers))\nprint(\"r['X-Custom'] =\", r['X-Custom'], ' r['+\"'x-CUSTOM']\"+' =', r['x-CUSTOM'])\nprint('Set-Cookie:', r.cookies['sid'].output())\nprint('has_header(\"x-other\") =', r.has_header('x-other'))"); print(o); R['hdr'] = o
print()
print('== 三:JsonResponse:序列化器、safe 参数')
o = run("r = c.get('/js/')\nprint('Content-Type:', r['Content-Type'])\nprint('body:', r.content.decode())\nr = c.get('/jlist/')\nprint('safe=False 的列表:', r.content.decode())\nfrom django.http import JsonResponse\ntry: JsonResponse([1, 2])\nexcept TypeError as e: print('JsonResponse([1,2]) →', type(e).__name__ + ':', e)\nimport datetime\ntry: JsonResponse({'s': {1, 2}})\nexcept TypeError as e: print('JsonResponse({set}) →', type(e).__name__ + ':', e)"); print(o); R['json'] = o
print()
print('== 四:响应头注入:值里带换行')
o = run("r = c.get('/inject/')\nprint(r.content.decode())"); print(o); R['inject'] = o
print()
print('== 五:Content-Length 由谁加的?带不带 CommonMiddleware')
d2 = proj('d21b', apps=['django.contrib.contenttypes'], with_lab=False, middleware=[], urls="from django.urls import path\nfrom django.http import HttpResponse\nurlpatterns = [path('plain/', lambda r: HttpResponse('hello'))]\n")
rc, out = pyscript(d2, "from django.test import Client\nr = Client().get('/plain/')\nprint('无中间件:', dict(r.headers))")
print(out.rstrip()); R['nocommon'] = out.rstrip()
save('d21', R)
