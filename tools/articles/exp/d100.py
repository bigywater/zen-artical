import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d100'); R = {}
models = '''
from django.db import models
class Category(models.Model):
    name = models.CharField(max_length=20)
    def __str__(self): return self.name
class Author(models.Model):
    name = models.CharField(max_length=20)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    def __str__(self): return f'{self.name} ({self.category.name})'
class Post(models.Model):
    title = models.CharField(max_length=20)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    def author_name(self): return self.author.name
    @property
    def label(self): return f'{self.title}/{self.author.category.name}'
    def __str__(self): return f'{self.title} by {self.author}'
'''
admin_py = '''
from django.contrib import admin
from .models import Post, Author, Category
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author')
@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
admin.site.register(Category)
'''
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.admin', 'django.contrib.sessions', 'django.contrib.messages', 'lab']
MW = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware']
TPL = "\nTEMPLATES[0]['OPTIONS']['context_processors'] += ['django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']\n"
urls = "from django.contrib import admin\nfrom django.urls import path\nurlpatterns = [path('admin/', admin.site.urls)]\n"
def build(admin_src):
    d = proj('d100', files={'lab/models.py': models, 'lab/admin.py': admin_src}, urls=urls, apps=apps, middleware=MW, settings_extra=TPL); manage(d, 'makemigrations', 'lab'); manage(d, 'migrate'); return d
def run(d, code): rc, out = pyscript(d, "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom django.contrib.auth.models import User\nfrom lab.models import *\nUser.objects.filter(username='root').delete(); root = User.objects.create_superuser('root', password='x')\nif not Post.objects.exists():\n    cats = Category.objects.bulk_create([Category(name=f'c{i}') for i in range(3)]); au = Author.objects.bulk_create([Author(name=f'a{i}', category=cats[i % 3]) for i in range(10)]); Post.objects.bulk_create([Post(title=f't{i}', author=au[i % 10]) for i in range(50)])\nc = Client(); c.force_login(root)\ndef q(url):\n    with CaptureQueriesContext(connection) as ctx: r = c.get(url)\n    return r.status_code, len(ctx)\n" + code); return out.rstrip()
print('== 一:admin 列表页(50 篇文章、10 个作者、3 个分类):list_display 里放外键')
d = build(admin_py)
o = run(d, """
print('文章列表 list_display=(title, author)      → status, 查询数 =', q('/admin/lab/post/'))
print('作者列表 list_display=(name, category)      → status, 查询数 =', q('/admin/lab/author/'))
""")
print(o); R['default'] = o
print()
print('== 二:为什么 admin 会 N+1:Post.__str__ 又调用 Author.__str__(里面用 category)——一路嵌套')
o = run(d, """
posts = list(Post.objects.all()[:5])
with CaptureQueriesContext(connection) as ctx: [str(p) for p in posts]
print('5 篇文章各 str(p) 的查询数:', len(ctx), '(每篇:取 author + 取 category = 2 次)')
with CaptureQueriesContext(connection) as ctx: [p.label for p in Post.objects.all()[:5]]
print('property label(author.category.name)5 篇:', len(ctx), ' (含 1 次取文章列表)')
""")
print(o); R['str'] = o
print()
print('== 三:list_select_related / get_queryset 优化后')
admin_fixed = admin_py.replace("list_display = ('title', 'author')", "list_display = ('title', 'author')\n    list_select_related = ('author__category',)").replace("list_display = ('name', 'category')", "list_display = ('name', 'category')\n    list_select_related = ('category',)")
d2 = build(admin_fixed)
o = run(d2, """
print('文章列表 list_select_related=("author__category") → 查询数 =', q('/admin/lab/post/')[1])
print('作者列表 list_select_related=("category")          → 查询数 =', q('/admin/lab/author/')[1])
""")
print(o); R['fixed'] = o
print()
print('== 四:不同数据量下的查询数(文章数 10 / 50 / 200):没优化 vs 优化')
R['scale'] = {}
for n in (10, 50, 200):
    row = {}
    for label, src in (('未优化', admin_py), ('优化', admin_fixed)):
        dd = build(src)
        o = run(dd, f"Post.objects.all().delete()\nau = list(Author.objects.all())\nPost.objects.bulk_create([Post(title=f'x{{i}}', author=au[i % len(au)]) for i in range({n})])\nprint(q('/admin/lab/post/')[1])")
        row[label] = int(o.strip().splitlines()[-1])
    R['scale'][n] = row; print(f'  {n:>4} 篇文章:未优化 {row["未优化"]} 次查询;优化后 {row["优化"]} 次')
save('d100', R)
