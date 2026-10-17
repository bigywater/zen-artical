import sys, os, time, json, re, statistics, collections, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
import asrv
tee('d134'); R = {}
pg = PG(9475, conf={'log_connections': 'on', 'max_connections': 20}).start()
urls = '''
from django.urls import path
from django.http import HttpResponse
from django.db import connection
def ping(r): return HttpResponse('ok')
def q(r):
    with connection.cursor() as c: c.execute('select pg_sleep(%s)', [float(r.GET.get('s', '0'))]); c.fetchone()
    return HttpResponse('ok')
urlpatterns = [path('ping/', ping), path('q/', q)]
'''
d = proj('d134', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[], settings_extra=ES)
def db(**opts):
    x = {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': pg.port}; x.update(opts); return {'default': x}
MODES = (('CONN_MAX_AGE=0(默认:每个请求新建连接)', db()), ('CONN_MAX_AGE=60(持久连接)', db(CONN_MAX_AGE=60)), ('连接池 OPTIONS pool(min 2, max 4)', db(OPTIONS={'pool': {'min_size': 2, 'max_size': 4}})))
def conns_logged(): return sum(1 for l in open(pg.dir / 'pg.log') if 'connection authorized' in l and 'application_name=psql' not in l)
def serve(port, dbs, *extra):
    return asrv.serve(d, 'gunicorn', port, extra=list(extra), EXTRA_SETTINGS=json.dumps(dict(ALLOWED_HOSTS=['*'], DEBUG=False, DATABASES=dbs)))
print('== 一:2 个 sync worker,200 个串行请求(每个请求 1 次查询):数据库那边一共建立了多少次连接、每个请求的中位延迟')
R['serial'] = {}
for i, (label, dbs) in enumerate(MODES):
    p = serve(9580 + i, dbs, '-w', '2')
    try:
        for _ in range(10): asrv.get(9580 + i, '/q/')
        b0 = conns_logged(); xs = [asrv.get(9580 + i, '/q/')[2] for _ in range(200)]; b1 = conns_logged()
    finally: asrv.stop(p)
    R['serial'][label] = dict(conns=b1 - b0, med=statistics.median(xs)); print(f'  {label:<40} 预热 10 个请求之后,新建连接 {b1 - b0:>4} 次   延迟中位 {statistics.median(xs):6.2f} ms')
print()
print('== 二:max_connections=20:gunicorn gthread 2 进程 × 20 线程,同时 40 个请求(每个请求持有连接 0.5 s)')
R['exhaust'] = {}
for i, (label, dbs) in enumerate(MODES[1:]):
    p = serve(9585 + i, dbs, '-w', '2', '-k', 'gthread', '--threads', '20')
    try:
        asrv.get(9585 + i, '/q/'); tot, res = asrv.conc(9585 + i, '/q/?s=0.5', 40, timeout=60)
    finally: asrv.stop(p)
    cnt = collections.Counter(r[0] for r in res); R['exhaust'][label] = dict(total=tot, codes=dict(cnt)); print(f'  {label:<40} 状态码分布 {dict(sorted(cnt.items()))}   总耗时 {tot:6.0f} ms')
err = [l.strip() for l in open(pg.dir / 'pg.log') if 'too many clients' in l or 'remaining connection slots' in l]
print('  PostgreSQL 日志里的拒绝信息(最后一条):', err[-1][-100:] if err else '(没有)'); R['pg_err'] = err[-1][-120:] if err else ''
pg.stop(); save('d134', R)
