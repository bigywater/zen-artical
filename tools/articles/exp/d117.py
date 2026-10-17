import sys, os, time, json, re, http.client, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d117'); R = {}
urls = '''
import asyncio, time, pathlib
from django.urls import path
from django.http import HttpResponse, StreamingHttpResponse
LOGF = pathlib.Path(__file__).parent.parent / 'events.log'
def ping(request): return HttpResponse('ok')
async def agen(n=5, delay=0.3):
    try:
        for i in range(n):
            await asyncio.sleep(delay); yield f'data: event {i}\\n\\n'.encode()
    finally:
        with open(LOGF, 'a') as f: f.write('async generator finally 执行了\\n')
def sgen(n=5, delay=0.3):
    for i in range(n):
        time.sleep(delay); yield f'data: event {i}\\n\\n'.encode()
async def async_stream(request): return StreamingHttpResponse(agen(), content_type='text/event-stream')
def sync_stream(request): return StreamingHttpResponse(sgen(), content_type='text/event-stream')
urlpatterns = [path('ping/', ping), path('as/', async_stream), path('ss/', sync_stream)]
'''
d = proj('d117', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
def timed(port, path, stop_after=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=60); t0 = time.perf_counter(); c.request('GET', path); r = c.getresponse()
    times = []
    while True:
        b = r.read1(65536)
        if not b: break
        times.append((time.perf_counter() - t0) * 1000)
        if stop_after and len(times) >= stop_after: c.close(); return times, True
    return times, False
print('== 一:5 个事件、每个间隔 0.3 s:客户端什么时候收到第一批数据、一共收到几批?')
R['ttfb'] = {}
for kind, port in (('uvicorn', 9530), ('gunicorn', 9531)):
    p = asrv.serve(d, kind, port)
    try:
        for name in ('as', 'ss'):
            ts, _ = timed(port, f'/{name}/'); lab = {'as': 'async 生成器', 'ss': 'sync 生成器'}[name]
            R['ttfb'][f'{kind}_{name}'] = dict(first=ts[0], total=ts[-1], chunks=len(ts))
            print(f'  {"ASGI uvicorn" if kind == "uvicorn" else "WSGI gunicorn":<13} + {lab:<10} 首批 {ts[0]:6.0f} ms  最后一批 {ts[-1]:6.0f} ms  收到 {len(ts)} 批')
    finally:
        stop_log = open(d / 'srv.log').read(); asrv.stop(p)
        w = sorted(set(l[l.index('StreamingHttpResponse must'):].strip()[:190] for l in stop_log.splitlines() if 'StreamingHttpResponse must' in l))
        for l in w: print('    服务端警告:', l)
        R.setdefault('warns', {})[kind] = w
print()
print('== 二:客户端读到第一批就断开:服务端的 async 生成器有没有被中止(events.log 里有没有 finally 的记录)')
p = asrv.serve(d, 'uvicorn', 9532)
try:
    (d / 'events.log').write_text('')
    ts, cut = timed(9532, '/as/', stop_after=1); time.sleep(1.5)
    print('  客户端在第', len(ts), '批之后断开;1.5 s 后 events.log 内容:', repr((d / 'events.log').read_text()))
    R['cancel'] = (d / 'events.log').read_text()
finally: asrv.stop(p)
print()
print('== 三:并发长连接:同时 30 个 async 流(每个 1.5 s)在 uvicorn 单 worker;6 个流在 gunicorn 单个同步 worker')
p = asrv.serve(d, 'uvicorn', 9533)
try:
    tot, res = asrv.conc(9533, '/as/', 30); print(f'  uvicorn  30 个并发 async 流总耗时 {tot:.0f} ms  全部 200: {all(r[0] == 200 for r in res)}'); R['c_uv'] = tot
finally: asrv.stop(p)
p = asrv.serve(d, 'gunicorn', 9534)
try:
    tot, res = asrv.conc(9534, '/ss/', 6); print(f'  gunicorn 6 个并发 sync 流总耗时 {tot:.0f} ms  全部 200: {all(r[0] == 200 for r in res)}'); R['c_gu'] = tot
finally: asrv.stop(p)
save('d117', R)
