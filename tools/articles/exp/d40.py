import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d40'); R = {}
pg = PG(9404).start()
models = "from django.db import models\nclass Author(models.Model):\n    name = models.CharField(max_length=30)\nclass Book(models.Model):\n    title = models.CharField(max_length=60)\n    price = models.IntegerField()\n    author = models.ForeignKey(Author, on_delete=models.CASCADE)\n"
d_sqlite = proj('d40', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'], databases="{'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}, 'pg': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': %d}}" % pg.port)
manage(d_sqlite, 'migrate', '--run-syncdb'); manage(d_sqlite, 'migrate', '--run-syncdb', '--database', 'pg')
pre = "import logging, time, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections\nfrom django.db.models import Q, F, Count\nfrom lab.models import *\nqs = Book.objects.filter(price__gt=10, title__icontains='x').exclude(author__name='bob').select_related('author').order_by('-price')[:5]\n"
def run(code): rc, out = pyscript(d_sqlite, pre + code); return out.rstrip()
print('== 一:QuerySet 本身只是一个 Query 对象:此时没有任何 SQL 文本')
o = run("""
q = qs.query
print('type(qs.query) =', type(q).__module__ + '.' + type(q).__name__)
print('where 节点:', type(q.where).__name__, ' 子条件:', [type(c).__name__ + ':' + str(c)[:60] for c in q.where.children])
print('alias_map(参与查询的表别名):', list(q.alias_map))
print('order_by =', q.order_by, ' low_mark/high_mark =', (q.low_mark, q.high_mark), ' select_related =', q.select_related)
""")
print(o); R['query'] = o
print()
print('== 二:编译:同一个 Query 在不同数据库后端上编译出不同的 SQL')
o = run("""
for alias in ('default', 'pg'):
    sql, params = qs.query.get_compiler(using=alias).as_sql(); print(f'[{connections[alias].vendor}]', sql); print('   params =', params)
""")
print(o); R['compile'] = o
print()
print('== 三:三个阶段各花多少时间:构建 Query(链式调用)/ 编译 SQL / 执行并构造对象(每阶段 2000 次取平均)')
o = run("""
from statistics import mean
def build(): return Book.objects.filter(price__gt=10, title__icontains='x').exclude(author__name='bob').select_related('author').order_by('-price')[:5]
N = 2000
t0 = time.perf_counter()
for _ in range(N): build()
t_build = (time.perf_counter() - t0) / N * 1e6
q = build()
t0 = time.perf_counter()
for _ in range(N): q.query.get_compiler(using='default').as_sql()
t_comp = (time.perf_counter() - t0) / N * 1e6
Author.objects.bulk_create([Author(name='ann')]); Book.objects.bulk_create([Book(title='x', price=20, author=Author.objects.first())])
t0 = time.perf_counter()
for _ in range(N): list(build())
t_all = (time.perf_counter() - t0) / N * 1e6
print(f'构建 QuerySet(filter/exclude/select_related/order_by/切片): {t_build:7.1f} µs')
print(f'编译成 SQL(get_compiler().as_sql()):                        {t_comp:7.1f} µs')
print(f'从头到尾 list(build())(含 SQLite 执行与构造对象):       {t_all:7.1f} µs')
""")
print(o); R['time'] = o
print()
print('== 四:看到实际发出的 SQL 的几种办法')
o = run("""
from django.test.utils import CaptureQueriesContext
print('str(qs.query)        →', str(qs.query)[:120], '...  (参数直接拼进去,只用于阅读,不保证可直接执行)')
sql, params = qs.query.sql_with_params(); print('sql_with_params()    → params =', params)
with CaptureQueriesContext(connection) as c: list(qs)
print('CaptureQueriesContext → 实际执行:', c.captured_queries[-1]['sql'][:100], '...')
print('connection.queries 需要 DEBUG=True 或 CaptureQueriesContext')
""")
print(o); R['views'] = o
pg.stop(); save('d40', R)
