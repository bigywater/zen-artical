import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d37'); R = {}
models = '''
from django.db import models
class ActiveManager(models.Manager):
    def get_queryset(self): return super().get_queryset().filter(deleted=False)
class BookQuerySet(models.QuerySet):
    def cheap(self): return self.filter(price__lt=30)
    def by(self, name): return self.filter(author__name=name)
class Author(models.Model):
    name = models.CharField(max_length=20)
    deleted = models.BooleanField(default=False)
    objects = ActiveManager()
    all_objects = models.Manager()
    def __str__(self): return self.name
class Book(models.Model):
    title = models.CharField(max_length=20)
    price = models.IntegerField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
    objects = BookQuerySet.as_manager()
'''
d = proj('d37', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nif not Author.all_objects.exists():\n    a = Author.all_objects.create(name='ann'); g = Author.all_objects.create(name='ghost', deleted=True)\n    Book.objects.create(title='b1', price=10, author=a); Book.objects.create(title='b2', price=50, author=a); Book.objects.create(title='gb', price=20, author=g)\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:自定义 QuerySet + as_manager():方法可以链在任何位置')
o = run("""
print('Book.objects.cheap()             →', [b.title for b in Book.objects.cheap()])
print('Book.objects.filter(...).cheap() →', [b.title for b in Book.objects.filter(price__gt=5).cheap()])
print('Book.objects.by("ann").cheap()   →', [b.title for b in Book.objects.by('ann').cheap()])
print('类型:', type(Book.objects).__name__, '/', type(Book.objects.filter(price__gt=1)).__name__)
""")
print(o); R['qs'] = o
print()
print('== 二:覆盖默认 Manager 的 get_queryset(软删除):objects 看不到已删除的')
o = run("""
print('Author.objects.all()      →', [a.name for a in Author.objects.all()])
print('Author.all_objects.all()  →', [a.name for a in Author.all_objects.all()])
print('Author._default_manager 是', type(Author._default_manager).__name__, '(模型里第一个定义的 Manager)')
print('Author._base_manager 是', type(Author._base_manager).__name__)
try: Author.objects.get(name='ghost')
except Exception as e: print("Author.objects.get(name='ghost') →", type(e).__name__)
""")
print(o); R['soft'] = o
print()
print('== 三:关系访问不走 objects:已软删除的作者仍然能通过 book.author 取到')
o = run("""
gb = Book.objects.get(title='gb')
print('gb.author →', gb.author, ' deleted =', gb.author.deleted, '(关联对象访问使用 _base_manager,不受 objects 过滤)')
print('Book.objects.filter(author__name="ghost") →', [b.title for b in Book.objects.filter(author__name='ghost')], '(JOIN 也不受影响)')
print('ann.books.all() →', [b.title for b in Author.objects.get(name='ann').books.all()], ' related manager 的类:', type(Author.objects.get(name='ann').books).__name__)
""")
print(o); R['rel'] = o
print()
print('== 四:Meta.default_manager_name / base_manager_name 与 Manager 顺序')
o = run("""
from django.db import models
print('Author._meta.managers 顺序:', [m.name for m in Author._meta.managers])
print('Book._meta.managers 顺序  :', [m.name for m in Book._meta.managers])
""")
print(o); R['order'] = o
save('d37', R)
