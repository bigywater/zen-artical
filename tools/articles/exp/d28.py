import sys, os, time, json, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d28'); R = {}
models = '''
from django.db import models
class Author(models.Model):
    name = models.CharField(max_length=30)
class Tag(models.Model):
    name = models.CharField(max_length=30)
class Book(models.Model):
    title = models.CharField(max_length=60)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
    tags = models.ManyToManyField(Tag, related_name='books')
'''
d = proj('d28', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, time, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nif not Book.objects.exists():\n    A = Author.objects.bulk_create([Author(name=f'a{i}') for i in range(100)]); T = Tag.objects.bulk_create([Tag(name=f't{i}') for i in range(20)])\n    Bs = Book.objects.bulk_create([Book(title=f'b{i}', author=A[i % 100]) for i in range(2000)])\n    Through = Book.tags.through\n    Through.objects.bulk_create([Through(book_id=b.id, tag_id=T[(b.id + k) % 20].id) for b in Bs for k in range(3)])\ndef measure(label, fn, reps=5):\n    best = 1e9; n = 0\n    for _ in range(reps):\n        connection.queries_log.clear()\n        with CaptureQueriesContext(connection) as c:\n            t0 = time.perf_counter(); fn(); dt = time.perf_counter() - t0\n        best = min(best, dt); n = len(c)\n    print(f'{label:<46} 查询 {n:>5} 次   {best*1000:8.1f} ms'); return c, n, best*1000\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:2000 本书、100 个作者、20 个标签(每本书 3 个标签):取书名和作者名')
o = run("""
def naive(): return [(b.title, b.author.name) for b in Book.objects.all()]
def sel(): return [(b.title, b.author.name) for b in Book.objects.select_related('author')]
def pf(): return [(b.title, b.author.name) for b in Book.objects.prefetch_related('author')]
for label, fn in (('不优化(每本书访问 author 查一次)', naive), ('select_related("author")', sel), ('prefetch_related("author")', pf)): measure(label, fn)
""")
print(o); R['fk'] = o
print()
print('== 二:多对多:取书名和标签名')
o = run("""
def naive(): return [(b.title, [t.name for t in b.tags.all()]) for b in Book.objects.all()]
def pf(): return [(b.title, [t.name for t in b.tags.all()]) for b in Book.objects.prefetch_related('tags')]
def sel_try():
    try: list(Book.objects.select_related('tags')[:1])
    except Exception as e: print('  select_related("tags") →', type(e).__name__ + ':', str(e)[:130])
measure('不优化', naive); measure('prefetch_related("tags")', pf); sel_try()
""")
print(o); R['m2m'] = o
print()
print('== 三:两种方式实际发出的 SQL')
o = run("""
with CaptureQueriesContext(connection) as c: list(Book.objects.select_related('author')[:2])
print('select_related:'); [print('  ', x['sql'][:260]) for x in c.captured_queries]
with CaptureQueriesContext(connection) as c: list(Book.objects.prefetch_related('tags')[:2])
print('prefetch_related:'); [print('  ', x['sql'][:260]) for x in c.captured_queries]
""")
print(o); R['sql'] = o
print()
print('== 四:反向外键(一对多)只能 prefetch;Prefetch 对象可以带过滤')
o = run("""
def naive(): return [(a.name, len(list(a.books.all()))) for a in Author.objects.all()]
def pf(): return [(a.name, len(a.books.all())) for a in Author.objects.prefetch_related('books')]
measure('100 个作者各查一次书', naive); c, n, ms = measure('prefetch_related("books")', pf)
from django.db.models import Prefetch
def pfilter(): return [(a.name, len(a.books.all())) for a in Author.objects.prefetch_related(Prefetch('books', queryset=Book.objects.filter(id__lte=200), to_attr='early'))]
with CaptureQueriesContext(connection) as c: r = [(a.name, len(a.early)) for a in Author.objects.prefetch_related(Prefetch('books', queryset=Book.objects.filter(id__lte=200), to_attr='early'))]
print('Prefetch(queryset=filter, to_attr) 的查询数:', len(c), ' SQL 2:', c.captured_queries[1]['sql'][:200] + '...')
print('  前 3 个作者带回的书数量:', [x[1] for x in r[:3]])
print('过滤后再访问原属性 a.books.all() 会不会多一次查询?')
with CaptureQueriesContext(connection) as c:
    for a in Author.objects.prefetch_related(Prefetch('books', queryset=Book.objects.filter(id__lte=200))): a.books.filter(id__lte=100).count()
print('  在预取的属性上再 .filter(...) 的查询数(100 个作者):', len(c))
""")
print(o); R['reverse'] = o
save('d28', R)
