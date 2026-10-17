import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d112'); R = {}
urls = '''
import asyncio, threading, json
from django.urls import path
from django.http import HttpResponse, JsonResponse
def ping(request): return HttpResponse('ok')
def info(kind):
    try: asyncio.get_running_loop(); loop = True
    except RuntimeError: loop = False
    return {'view': kind, 'thread': threading.current_thread().name, 'main_thread': threading.current_thread() is threading.main_thread(), 'event_loop_running_here': loop}
async def a(request): return JsonResponse(info('async def'))
def s(request): return JsonResponse(info('def'))
urlpatterns = [path('ping/', ping), path('a/', a), path('s/', s)]
'''
d = proj('d112', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
print('== 一:视图代码到底在哪个线程、有没有事件循环?(每种组合请求两次,取第二次)')
R['rows'] = []
for kind, port in (('uvicorn', 9504), ('gunicorn', 9505)):
    p = asrv.serve(d, kind, port)
    try:
        for path_, label in (('/a/', 'async def'), ('/s/', 'def')):
            asrv.get(port, path_); st, body, _ = asrv.get(port, path_); j = json.loads(body)
            row = dict(server=kind, view=label, thread=j['thread'], main=j['main_thread'], loop=j['event_loop_running_here']); R['rows'].append(row)
            print(f'  {"ASGI (uvicorn)" if kind == "uvicorn" else "WSGI (gunicorn)":<16} {label:<10} → 线程 {j["thread"]:<22} 是主线程: {str(j["main_thread"]):<5} 该线程里有运行中的事件循环: {j["event_loop_running_here"]}')
    finally: asrv.stop(p)
print()
print('== 二:ASGI 下连续请求 sync 视图:每次是不是同一个线程?')
p = asrv.serve(d, 'uvicorn', 9506)
try:
    ths = [json.loads(asrv.get(9506, '/s/')[1])['thread'] for _ in range(6)]
    print('  6 次请求 sync 视图的线程名:', ths)
    print('  不同的线程数:', len(set(ths))); R['threads'] = ths
finally: asrv.stop(p)
save('d112', R)
