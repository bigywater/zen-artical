import sys, os, time, json, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d111'); R = {}
urls = '''
import asyncio, time
from django.urls import path
from django.http import HttpResponse
def ping(request): return HttpResponse('ok')
async def a_sleep(request):
    await asyncio.sleep(0.5); return HttpResponse('async')
def s_sleep(request):
    time.sleep(0.5); return HttpResponse('sync')
urlpatterns = [path('ping/', ping), path('a/', a_sleep), path('s/', s_sleep)]
'''
d = proj('d111', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
N = 20
def row(label, kind, path, port):
    p = asrv.serve(d, kind, port)
    try:
        asrv.get(port, path); tot, res = asrv.conc(port, path, N)
    finally: asrv.stop(p)
    ok = all(r[0] == 200 for r in res); ms = sorted(r[2] for r in res)
    print(f'  {label:<34} 总耗时 {tot:7.0f} ms   单个请求最快 {ms[0]:6.0f} / 最慢 {ms[-1]:6.0f} ms   全部 200: {ok}')
    return dict(total=tot, fast=ms[0], slow=ms[-1], ok=ok)
print(f'== 一:{N} 个并发请求,每个请求的视图里「等」0.5 秒(1 个 worker):async 视图 vs sync 视图,ASGI(uvicorn) vs WSGI(gunicorn 同步 worker)')
R['t'] = {}
R['t']['asgi_async'] = row('uvicorn + async def 视图(asyncio.sleep)', 'uvicorn', '/a/', 9500)
R['t']['asgi_sync'] = row('uvicorn + 普通 def 视图(time.sleep)', 'uvicorn', '/s/', 9501)
R['t']['wsgi_async'] = row('gunicorn 同步 worker + async def 视图', 'gunicorn', '/a/', 9502)
R['t']['wsgi_sync'] = row('gunicorn 同步 worker + 普通 def 视图', 'gunicorn', '/s/', 9503)
save('d111', R)
