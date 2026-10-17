import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d116'); R = {}
mw = '''
import asyncio, time
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
class SyncMW:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request): return self.get_response(request)
class SyncSleepMW:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request): time.sleep(0.2); return self.get_response(request)
class AsyncMW:
    sync_capable = False; async_capable = True
    def __init__(self, get_response):
        self.get_response = get_response; markcoroutinefunction(self)
    async def __call__(self, request): return await self.get_response(request)
class AsyncSleepMW:
    sync_capable = False; async_capable = True
    def __init__(self, get_response):
        self.get_response = get_response; markcoroutinefunction(self)
    async def __call__(self, request): await asyncio.sleep(0.2); return await self.get_response(request)
'''
urls = '''
import asyncio
from django.urls import path
from django.http import HttpResponse
def ping(request): return HttpResponse('ok')
async def a(request): return HttpResponse('a')
async def slow(request):
    await asyncio.sleep(0.2); return HttpResponse('slow')
urlpatterns = [path('ping/', ping), path('a/', a), path('slow/', slow)]
'''
extra = '''
import os
MODES = {'none': [], 'sync1': ['proj.mw.SyncMW'], 'sync5': ['proj.mw.SyncMW'] * 5, 'async5': ['proj.mw.AsyncMW'] * 5,
         'syncsleep': ['proj.mw.SyncSleepMW'], 'asyncsleep': ['proj.mw.AsyncSleepMW']}
MIDDLEWARE = MODES[os.environ.get('MW_MODE', 'none')]
LOGGING = {'version': 1, 'disable_existing_loggers': False, 'handlers': {'c': {'class': 'logging.StreamHandler'}}, 'loggers': {'django.request': {'handlers': ['c'], 'level': 'DEBUG'}}}
'''
d = proj('d116', files={'proj/mw.py': mw}, urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[], settings_extra=extra)
def bench(mode, port, path='/a/', n=400):
    p = asrv.serve(d, 'uvicorn', port, MW_MODE=mode)
    try:
        for _ in range(30): asrv.get(port, path)
        xs = []
        for _ in range(n): xs.append(asrv.get(port, path)[2])
        return statistics.median(xs), open(d / 'srv.log').read()
    finally: asrv.stop(p)
print('== 一:串行请求一个 async 视图 400 次,uvicorn(DEBUG=True),不同中间件组合的请求耗时中位数')
R['lat'] = {}; logs = {}
for i, (mode, label) in enumerate((('none', '没有中间件'), ('async5', '5 个 async 中间件'), ('sync1', '1 个只支持 sync 的中间件'), ('sync5', '5 个只支持 sync 的中间件'))):
    m, log = bench(mode, 9510 + i); R['lat'][mode] = m; logs[mode] = log
    print(f'  {label:<26} {m:6.3f} ms')
print()
print('== 二:django.request 的 DEBUG 日志里怎么说这些同步中间件(uvicorn 日志里含 adapted 的行,去重)')
lines = sorted(set(l.strip() for l in logs['sync5'].splitlines() if 'adapted' in l))
for l in lines: print(' ', l)
if not lines: print('  (没有 adapted 日志)')
R['adapted'] = lines
print('  没有同步中间件时(async5)日志里 adapted 行数:', sum('adapted' in l for l in logs['async5'].splitlines()))
print()
print('== 三:中间件里做阻塞 / 非阻塞的等待(每个请求 0.2 s),20 个并发请求打 /slow/(视图本身也 await 0.2 s)')
R['conc'] = {}
for i, (mode, label) in enumerate((('asyncsleep', 'async 中间件里 await asyncio.sleep(0.2)'), ('syncsleep', 'sync 中间件里 time.sleep(0.2)'))):
    p = asrv.serve(d, 'uvicorn', 9520 + i, MW_MODE=mode)
    try:
        asrv.get(9520 + i, '/slow/'); tot, res = asrv.conc(9520 + i, '/slow/', 20)
    finally: asrv.stop(p)
    R['conc'][mode] = tot; print(f'  {label:<40} 20 并发总耗时 {tot:6.0f} ms  全部 200: {all(r[0] == 200 for r in res)}')
save('d116', R)
