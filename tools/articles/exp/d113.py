import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d113'); R = {}
urls = '''
import asyncio, threading, time, json
from asgiref.sync import sync_to_async
from django.urls import path
from django.http import HttpResponse, JsonResponse
def ping(request): return HttpResponse('ok')
def work(delay):
    time.sleep(delay); return threading.current_thread().name
async def ts(request):
    n = int(request.GET['n']); sens = request.GET['sens'] == '1'; delay = float(request.GET.get('delay', '0.2'))
    t0 = time.perf_counter()
    names = await asyncio.gather(*[sync_to_async(work, thread_sensitive=sens)(delay) for _ in range(n)])
    return JsonResponse({'ms': (time.perf_counter() - t0) * 1000, 'threads': sorted(set(names)), 'n_threads': len(set(names))})
async def seq(request):
    names = [await sync_to_async(work)(0) for _ in range(5)]
    return JsonResponse({'threads': names})
urlpatterns = [path('ping/', ping), path('ts/', ts), path('seq/', seq)]
'''
d = proj('d113', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
p = asrv.serve(d, 'uvicorn', 9507)
try:
    print('== 一:同一个 async 视图里连续 5 次 sync_to_async(默认 thread_sensitive=True):线程名')
    a = json.loads(asrv.get(9507, '/seq/')[1]); print('  ', a['threads'], '→ 不同线程数', len(set(a['threads']))); R['seq'] = a
    print()
    print('== 二:在一个请求里 gather 10 个 sync_to_async(time.sleep(0.2)):thread_sensitive=True vs False')
    R['ts'] = {}
    for sens in (1, 0):
        st, b, _ = asrv.get(9507, f'/ts/?n=10&sens={sens}'); j = json.loads(b); R['ts'][str(sens)] = j
        print(f'  thread_sensitive={bool(sens)!s:<5} 总耗时 {j["ms"]:7.0f} ms   用到的线程数 {j["n_threads"]}')
    print()
    print('== 三:20 个并发请求,每个请求里各做一次 sync_to_async(time.sleep(0.5))(默认 thread_sensitive=True)')
    tot, res = asrv.conc(9507, '/ts/?n=1&sens=1&delay=0.5', 20); ths = set(json.loads(r[1])['threads'][0] for r in res)
    print(f'  20 个并发请求总耗时 {tot:.0f} ms,用到 {len(ths)} 个不同线程'); R['conc'] = dict(total=tot, threads=len(ths))
    print()
    print('== 四:一个请求里 gather 50 个 thread_sensitive=False 的 0.2 s 任务:线程数与总耗时')
    st, b, _ = asrv.get(9507, '/ts/?n=50&sens=0'); j = json.loads(b); print(f'  总耗时 {j["ms"]:.0f} ms,用到 {j["n_threads"]} 个线程'); R['fifty'] = j
finally: asrv.stop(p)
save('d113', R)
