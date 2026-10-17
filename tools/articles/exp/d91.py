import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d91'); R = {}
models = "from django.db import models\nclass Author(models.Model):\n    name = models.CharField(max_length=20)\n    def __str__(self): return self.name\nclass Post(models.Model):\n    title = models.CharField(max_length=20)\n    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='posts')\n    def __str__(self): return f'{self.title} by {self.author.name}'\n"
tpls = {
    'templates/iter.html': '{% for p in posts %}{{ p.title }};{% endfor %}',
    'templates/iter_twice.html': '{% for p in posts %}{{ p.title }};{% endfor %}|{% for p in posts %}{{ p.title }};{% endfor %}',
    'templates/if_then_for.html': '{% if posts %}{% for p in posts %}{{ p.title }};{% endfor %}{% endif %}',
    'templates/count.html': '{{ posts.count }}|{% for p in posts %}{{ p.title }};{% endfor %}|{{ posts.count }}',
    'templates/length.html': '{{ posts|length }}|{% for p in posts %}{{ p.title }};{% endfor %}',
    'templates/all_each.html': '{% for p in posts.all %}{{ p.title }};{% endfor %}|{% for p in posts.all %}{{ p.title }};{% endfor %}',
    'templates/fk.html': '{% for p in posts %}{{ p.author.name }};{% endfor %}',
    'templates/str.html': '{% for p in posts %}{{ p }};{% endfor %}',
    'templates/related_count.html': '{% for a in authors %}{{ a.name }}={{ a.posts.count }};{% endfor %}',
    'templates/related_all.html': '{% for a in authors %}{{ a.name }}={{ a.posts.all|length }};{% endfor %}',
    'templates/first.html': '{{ posts.0.title }}|{{ posts.first.title }}',
    'templates/emptycheck.html': '{% for p in posts %}{{ p.title }}{% empty %}none{% endfor %}',
}
d = proj('d91', files=dict(tpls, **{'lab/models.py': models}), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom django.template.loader import render_to_string\nfrom lab.models import *\nif not Post.objects.exists():\n    A = Author.objects.bulk_create([Author(name=f'a{i}') for i in range(5)]); Post.objects.bulk_create([Post(title=f't{i}', author=A[i % 5]) for i in range(20)])\ndef n(tpl, **ctx):\n    with CaptureQueriesContext(connection) as c: render_to_string(tpl, ctx)\n    return len(c)\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:模板里对 QuerySet 的各种用法,发出的查询次数(20 篇文章、5 个作者)')
o = run("""
qs = lambda: Post.objects.all()
rows = [
 ('for p in posts(遍历一次)', n('iter.html', posts=qs())),
 ('遍历两次(同一个 QuerySet 对象)', n('iter_twice.html', posts=qs())),
 ('{% if posts %} 再 for', n('if_then_for.html', posts=qs())),
 ('{{ posts.count }} + for + {{ posts.count }}', n('count.html', posts=qs())),
 ('{{ posts|length }} + for', n('length.html', posts=qs())),
 ('{% for p in posts.all %} 写两次(每次 .all 产生新 QuerySet)', n('all_each.html', posts=qs())),
 ('{{ posts.0.title }} 和 {{ posts.first.title }}', n('first.html', posts=qs())),
 ('{% for %}{% empty %}', n('emptycheck.html', posts=qs())),
]
for label, q in rows: print(f'  {label:<52} {q} 次')
""")
print(o); R['basic'] = o
print()
print('== 二:遍历里访问外键 / __str__ / 反向关系:N+1 就藏在这些「看起来没查」的地方')
o = run("""
rows = [
 ('p.author.name(不优化)', n('fk.html', posts=Post.objects.all())),
 ('p.author.name + select_related("author")', n('fk.html', posts=Post.objects.select_related('author'))),
 ('{{ p }}(__str__ 里用了 self.author.name)不优化', n('str.html', posts=Post.objects.all())),
 ('{{ p }} + select_related("author")', n('str.html', posts=Post.objects.select_related('author'))),
 ('a.posts.count(每个作者一次 COUNT)', n('related_count.html', authors=Author.objects.all())),
 ('a.posts.all|length(每个作者一次查询)', n('related_all.html', authors=Author.objects.all())),
 ('a.posts.all|length + prefetch_related("posts")', n('related_all.html', authors=Author.objects.prefetch_related('posts'))),
 ('a.posts.count + prefetch_related("posts")(count 用预取好的缓存)', n('related_count.html', authors=Author.objects.prefetch_related('posts'))),
]
for label, q in rows: print(f'  {label:<58} {q} 次')
""")
print(o); R['fk'] = o
print()
print('== 三:在视图里先求值、再传给模板:一劳永逸')
o = run("""
posts = list(Post.objects.select_related('author'))
print('传 list 给 iter_twice.html:', n('iter_twice.html', posts=posts), '次(list 已经在内存里)')
print('传 list 给 length.html:', n('length.html', posts=posts), '次')
""")
print(o); R['list'] = o
save('d91', R)
