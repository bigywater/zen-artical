import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d39'); R = {}
pg = PG(9403).start()
models = '''
from django.db import models
from django.db.models import Lookup, Transform, Field, IntegerField
from django.db.models.functions import Lower
@Field.register_lookup
class NotEqual(Lookup):
    lookup_name = 'ne'
    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return '%s <> %s' % (lhs, rhs), tuple(lhs_params) + tuple(rhs_params)
@Field.register_lookup
class AbsoluteValue(Transform):
    lookup_name = 'abs'
    function = 'ABS'
    @property
    def output_field(self): return IntegerField()
class Person(models.Model):
    name = models.CharField(max_length=40)
    score = models.IntegerField(default=0)
    class Meta:
        indexes = [models.Index(Lower('name'), name='person_lower_name_idx')]
'''
d = proj('d39', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.db.models.functions import Lower\nfrom django.db.models import CharField\nfrom lab.models import Person\nif not Person.objects.exists():\n    Person.objects.bulk_create([Person(name=f'Name{i}', score=i - 500) for i in range(20000)])\n    with connection.cursor() as c: c.execute('ANALYZE lab_person')\ndef w(qs):\n    s = str(qs.query); return s[s.index(' WHERE '):] if ' WHERE ' in s else s\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:自定义 Lookup(__ne)与 Transform(__abs):SQL')
o = run("""
qs = Person.objects.filter(score__ne=5); print('score__ne=5          →', w(qs), '  行数:', qs.count())
qs = Person.objects.filter(score__abs=5); print('score__abs=5         →', w(qs), '  行数:', qs.count())
qs = Person.objects.filter(score__abs__gt=498); print('score__abs__gt=498   →', w(qs), '  行数:', qs.count())
qs = Person.objects.filter(score__abs__ne=5); print('score__abs__ne=5     →', w(qs), '  行数:', qs.count())
""")
print(o); R['sql'] = o
print()
print('== 二:Transform 也可以出现在 values() / order_by 里;同一个 Transform 注册在字段类上就对所有该类字段生效')
o = run("""
print('values_list("score__abs")[:3] →', list(Person.objects.order_by('id').values_list('score__abs', flat=True)[:3]))
print('order_by("score__abs").first().score =', Person.objects.order_by('score__abs', 'id').first().score)
print('CharField 上有 abs 吗:', end=' ')
try: list(Person.objects.filter(name__abs=1))
except Exception as e: print(type(e).__name__ + ':', str(e)[:120])
""")
print(o); R['misc'] = o
print()
print('== 三:与函数索引配合:Lower(name) 的索引;icontains / iexact 是否用得上(PostgreSQL EXPLAIN)')
o = run("""
def plan(qs):
    from django.db import connection
    sql, params = qs.query.sql_with_params()
    with connection.cursor() as c: c.execute('EXPLAIN ' + sql, params); return [r[0] for r in c.fetchall()]
def first(p): return p[0].strip()[:110]
qs = Person.objects.annotate(l=Lower('name')).filter(l='name777'); print('annotate(Lower).filter(l="name777")   →', first(plan(qs)))
qs = Person.objects.filter(name__iexact='name777'); print('filter(name__iexact="name777")       →', first(plan(qs)), '  SQL:', w(qs)[:80])
qs = Person.objects.filter(name='Name777'); print('filter(name="Name777")               →', first(plan(qs)))
""")
print(o); R['plan'] = o
print()
print('== 四:注册在 Field 基类上:IntegerField / CharField 等所有字段类型都能看到')
o = run("""
from django.db.models import IntegerField
print("IntegerField().get_lookup('ne') =", IntegerField().get_lookup('ne').__name__, ' CharField().get_lookup(ne) =', CharField().get_lookup('ne').__name__)
print('IntegerField 共有 %d 个 lookup,含 ne:' % len(IntegerField().get_lookups()), 'ne' in IntegerField().get_lookups(), ' get_transform(abs) =', IntegerField().get_transform('abs').__name__)
""")
print(o); R['reg'] = o
pg.stop(); save('d39', R)
