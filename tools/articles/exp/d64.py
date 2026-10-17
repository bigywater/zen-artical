import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d64'); R = {}
models = '''
from django.db import models
class Author(models.Model):
    name = models.CharField(max_length=20)
class Post(models.Model):
    title = models.CharField(max_length=20)
    body = models.TextField(blank=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True)
'''
d = proj('d64', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django import forms\nfrom lab.models import *\na = Author.objects.first() or Author.objects.create(name='ann')\n" + code); return out.rstrip()
print('== 一:ModelForm 由模型字段自动生成表单字段:类型、必填、选项')
o = run("""
class PF(forms.ModelForm):
    class Meta: model = Post; fields = '__all__'
f = PF()
for n, fl in f.fields.items(): print(f'  {n:<12} {type(fl).__name__:<18} required={fl.required!s:<5} widget={type(fl.widget).__name__}')
print('  没出现的模型字段(不可编辑):', sorted(set(x.name for x in Post._meta.fields) - set(f.fields)))
""")
print(o); R['gen'] = o
print()
print('== 二:Meta.fields 与批量赋值:fields = "__all__" 会让用户提交 is_featured')
o = run("""
class Open(forms.ModelForm):
    class Meta: model = Post; fields = '__all__'
class Safe(forms.ModelForm):
    class Meta: model = Post; fields = ['title', 'body', 'slug', 'author']
data = {'title': 't', 'slug': 's1', 'author': a.pk, 'is_featured': 'on', 'published': 'on'}
f = Open(data); f.is_valid(); p = f.save(); print('fields="__all__":用户额外提交 is_featured/published → 保存后 is_featured =', p.is_featured, ' published =', p.published)
data['slug'] = 's2']; f = Safe(data); f.is_valid(); p = f.save(); print('fields=[...] 白名单:同样的提交 → is_featured =', p.is_featured, ' published =', p.published, '(多余字段被忽略)')
""".replace("data['slug'] = 's2']", "data['slug'] = 's2'"))
print(o); R['mass'] = o
print()
print('== 三:ModelForm 的校验包括模型校验:unique、模型字段 validators、模型的 clean()')
o = run("""
class SF(forms.ModelForm):
    class Meta: model = Post; fields = ['title', 'slug', 'author']
Post.objects.all().delete(); Post.objects.create(title='x', slug='taken', author=a)
f = SF({'title': 't', 'slug': 'taken', 'author': a.pk}); print('slug 重复 → is_valid() =', f.is_valid(), {k: [(e.code, e.message) for e in v.as_data()] for k, v in f.errors.items()})
f = SF({'title': 'x' * 30, 'slug': 'new', 'author': a.pk}); f.is_valid(); print('title 超长 →', {k: [e.code for e in v.as_data()] for k, v in f.errors.items()})
f = SF({'title': 't', 'slug': 'Bad Slug!', 'author': a.pk}); f.is_valid(); print('slug 格式错 →', {k: [e.code for e in v.as_data()] for k, v in f.errors.items()})
f = SF({'title': 't', 'slug': 'ok', 'author': 9999}); f.is_valid(); print('author 不存在 →', {k: [e.code for e in v.as_data()] for k, v in f.errors.items()})
""")
print(o); R['valid'] = o
print()
print('== 四:instance 是什么时候被填充的;编辑已有对象;is_valid() 失败时 instance 已经被改了')
o = run("""
class SF(forms.ModelForm):
    class Meta: model = Post; fields = ['title', 'slug', 'author']
Post.objects.all().delete(); p = Post.objects.create(title='orig', slug='orig', author=a)
f = SF({'title': 'changed', 'slug': '', 'author': a.pk}, instance=p); print('构造后 instance.title =', p.title)
ok = f.is_valid(); print('is_valid() =', ok, '(slug 必填,失败)', ' 此时 instance.title =', p.title, '← 内存里的对象已被改成用户提交的值', ' 库里 =', Post.objects.get(pk=p.pk).title)
f = SF({'title': 'changed', 'slug': 'orig', 'author': a.pk}, instance=p); f.is_valid(); print('校验通过、还没 save():库里 =', Post.objects.get(pk=p.pk).title); f.save(); print('save() 之后库里 =', Post.objects.get(pk=p.pk).title)
""")
print(o); R['instance'] = o
save('d64', R)
