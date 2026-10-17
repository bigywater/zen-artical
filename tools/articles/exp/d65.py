import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d65'); R = {}
models = '''
from django.db import models
class Tag(models.Model):
    name = models.CharField(max_length=20)
class Post(models.Model):
    title = models.CharField(max_length=20)
    owner = models.CharField(max_length=20, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
'''
d = proj('d65', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django import forms\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nfor n in ('a', 'b', 'c'):\n    Tag.objects.get_or_create(name=n)\nT = {t.name: t.pk for t in Tag.objects.all()}\nclass PF(forms.ModelForm):\n    class Meta: model = Post; fields = ['title', 'tags']\ndef q(c): return [' '.join(x['sql'].split())[:100] for x in c.captured_queries]\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:commit=True:一次 save() 就把对象和多对多都写好;SQL')
o = run("""
Post.objects.all().delete()
f = PF({'title': 't1', 'tags': [T['a'], T['b']]}); f.is_valid()
with CaptureQueriesContext(connection) as c: p = f.save()
[print('  ', s) for s in q(c)]; print('  tags =', sorted(t.name for t in p.tags.all()))
""")
print(o); R['commit_true'] = o
print()
print('== 二:commit=False:返回未保存的对象(pk=None);多对多要等 save_m2m()')
o = run("""
Post.objects.all().delete()
f = PF({'title': 't2', 'tags': [T['a'], T['b']]}); f.is_valid()
with CaptureQueriesContext(connection) as c: p = f.save(commit=False)
print('save(commit=False) 发出的查询数:', len(c), ' p.pk =', p.pk, ' 库里 Post 数量:', Post.objects.count())
p.owner = 'me'
with CaptureQueriesContext(connection) as c: p.save()
print('p.save():'); [print('  ', s) for s in q(c)]; print('  此时 tags =', sorted(t.name for t in p.tags.all()), ' ← 多对多还没写')
with CaptureQueriesContext(connection) as c: f.save_m2m()
print('f.save_m2m():'); [print('  ', s) for s in q(c)]; print('  之后 tags =', sorted(t.name for t in p.tags.all()))
print('  form 上有 save_m2m 属性是因为 save(commit=False) 把它挂上去了:', hasattr(f, 'save_m2m'))
""")
print(o); R['commit_false'] = o
print()
print('== 三:忘了 save_m2m():多对多悄悄丢失;还有一种:在 commit=False 之前调用 form.save_m2m 会怎样')
o = run("""
Post.objects.all().delete()
f = PF({'title': 't3', 'tags': [T['c']]}); f.is_valid(); p = f.save(commit=False); p.save()
print('忘了 save_m2m():库里这个 Post 的 tags =', list(p.tags.all()), '(用户选的 c 丢了,没有任何报错)')
f2 = PF({'title': 't4', 'tags': [T['c']]}); f2.is_valid()
print('没调用 save(commit=False) 就用 save_m2m:', end=' ')
try: f2.save_m2m()
except Exception as e: print(type(e).__name__ + ':', e)
""")
print(o); R['forgot'] = o
print()
print('== 四:补上会改字段值的常见写法:在 commit=False 之后设置 owner')
o = run("""
Post.objects.all().delete()
f = PF({'title': 't5', 'tags': [T['a']]}); f.is_valid()
p = f.save(commit=False); p.owner = 'request.user'; p.save(); f.save_m2m()
p = Post.objects.get(title='t5'); print('owner =', p.owner, ' tags =', [t.name for t in p.tags.all()])
""")
print(o); R['owner'] = o
save('d65', R)
