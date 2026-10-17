import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d41'); R = {}
pg = PG(9410).start()
models = "from django.db import models\nclass Order(models.Model):\n    customer = models.IntegerField()\n    status = models.CharField(max_length=10)\n    amount = models.IntegerField()\n"
dbs = "{'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}, 'pg': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': %d}}" % pg.port
d = proj('d41', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'], databases=dbs)
manage(d, 'migrate', '--run-syncdb'); manage(d, 'migrate', '--run-syncdb', '--database', 'pg')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connections\nfrom lab.models import Order\nOrder.objects.using('pg').exists() or Order.objects.using('pg').bulk_create([Order(customer=i % 1000, status='paid' if i % 10 else 'new', amount=i) for i in range(200000)], batch_size=5000)\nwith connections['pg'].cursor() as c: c.execute('ANALYZE lab_order')\nOrder.objects.using('default').exists() or Order.objects.using('default').bulk_create([Order(customer=i % 1000, status='paid', amount=i) for i in range(1000)])\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:explain() 是什么:让数据库说明执行计划(不带 analyze 时不真正执行查询)')
o = run("""
qs = Order.objects.using('pg').filter(customer=42)
print('PostgreSQL(customer 没有索引):'); print(qs.explain())
print(); print('SQLite:'); print(Order.objects.using('default').filter(customer=42).explain())
""")
print(o); R['basic'] = o
print()
print('== 二:加索引前后计划的变化(PostgreSQL)')
o = run("""
with connections['pg'].cursor() as c: c.execute('CREATE INDEX IF NOT EXISTS order_customer_idx ON lab_order (customer)'); c.execute('ANALYZE lab_order')
qs = Order.objects.using('pg').filter(customer=42)
print('customer 上有索引之后:'); print(qs.explain())
qs = Order.objects.using('pg').filter(amount__gt=100)
print('amount__gt=100(amount 没有索引,匹配大多数行):'); print(qs.explain())
""")
print(o); R['index'] = o
print()
print('== 三:analyze=True 真的执行并给出实际耗时;其它选项')
o = run("""
qs = Order.objects.using('pg').filter(customer=42)
print(qs.explain(analyze=True))
print('--- verbose + format=json 的第一层键:'); import json; r = qs.explain(format='json'); print(list(json.loads(r)[0].keys()) if isinstance(r, str) else type(r))
print('--- buffers=True(需要 analyze):'); print(qs.explain(analyze=True, buffers=True).splitlines()[-4:])
""")
print(o); R['analyze'] = o
print()
print('== 四:analyze 会执行语句:对带副作用的查询要小心;explain 对聚合、count 的支持')
o = run("""
qs = Order.objects.using('pg').filter(status='paid')
print('explain 只对 QuerySet;count() 不能 explain:', end=' ')
try: print(qs.count().explain())
except Exception as e: print(type(e).__name__ + ':', str(e)[:80])
print('对 annotate 聚合查询的 explain:'); from django.db.models import Count; print(Order.objects.using('pg').values('status').annotate(n=Count('id')).explain().splitlines()[0])
""")
print(o); R['misc'] = o
pg.stop(); save('d41', R)
