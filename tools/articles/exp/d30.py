import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d30'); R = {}
models = '''
from django.db import models
class Author(models.Model):
    name = models.CharField(max_length=30)
    class Meta: ordering = ['name']
class Tag(models.Model):
    name = models.CharField(max_length=30)
class Book(models.Model):
    title = models.CharField(max_length=60)
    price = models.IntegerField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
    tags = models.ManyToManyField(Tag, related_name='books')
'''
d = proj('d30', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.db.models import *\nfrom django.db.models.functions import Coalesce\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nif not Book.objects.exists():\n    A = Author.objects.bulk_create([Author(name=n) for n in ('ann', 'bob', 'cat', 'dan')])\n    T = Tag.objects.bulk_create([Tag(name=f't{i}') for i in range(3)])\n    data = {'ann': [10, 20, 30], 'bob': [40, 50], 'cat': [60]}\n    for a in A[:3]:\n        for i, p in enumerate(data[a.name]):\n            b = Book.objects.create(title=a.name + str(i), price=p, author=a); b.tags.set(T[:2 + (i % 2)])\ndef sql(qs, tail=True):\n    with CaptureQueriesContext(connection) as c: r = list(qs.all())\n    x = c.captured_queries[-1]['sql']\n    return x[x.index(' FROM '):] if tail else x\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:数据:ann 3 本书(10/20/30),bob 2 本(40/50),cat 1 本(60),dan 没有书;每本书 2~3 个标签')
print('== 二:aggregate 与 annotate:返回值与 SQL')
o = run("""
r = Book.objects.aggregate(total=Sum('price'), avg=Avg('price'), n=Count('id'))
print('aggregate →', r)
print('aggregate SQL:', str(connection.queries[-1]['sql']) if connection.queries else '')
qs = Author.objects.annotate(n=Count('books'), total=Sum('books__price'))
print('annotate →', [(a.name, a.n, a.total) for a in qs])
print('annotate SQL:', sql(qs, False))
print('dan 没有书:Count 是 0,Sum 是', [a.total for a in qs if a.name == 'dan'][0], '→ 用 Coalesce:', [(a.name, a.t) for a in Author.objects.annotate(t=Coalesce(Sum('books__price'), 0))])
""")
print(o); R['basic'] = o
print()
print('== 三:同时对两个多值关系 Count:结果被放大;distinct=True 才对')
o = run("""
qs = Author.objects.annotate(nb=Count('books'), nt=Count('books__tags'))
print('Count("books") + Count("books__tags"):', [(a.name, a.nb, a.nt) for a in qs])
qs = Author.objects.annotate(nb=Count('books', distinct=True), nt=Count('books__tags', distinct=True))
print('都加 distinct=True(注意 nt 现在是「不同标签数」,不是「书-标签对数」):', [(a.name, a.nb, a.nt) for a in qs])
qs = Author.objects.annotate(nb=Count('books'), sp=Sum('books__price'))
print('Count("books") + Sum("books__price"):', [(a.name, a.nb, a.sp) for a in qs])
qs = Author.objects.annotate(nb=Count('books'), sp=Sum('books__price'), nt=Count('books__tags'))
print('再多加一个标签的 Count(nb, sp 也被放大):', [(a.name, a.nb, a.sp, a.nt) for a in qs])
print('SQL:', sql(qs))
""")
print(o); R['multi'] = o
print()
print('== 四:filter 在 annotate 之前还是之后:WHERE 与 HAVING')
o = run("""
q1 = Author.objects.filter(books__price__gt=15).annotate(n=Count('books'))
print('filter(books__price__gt=15).annotate(n=Count("books")):', [(a.name, a.n) for a in q1]); print('  SQL:', sql(q1))
q2 = Author.objects.annotate(n=Count('books')).filter(books__price__gt=15)
print('annotate(n=Count("books")).filter(books__price__gt=15):', [(a.name, a.n) for a in q2]); print('  SQL:', sql(q2))
q3 = Author.objects.annotate(n=Count('books')).filter(n__gt=1)
print('annotate(n=Count("books")).filter(n__gt=1):', [(a.name, a.n) for a in q3]); print('  SQL:', sql(q3))
q4 = Author.objects.annotate(n=Count('books', filter=Q(books__price__gt=15)))
print('Count("books", filter=Q(price>15)):', [(a.name, a.n) for a in q4]); print('  SQL:', sql(q4, False))
""")
print(o); R['filter'] = o
print()
print('== 五:values().annotate() 分组;Meta.ordering 会不会混进 GROUP BY')
o = run("""
q = Book.objects.values('author__name').annotate(n=Count('id'), s=Sum('price')).order_by('author__name')
print(list(q)); print('SQL:', sql(q))
q = Author.objects.annotate(n=Count('books'))
print('Author 的 Meta.ordering = [name];annotate 的 SQL 尾部:', sql(q))
""")
print(o); R['group'] = o
save('d30', R)
