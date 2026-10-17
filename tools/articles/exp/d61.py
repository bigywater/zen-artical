import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d61'); R = {}
models = '''
import datetime
from django.db import models
from django.db.models.signals import post_save
class Author(models.Model):
    name = models.CharField(max_length=30, unique=True)
    def natural_key(self): return (self.name,)
class Book(models.Model):
    title = models.CharField(max_length=30)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    updated = models.DateTimeField(auto_now=True)
    def save(self, *a, **k): self.title = self.title + '!' ; super().save(*a, **k)
CALLED = {'save': 0, 'post_save_raw': 0, 'post_save': 0}
def _ps(sender, raw=False, **kw): CALLED['post_save'] += 1; CALLED['post_save_raw'] += 1 if raw else 0
post_save.connect(_ps, sender=Book)
'''
d = proj('d61', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom lab.models import *\nfrom django.core.management import call_command\nimport io, json\ndef dump(*a, **k):\n    b = io.StringIO(); call_command('dumpdata', *a, stdout=b, **k); return b.getvalue()\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:dumpdata 的输出格式:pk、字段名、外键怎么写;--natural-foreign;--indent')
o = run("""
a = Author.objects.create(name='ann'); Book.objects.create(title='b1', author=a)
print(dump('lab', indent=None)[:400])
print('--natural-foreign:', dump('lab.book', natural_foreign=True)[:300])
print('--natural-primary + --natural-foreign(Author):', dump('lab.author', natural_primary=True, natural_foreign=True)[:200])
print('格式:', [f for f in ('json', 'jsonl', 'xml')])
print('jsonl 首行:', dump('lab.author', format='jsonl').strip()[:120])
""")
print(o); R['dump'] = o
print()
print('== 二:loaddata 不调用模型的 save(),但会发 post_save 信号(raw=True);auto_now 字段用文件里的值')
o = run("""
import tempfile, os
Book.objects.all().delete(); Author.objects.all().delete(); CALLED.update(save=0, post_save=0, post_save_raw=0)
fx = [{'model': 'lab.author', 'pk': 7, 'fields': {'name': 'zed'}}, {'model': 'lab.book', 'pk': 9, 'fields': {'title': 'from-fixture', 'author': 7, 'updated': '2000-01-01T00:00:00Z'}}]
p = os.path.join(tempfile.mkdtemp(), 'f.json'); open(p, 'w').write(json.dumps(fx))
call_command('loaddata', p, verbosity=0)
b = Book.objects.get(pk=9)
print('title =', repr(b.title), '(自定义 save() 会给标题加 "!"——这里没加,说明 loaddata 没调用它)')
print('updated =', b.updated, '(auto_now 没有被改成现在的时间)')
print('post_save 触发次数:', CALLED['post_save'], ' 其中 raw=True:', CALLED['post_save_raw'])
""")
print(o); R['load'] = o
print()
print('== 三:同 pk 再 loaddata 一次 = 覆盖(update);不存在的字段;外键指向不存在的行')
o = run("""
import tempfile, os
fx = [{'model': 'lab.author', 'pk': 7, 'fields': {'name': 'zed2'}}]
p = os.path.join(tempfile.mkdtemp(), 'g.json'); open(p, 'w').write(json.dumps(fx)); call_command('loaddata', p, verbosity=0)
print('pk=7 的作者名字变成:', Author.objects.get(pk=7).name, '; 作者总数:', Author.objects.count())
fx = [{'model': 'lab.author', 'pk': 8, 'fields': {'name': 'x', 'nope': 1}}]
p = os.path.join(tempfile.mkdtemp(), 'h.json'); open(p, 'w').write(json.dumps(fx))
try: call_command('loaddata', p, verbosity=0)
except Exception as e: print('多余字段 →', type(e).__name__ + ':', str(e).splitlines()[-1][:120])
call_command('loaddata', p, verbosity=0, ignorenonexistent=True) if False else None
fx = [{'model': 'lab.book', 'pk': 11, 'fields': {'title': 'orphan', 'author': 999, 'updated': '2000-01-01T00:00:00Z'}}]
p = os.path.join(tempfile.mkdtemp(), 'i.json'); open(p, 'w').write(json.dumps(fx))
try: call_command('loaddata', p, verbosity=0)
except Exception as e: print('外键指向不存在的作者 →', type(e).__name__ + ':', str(e).splitlines()[-1][:140])
""")
print(o); R['edge'] = o
print()
print('== 四:natural key:跨环境 pk 不同时,用名字而不是数字 id 关联')
o = run("""
Book.objects.all().delete(); Author.objects.all().delete()
a = Author.objects.create(name='ann'); Book.objects.create(title='nk', author=a)
js = dump('lab', natural_foreign=True, natural_primary=True); print(js[:340])
""")
print(o); R['natural'] = o
print()
print('== 五:速度:1 万本书 dumpdata / loaddata 的耗时与文件大小')
o = run("""
import time, os, tempfile
Book.objects.all().delete(); Author.objects.all().delete(); a = Author.objects.create(name='bulk')
Book.objects.bulk_create([Book(title=f't{i}', author=a) for i in range(10000)])
t0 = time.perf_counter(); s = dump('lab.book'); t1 = time.perf_counter()
p = os.path.join(tempfile.mkdtemp(), 'big.json'); open(p, 'w').write(s)
Book.objects.all().delete(); t2 = time.perf_counter(); call_command('loaddata', p, verbosity=0); t3 = time.perf_counter()
print('dumpdata 1 万行: %.2f s,文件 %.0f KiB;loaddata 1 万行: %.2f s;表里 %d 行' % (t1 - t0, len(s) / 1024, t3 - t2, Book.objects.count()))
""")
print(o); R['speed'] = o
save('d61', R)
