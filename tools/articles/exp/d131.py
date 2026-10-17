import sys, os, time, json, re, signal, threading, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d131'); R = {}
urls = '''
import asyncio, os, time
from django.urls import path
from django.http import HttpResponse
def ping(r): return HttpResponse('ok')
async def a(r):
    await asyncio.sleep(float(r.GET.get('s', '0.5'))); return HttpResponse(str(os.getpid()))
def s(r):
    time.sleep(float(r.GET.get('s', '0.5'))); return HttpResponse(str(os.getpid()))
urlpatterns = [path('ping/', ping), path('a/', a), path('s/', s)]
'''
d = proj('d131', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
KINDS = (('uvicorn', 'uvicorn'), ('daphne', 'daphne'), ('gunicorn-uvicorn', 'gunicorn + UvicornWorker'))
print('== 一:三种 ASGI 部署方式,各起 1 个进程,20 个并发请求(每个视图里等 0.5 s):async def 视图与普通 def 视图')
R['conc'] = {}
for i, (kind, label) in enumerate(KINDS):
    t0 = time.perf_counter(); p = asrv.serve(d, kind, 9560 + i); boot = (time.perf_counter() - t0) * 1000
    try:
        asrv.get(9560 + i, '/a/?s=0'); ta, ra = asrv.conc(9560 + i, '/a/', 20); ts, rs = asrv.conc(9560 + i, '/s/', 20)
    finally: asrv.stop(p)
    R['conc'][kind] = dict(a=ta, s=ts, boot=boot, ok=all(r[0] == 200 for r in ra + rs))
    print(f'  {label:<26} async 视图 {ta:6.0f} ms   sync 视图 {ts:6.0f} ms   启动到能响应 {boot:5.0f} ms   全部 200: {R["conc"][kind]["ok"]}')
print()
print('== 二:ASGI 的 lifespan 协议:Django 的 ASGIHandler 不支持,uvicorn 的日志(--log-level info)怎么说')
p = asrv.serve(d, 'uvicorn', 9563, extra=['--log-level', 'info'])
try: asrv.get(9563, '/ping/')
finally: asrv.stop(p)
lg = [l.strip() for l in open(d / 'srv.log').read().splitlines() if 'ifespan' in l or 'Started server' in l or 'Application startup' in l]
for l in lg: print('  ', l[:120])
R['lifespan'] = lg
print()
print('== 三:uvicorn --workers 2:40 个并发请求落在几个进程上')
p = asrv.serve(d, 'uvicorn', 9564, workers=2)
try:
    asrv.get(9564, '/a/?s=0'); tot, res = asrv.conc(9564, '/a/?s=0.3', 40); cnt = collections.Counter(r[1] for r in res)
finally: asrv.stop(p)
print(f'  总耗时 {tot:.0f} ms;各 worker 进程处理的请求数:', sorted(cnt.values()), f'(共 {len(cnt)} 个进程)'); R['workers'] = dict(total=tot, dist=sorted(cnt.values()))
print()
print('== 四:SIGTERM 时还有一个 2 s 的在途请求:uvicorn / daphne 各自的表现')
R['term'] = {}
for i, (kind, label) in enumerate(KINDS[:2]):
    port = 9565 + i; p = asrv.serve(d, kind, port); out_ = {}
    def req():
        try: out_['r'] = asrv.get(port, '/a/?s=2', timeout=30)[0]
        except Exception as e: out_['r'] = type(e).__name__
    th = threading.Thread(target=req); th.start(); time.sleep(0.6); t0 = time.perf_counter(); p.send_signal(signal.SIGTERM)
    try: p.wait(20)
    except Exception: p.kill()
    el = (time.perf_counter() - t0) * 1000; th.join()
    R['term'][kind] = dict(result=out_['r'], ms=el); print(f'  {label:<10} 在途请求结果 {out_["r"]}   SIGTERM 后进程退出用时 {el:.0f} ms')
save('d131', R)
