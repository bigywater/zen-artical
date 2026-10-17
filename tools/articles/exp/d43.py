import sys, os, time, json, signal, http.client, subprocess, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d43'); R = {}
pg = PG(9413, conf={'max_connections': 30}).start()
GUN = str(HERE.parent / 'djlab' / 'bin' / 'gunicorn')
urls = '''
from django.urls import path
from django.http import JsonResponse
from django.db import connection
def ping(request):
    with connection.cursor() as c: c.execute('select pg_backend_pid()'); pid = c.fetchone()[0]
    return JsonResponse({'pid': pid})
urlpatterns = [path('ping/', ping)]
'''
PORT = 9414
def start(d, workers=1, threads=1):
    p = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT}', '-w', str(workers), '--threads', str(threads), '--timeout', '60', '--log-level', 'error'], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: http.client.HTTPConnection('127.0.0.1', PORT, timeout=1).request('GET', '/ping/'); break
        except Exception: time.sleep(0.1)
    time.sleep(0.5); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    time.sleep(0.6)
def get(conn):
    t0 = time.perf_counter(); conn.request('GET', '/ping/'); r = json.loads(conn.getresponse().read()); return (time.perf_counter() - t0) * 1000, r['pid']
def clients_now():
    r = pg.psql("select count(*) from pg_stat_activity where datname='lab' and usename='lab' and pid <> pg_backend_pid()")
    try: return int(r)
    except ValueError: return 'psql 自己也连不上:' + r.split('FATAL:')[-1].strip()
print('== 一:同一个 keep-alive 连接连续发 300 个请求:不同 CONN_MAX_AGE 下的延迟与用到的数据库连接数(gunicorn 1 worker 1 线程)')
R['seq'] = {}
print(f'  {"CONN_MAX_AGE":<14} {"中位(ms)":>10} {"p99(ms)":>10} {"不同 pid 数":>12} {"结束后连接数":>12}')
for label, extra in (('0(默认)', ''), ('60', ", 'CONN_MAX_AGE': 60"), ('None', ", 'CONN_MAX_AGE': None")):
    d = proj('d43', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, databases=pg.databases(extra))
    p = start(d); c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10)
    for _ in range(20): get(c)
    r = [get(c) for _ in range(300)]; lat = sorted(x[0] for x in r); pids = len(set(x[1] for x in r)); left = clients_now()
    R['seq'][label] = dict(med=statistics.median(lat), p99=lat[int(len(lat) * .99)], pids=pids, left=left)
    print(f'  {label:<14} {R["seq"][label]["med"]:>10.2f} {R["seq"][label]["p99"]:>10.2f} {pids:>12} {left:>12}')
    stop(p)
print()
print('== 二:持久连接的代价:max_connections=30 的数据库上,4 个 worker × 4 线程 = 最多 16 个持久连接;再开一个同样配置的服务会怎样')
d = proj('d43', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, databases=pg.databases(", 'CONN_MAX_AGE': None"))
p1 = start(d, 4, 4)
def hammer(port, n_threads=16, n=20):
    errs = []; lock = threading.Lock()
    def w():
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        for _ in range(n):
            try:
                c.request('GET', '/ping/'); r = c.getresponse(); b = r.read()
                if r.status != 200: errs.append(r.status)
            except Exception as e: errs.append(type(e).__name__)
    ts = [threading.Thread(target=w) for _ in range(n_threads)]; [t.start() for t in ts]; [t.join() for t in ts]; return errs
e1 = hammer(PORT); a_n = clients_now(); print('  服务 A(16 个处理线程)被打满后,数据库端连接数:', a_n, ' 错误数:', len(e1))
PORT2 = 9415
p2 = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT2}', '-w', '4', '--threads', '4', '--timeout', '60', '--log-level', 'error'], cwd=d, env=env(d), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(1.5)
e2 = hammer(PORT2); print('  再开服务 B(同样 16 个线程)并打满:数据库端连接数', clients_now(), ' 状态码/错误分布:', {k: e2.count(k) for k in set(e2)} or '无')
R['limit'] = dict(a_conns=a_n, a_errs=len(e1), b_errs={str(k): e2.count(k) for k in set(e2)}, b_conns=str(clients_now()))
print('  数据库日志里的相关行:', [l[-90:] for l in (pg.dir / 'pg.log').read_text().splitlines() if 'too many clients' in l][:2])
stop(p1); p2.terminate(); p2.wait(10)
pg.stop(); save('d43', R)
