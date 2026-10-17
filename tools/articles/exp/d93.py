import sys, os, time, json, re, signal, http.client, subprocess, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d93'); R = {}
from rl import Node
GUN = str(HERE.parent / 'djlab' / 'bin' / 'gunicorn')
rn = Node(9460, name='d93redis'); rn.start()
CFG = {
    'locmem': "{'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}",
    'db': "{'BACKEND': 'django.core.cache.backends.db.DatabaseCache', 'LOCATION': 'cache_table'}",
    'file': "{'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache', 'LOCATION': str(BASE_DIR / 'cachefiles')}",
    'redis': "{'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:9460/0'}",
}
urls = "from django.urls import path\nfrom django.http import JsonResponse\nimport os\nfrom django.core.cache import cache\ndef setk(request): cache.set('shared', os.getpid(), 300); return JsonResponse({'set_by': os.getpid()})\ndef getk(request): return JsonResponse({'served_by': os.getpid(), 'value': cache.get('shared')})\nurlpatterns = [path('set/', setk), path('get/', getk)]\n"
def build(name):
    d = proj('d93', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra=f"\nCACHES = {{'default': {CFG[name]}}}\n"); (d / 'cachefiles').mkdir(exist_ok=True)
    if name == 'db': manage(d, 'createcachetable')
    return d
print('== 一:五次读写的耗时(每种后端 1000 次 set + 1000 次 get 的每次中位数,进程内直接调用)')
R['perf'] = {}
print(f'  {"后端":<8} {"set(µs)":>10} {"get 命中(µs)":>14} {"get 未命中(µs)":>15}')
for name in CFG:
    d = build(name)
    rc, out = pyscript(d, """
import logging, time, statistics; logging.disable(logging.CRITICAL)
from django.core.cache import cache
cache.clear()
def bench(fn, n=1000):
    xs = []
    for i in range(n):
        t0 = time.perf_counter(); fn(i); xs.append((time.perf_counter() - t0) * 1e6)
    return statistics.median(xs)
val = {'k': 'v' * 200}
print('%.1f %.1f %.1f' % (bench(lambda i: cache.set(f'k{i}', val, 300)), bench(lambda i: cache.get(f'k{i}')), bench(lambda i: cache.get(f'nope{i}'))))
""")
    a, b, c = map(float, out.strip().splitlines()[-1].split()); R['perf'][name] = dict(set=a, hit=b, miss=c); print(f'  {name:<8} {a:>10.1f} {b:>14.1f} {c:>15.1f}')
print()
print('== 二:多个 worker 进程之间共享吗?gunicorn 2 个 worker:一个请求写、多个请求读')
PORT = 9461; R['share'] = {}
def start(d):
    p = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT}', '-w', '2', '--log-level', 'error'], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: http.client.HTTPConnection('127.0.0.1', PORT, timeout=1).request('GET', '/get/'); break
        except Exception: time.sleep(0.1)
    time.sleep(0.5); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    time.sleep(0.5)
def gj(path):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10); c.request('GET', path); return json.loads(c.getresponse().read())
for name in CFG:
    d = build(name); p = start(d)
    w = gj('/set/'); reads = [gj('/get/') for _ in range(20)]
    seen = sum(1 for r in reads if r['value'] == w['set_by']); pids = len(set(r['served_by'] for r in reads))
    R['share'][name] = dict(seen=seen, of=20, workers=pids); print(f'  {name:<8} set 由 pid {w["set_by"]} 执行;20 次读取来自 {pids} 个 worker,读到该值 {seen}/20 次')
    stop(p)
print()
print('== 三:重启之后还在吗:写入 → 停服务 → 再起 → 读')
R['restart'] = {}
for name in CFG:
    d = build(name); p = start(d); w = gj('/set/'); stop(p); p = start(d); r = gj('/get/'); stop(p)
    R['restart'][name] = r['value'] is not None; print(f'  {name:<8} 重启后 get =', r['value'], '(' + ('保留' if r['value'] is not None else '丢失') + ')')
print()
print('== 四:LocMem 的容量:MAX_ENTRIES 默认 300,超过时按 CULL_FREQUENCY 淘汰')
d = build('locmem')
rc, out = pyscript(d, """
import logging; logging.disable(logging.CRITICAL)
from django.core.cache import cache
cache.clear()
for i in range(500): cache.set(f'k{i}', i, 300)
alive = sum(1 for i in range(500) if cache.get(f'k{i}') is not None)
print('写入 500 个 key 后还在的:', alive, '(MAX_ENTRIES 默认 300,超过后淘汰约 1/3)')
print('最早写入的 k0 还在吗:', cache.get('k0'), ' 最新的 k499:', cache.get('k499'))
""")
print('  ' + out.strip().replace('\n', '\n  ')); R['locmem_cap'] = out.strip()
rn.stop(); save('d93', R)
