import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d29'); R = {}
models = '''
from django.db import models
class Author(models.Model):
    name = models.CharField(max_length=30)
class Article(models.Model):
    title = models.CharField(max_length=60)
    body = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
'''
d = proj('d29', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, time, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nif not Article.objects.exists():\n    A = Author.objects.bulk_create([Author(name=f'a{i}') for i in range(10)])\n    Article.objects.bulk_create([Article(title=f't{i}', body='B' * 10000, author=A[i % 10]) for i in range(2000)])\ndef measure(label, fn, reps=5):\n    best = 1e9; n = 0\n    for _ in range(reps):\n        connection.queries_log.clear()\n        with CaptureQueriesContext(connection) as c:\n            t0 = time.perf_counter(); fn(); dt = time.perf_counter() - t0\n        best = min(best, dt); n = len(c)\n    print(f'{label:<50} 查询 {n:>5} 次   {best*1000:8.1f} ms'); return n, best*1000\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:only() / defer() 生成的 SQL,以及被推迟的字段')
o = run("""
def sql(label, qs):
    with CaptureQueriesContext(connection) as c: list(qs[:1])
    print(f'{label:<30}', c.captured_queries[0]['sql'].replace('"lab_article".', '').replace('FROM "lab_article" LIMIT 1', ''))
sql('all()', Article.objects.all()); sql("only('title')", Article.objects.only('title')); sql("defer('body')", Article.objects.defer('body')); sql("only('title', 'author__name')+select_related", Article.objects.select_related('author').only('title', 'author__name'))
a = Article.objects.only('title').first(); print("only('title') 的实例 get_deferred_fields() =", sorted(a.get_deferred_fields()))
a = Article.objects.defer('body').first(); print("defer('body') 的实例 get_deferred_fields() =", sorted(a.get_deferred_fields()))
""")
print(o); R['sql'] = o
print()
print('== 二:访问被推迟的字段:每个实例一次额外查询(N+1 的另一种形态)')
o = run("""
def only_then_body(): return [len(a.body) for a in Article.objects.only('title')[:200]]
def only_title(): return [a.title for a in Article.objects.only('title')[:200]]
def all_fields(): return [len(a.body) for a in Article.objects.all()[:200]]
measure('200 行 all() 读 body', all_fields); measure("200 行 only('title') 只读 title", only_title); measure("200 行 only('title') 又读了 body", only_then_body)
""")
print(o); R['n1'] = o
print()
print('== 三:2000 行、每行 body 约 10 KB:不同取法的耗时')
o = run("""
measure('Article.objects.all()(取全部字段)', lambda: [a.title for a in Article.objects.all()])
measure("defer('body')", lambda: [a.title for a in Article.objects.defer('body')])
measure("only('title')", lambda: [a.title for a in Article.objects.only('title')])
measure("values_list('title', flat=True)", lambda: list(Article.objects.values_list('title', flat=True)))
""")
print(o); R['perf'] = o
print()
print('== 四:对带推迟字段的实例 save():UPDATE 里有哪些列;refresh_from_db 取回字段')
o = run("""
a = Article.objects.only('title').first(); a.title = 'changed'
with CaptureQueriesContext(connection) as c: a.save()
print('only("title") 实例 save() 的 SQL:', c.captured_queries[-1]['sql'][:200])
with CaptureQueriesContext(connection) as c: a.refresh_from_db(fields=['body']); 
print('refresh_from_db(fields=["body"]) 的 SQL:', c.captured_queries[0]['sql'][:160], ' | 之后 deferred =', sorted(a.get_deferred_fields()))
""")
print(o); R['save'] = o
save('d29', R)
