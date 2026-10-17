import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d32'); R = {}
models = '''
from django.db import models
class Author(models.Model):
    name = models.CharField(max_length=30)
class Book(models.Model):
    title = models.CharField(max_length=60)
    price = models.IntegerField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
'''
d = proj('d32', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.db.models import Q\nfrom lab.models import *\nif not Book.objects.exists():\n    A = Author.objects.bulk_create([Author(name=n) for n in ('ann', 'bob', 'cat', 'dan')])\n    for a, ps in zip(A, ([10, 20, 30], [40, 50], [60], [])):\n        Book.objects.bulk_create([Book(title=f'{a.name}{i}', price=p, author=a) for i, p in enumerate(ps)])\ndef w(qs):\n    s = str(qs.query); return s[s.index(' WHERE '):] if ' WHERE ' in s else '(无 WHERE)'\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:Q 对象的 & | ~ 与 SQL')
o = run("""
for label, q in (('Q(price__gt=15)', Q(price__gt=15)), ('Q(price__gt=15) | Q(title__startswith="a")', Q(price__gt=15) | Q(title__startswith='a')), ('Q(a) & Q(b) | Q(c)', (Q(price__gt=15) & Q(price__lt=50)) | Q(title='ann0')), ('~Q(price__gt=15)', ~Q(price__gt=15)), ('~(Q(a) | Q(b))', ~(Q(price__gt=15) | Q(title='ann0'))), ('filter(Q(a), Q(b)) 两个位置参数', None)):
    if q is None: qs = Book.objects.filter(Q(price__gt=15), Q(price__lt=50))
    else: qs = Book.objects.filter(q)
    print(f'{label:<48}', sorted(b.title for b in qs), '\\n   ', w(qs))
""")
print(o); R['ops'] = o
print()
print('== 二:动态拼条件;空 Q 的含义')
o = run("""
params = {'title__startswith': 'a', 'price__gte': 20, 'price__lte': 999}
q = Q()
for k, v in params.items(): q &= Q(**{k: v})
print('用 &= 逐个拼:', q); print('结果:', sorted(b.title for b in Book.objects.filter(q)))
print('Q() 是空条件:', sorted(b.title for b in Book.objects.filter(Q())), '(不过滤)')
print('Q() | Q(price__gt=50):', sorted(b.title for b in Book.objects.filter(Q() | Q(price__gt=50))), '(空 Q 在 | 里被忽略,而不是「永远为真」)')
q = Q(price__gt=50)
for extra in ([], [Q(title='x')]):
    for e in extra: q |= e
print('OR 拼接 Q(price>50) | Q(title="x"):', sorted(b.title for b in Book.objects.filter(q)))
print('对空列表用 reduce(or_) 要小心:functools.reduce(operator.or_, [], Q()) →', repr(__import__('functools').reduce(__import__('operator').or_, [], Q())))
""")
print(o); R['dyn'] = o
print()
print('== 三:filter(a, b) 与 filter(a).filter(b) —— 多值关系上语义不同')
o = run("""
qa = Author.objects.filter(books__price__gt=25, books__title='ann0')
qb = Author.objects.filter(books__price__gt=25).filter(books__title='ann0')
print('filter(books__price__gt=25, books__title="ann0")            →', sorted(set(a.name for a in qa)), '  INNER JOIN 次数:', str(qa.query).count('INNER JOIN'))
print('filter(books__price__gt=25).filter(books__title="ann0")     →', sorted(set(a.name for a in qb)), '  INNER JOIN 次数:', str(qb.query).count('INNER JOIN'))
print('  ann 的书:ann0(10) ann1(20) ann2(30)。前者要求「同一本书」价格>25 且书名 ann0(不存在);后者是「某本书价格>25(ann2)」且「某本书书名 ann0」(可以是不同的书)')
""")
print(o); R['multi'] = o
print()
print('== 四:exclude() 与多值关系:子查询')
o = run("""
qs = Author.objects.exclude(books__price__gt=45)
print('exclude(books__price__gt=45):', sorted(a.name for a in qs)); print('  ', w(qs)[:260])
qs2 = Author.objects.filter(~Q(books__price__gt=45))
print('filter(~Q(books__price__gt=45)):', sorted(a.name for a in qs2))
qs3 = Author.objects.filter(books__price__lte=45).distinct()
print('对照 filter(books__price__lte=45).distinct():', sorted(a.name for a in qs3), ' ← dan 没有书,不出现;bob 有 40 也出现了(与 exclude 不同)')
""")
print(o); R['excl'] = o
save('d32', R)
