import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d27'); R = {}
d = proj('d27', files={'lab/models.py': "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=30)\n    price = models.IntegerField(default=0)\n"}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.db import connection, reset_queries\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Item\nif not Item.objects.exists(): Item.objects.bulk_create([Item(name=f'n{i}', price=i) for i in range(50)])\ndef q(label, fn):\n    with CaptureQueriesContext(connection) as c: r = fn()\n    print(f'{label:<52} 查询 {len(c)} 次' + ('  SQL: ' + c.captured_queries[0]['sql'].split('FROM')[0][-2:] + '...' if False else ''))\n    return c\n" + code); return out.rstrip()
print('== 一:创建 QuerySet、链式调用、迭代、再次迭代:各发几次查询')
o = run("""
qs = None
def build():
    global qs; qs = Item.objects.filter(price__gt=10).order_by('price').exclude(name='n20')
q('构造 + 链式调用 filter/order_by/exclude', build)
q('第 1 次 list(qs)', lambda: list(qs))
q('第 2 次 list(qs)(结果已缓存)', lambda: list(qs))
q('len(qs)(已缓存)', lambda: len(qs))
q('qs[0](已缓存)', lambda: qs[0])
q('qs.count()(已缓存)', lambda: qs.count())
q('qs.exists()(已缓存)', lambda: qs.exists())
""")
print(o); R['basic'] = o
print()
print('== 二:没有缓存时,各种操作各自发的 SQL')
o = run("""
def sql(label, fn):
    with CaptureQueriesContext(connection) as c: r = fn()
    print(f'{label:<34} {len(c)} 次: ' + ' || '.join(x['sql'][:120] for x in c.captured_queries))
    return r
sql('Item.objects.all()[0]', lambda: Item.objects.all()[0])
sql('Item.objects.all()[5:10] 并迭代', lambda: list(Item.objects.all()[5:10]))
sql('qs.count()', lambda: Item.objects.filter(price__gt=10).count())
sql('qs.exists()', lambda: Item.objects.filter(price__gt=10).exists())
sql('bool(qs)', lambda: bool(Item.objects.filter(price__gt=10)))
sql('len(qs)', lambda: len(Item.objects.filter(price__gt=10)))
sql('repr(qs)(比如在 shell 里回车)', lambda: repr(Item.objects.all()))
""")
print(o); R['sql'] = o
print()
print('== 三:同一个 QuerySet:先 exists() 再迭代 / 先迭代再 exists(),各发几次')
o = run("""
qs = Item.objects.filter(price__gt=10)
q('先 qs.exists()', lambda: qs.exists()); q('再 list(qs)', lambda: list(qs)); q('再 qs.exists()(有缓存了)', lambda: qs.exists())
qs2 = Item.objects.filter(price__gt=10)
q('新 qs:先 if qs2: (bool)', lambda: bool(qs2)); q('再 qs2.count()(缓存)', lambda: qs2.count())
qs3 = Item.objects.filter(price__gt=10)
q('新 qs:qs3.iterator() 遍历一遍', lambda: list(qs3.iterator())); q('再 list(qs3)(iterator 不填充缓存)', lambda: list(qs3))
""")
print(o); R['mix'] = o
print()
print('== 四:结果缓存的副作用:迭代后数据库变了,同一个 QuerySet 看不到')
o = run("""
qs = Item.objects.filter(name='cache-test'); print('第一次 list(qs):', list(qs))
Item.objects.create(name='cache-test'); print('新建一条之后再 list(qs)(同一个对象):', list(qs))
print('qs.all() 生成新的 QuerySet 再取:', list(qs.all()))
print('qs.filter() 之后:', list(qs.filter()))
Item.objects.filter(name='cache-test').delete()
""")
print(o); R['stale'] = o
save('d27', R)
