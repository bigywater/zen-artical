import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d102'); R = {}
pg = PG(9470).start()
models = "from django.db import models\nclass Tag(models.Model):\n    name = models.CharField(max_length=20)\nclass Row(models.Model):\n    a = models.IntegerField()\n    b = models.CharField(max_length=40)\n    d = models.TextField()\n    tag = models.ForeignKey(Tag, null=True, on_delete=models.SET_NULL)\n"
dbs = "{'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}, 'pg': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': %d}}" % pg.port
d = proj('d102', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'], databases=dbs)
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate'); manage(d, 'migrate', '--database', 'pg')
pg.psql("insert into lab_tag (name) select 't' || g from generate_series(1, 50) g")
pg.psql("insert into lab_row (a, b, d, tag_id) select g, 'bee-' || g, repeat('d', 200), (g % 50) + 1 from generate_series(1, 200000) g")
from dj import subprocess as _sp
rc, o = pyscript(d, "from django.db import connections\nfrom lab.models import *\nfrom django.db.models import F\nconnections['default'].cursor()\nTag.objects.bulk_create([Tag(name=f't{i}') for i in range(50)]); tg = list(Tag.objects.all())\nRow.objects.bulk_create([Row(a=i, b=f'bee-{i}', d='d' * 200, tag=tg[i % 50]) for i in range(200000)], batch_size=5000)")
pre = "import logging, time, tracemalloc, gc, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\ndef m(label, fn, using):\n    gc.collect(); t0 = time.perf_counter(); r = fn(); dt = time.perf_counter() - t0\n    gc.collect(); tracemalloc.start(); r = fn(); cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()\n    print(f'  [{using}] {label:<44} {dt*1000:8.0f} ms   峰值内存 {peak/1048576:7.1f} MiB   → {r}'); return dt * 1000, peak / 1048576\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:20 万行(每行约 260 字节)的三种遍历方式:list() / 直接 for(有缓存)/ iterator()')
o = run("""
for using in ('default', 'pg'):
    qs = lambda: Row.objects.using(using).all()
    def as_list(): return len(list(qs()))
    def for_loop():
        n = 0; q = qs()
        for r in q: n += 1
        return n
    def it(): 
        n = 0
        for r in qs().iterator(): n += 1
        return n
    def it_small():
        n = 0
        for r in qs().iterator(chunk_size=500): n += 1
        return n
    m('list(qs)', as_list, using); m('for r in qs(结果缓存在 QuerySet 里)', for_loop, using); m('for r in qs.iterator()', it, using); m('for r in qs.iterator(chunk_size=500)', it_small, using)
""")
print(o); R['modes'] = o
print()
print('== 二:PostgreSQL 上 iterator() 用服务端游标:同时看数据库端是否存在游标(pg_cursors)')
o = run("""
import threading
from django.db import connections
using = 'pg'
peek = {}
it = Row.objects.using(using).all().iterator(chunk_size=1000)
next(it)
with connections['pg'].cursor() as c2: pass
import psycopg
c = psycopg.connect(host='127.0.0.1', port=%d, user='lab', dbname='lab', autocommit=True)
print('iterator() 已取第一批之后,另一个连接看到的活动语句数(pg_stat_activity 中 state != idle):', c.execute("select count(*) from pg_stat_activity where datname='lab' and state <> 'idle' and pid <> pg_backend_pid()").fetchone()[0], '(游标是在 Django 连接的事务里,不是独立会话)')
for _ in it: pass
""" % pg.port)
print(o); R['cursor'] = o
print()
print('== 三:iterator() 与 prefetch_related 一起用:必须给 chunk_size(Django 4.1+),预取按批做')
o = run("""
from django.db.models import Prefetch
for using in ('default', 'pg'):
    try:
        it = Row.objects.using(using).select_related(None).prefetch_related('tag').iterator()
        next(it); print(f'  [{using}] 不给 chunk_size:', '没有报错')
    except Exception as e: print(f'  [{using}] 不给 chunk_size →', type(e).__name__ + ':', str(e)[:110])
    with CaptureQueriesContext(connections[using]) as c:
        n = 0
        for r in Row.objects.using(using).prefetch_related('tag').iterator(chunk_size=20000):
            n += 1
            if n >= 60000: break
    print(f'  [{using}] chunk_size=20000,处理 6 万行(3 批)的查询数:', len(c), ' 其中预取 tag 的查询:', sum('lab_tag' in q['sql'] for q in c.captured_queries))
""")
print(o); R['prefetch'] = o
print()
print('== 四:iterator() 之后 QuerySet 不缓存:再次遍历会再查一次;.count() / 切片的表现')
o = run("""
qs = Row.objects.all()
with CaptureQueriesContext(connection) as c:
    for r in qs.iterator(chunk_size=5000): break
    for r in qs.iterator(chunk_size=5000): break
print('两次 iterator()(各只取第一条):查询', len(c), '次(每次都新发查询)')
with CaptureQueriesContext(connection) as c:
    n = sum(1 for _ in qs); n2 = sum(1 for _ in qs)
print('普通遍历两次:查询', len(c), '次(第二次用缓存)')
""")
print(o); R['nocache'] = o
pg.stop(); save('d102', R)
