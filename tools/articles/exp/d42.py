import sys, os, time, json, signal, http.client, subprocess, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d42'); R = {}
pg = PG(9411).start()
GUN = str(HERE.parent / 'djlab' / 'bin' / 'gunicorn')
urls = '''
import threading
from django.urls import path
from django.http import JsonResponse
from django.db import connection
def info(request):
    before = connection.connection is None
    with connection.cursor() as c:
        c.execute('select pg_backend_pid()'); pid = c.fetchone()[0]
    return JsonResponse({'pid': pid, 'thread': threading.current_thread().name, 'conn_was_none': before})
def nodb(request): return JsonResponse({'has_conn': connection.connection is not None})
urlpatterns = [path('info/', info), path('nodb/', nodb)]
'''
d = proj('d42', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, databases=pg.databases())
PORT = 9412
def start(workers=1, threads=1, extra=()):
    p = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT}', '-w', str(workers), '--threads', str(threads), '--timeout', '60', '--log-level', 'error', *extra], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: http.client.HTTPConnection('127.0.0.1', PORT, timeout=1).request('GET', '/nodb/'); break
        except Exception: time.sleep(0.1)
    time.sleep(0.5); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    time.sleep(0.5)
def get(path):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10); c.request('GET', path); return json.loads(c.getresponse().read())
def clients_now(): return int(pg.psql("select count(*) from pg_stat_activity where datname='lab' and usename='lab' and pid <> pg_backend_pid()") or 0)
print('== 一:默认(CONN_MAX_AGE=0):一个 worker、一个线程,连续 6 个请求看到的数据库后端进程号')
p = start(); a = get('/nodb/'); print('  还没有任何查询时,connection.connection 是否已建立:', a['has_conn']); R['nodb'] = a
res = [get('/info/') for _ in range(6)]; time.sleep(0.3)
print('  每个请求里 pg_backend_pid():', [r['pid'] for r in res]); print('  每个请求开始时 connection.connection 是 None 吗:', [r['conn_was_none'] for r in res]); print('  请求处理线程:', sorted(set(r['thread'] for r in res)))
print('  请求结束后数据库端还剩多少个来自应用的连接:', clients_now(), '(请求结束时连接被关闭)')
R['default'] = dict(pids=[r['pid'] for r in res], none=[r['conn_was_none'] for r in res], left=clients_now())
stop(p)
print()
print('== 二:每个线程一个连接(连接是线程局部的):CONN_MAX_AGE=None(不关闭),1 个 worker、4 个线程,并发 40 个请求')
d2 = proj('d42', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, databases=pg.databases(", 'CONN_MAX_AGE': None"))
p = start(1, 4); res = []; lock = threading.Lock()
def w():
    for _ in range(10):
        r = get('/info/')
        with lock: res.append(r)
ts = [threading.Thread(target=w) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]; time.sleep(0.3)
print('  40 个请求用到的不同数据库连接(pid)数:', len(set(r['pid'] for r in res)), ';不同处理线程数:', len(set(r['thread'] for r in res)))
print('  请求全部结束后,数据库端仍保持的连接数:', clients_now(), '(持久连接没有被关闭)')
R['threads'] = dict(pids=len(set(r['pid'] for r in res)), threads=len(set(r['thread'] for r in res)), left=clients_now())
stop(p)
print('  服务停止后数据库端连接数:', clients_now())
pg.stop(); save('d42', R)
