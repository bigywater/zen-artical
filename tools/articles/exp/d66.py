import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d66'); R = {}
models = '''
from django.db import models
class Tag(models.Model):
    name = models.CharField(max_length=20)
class Post(models.Model):
    title = models.CharField(max_length=20)
    tags = models.ManyToManyField(Tag, blank=True)
class Member(models.Model):
    name = models.CharField(max_length=20)
class Team(models.Model):
    name = models.CharField(max_length=20)
    members = models.ManyToManyField(Member, through='Membership')
class Membership(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, default='dev')
'''
d = proj('d66', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django import forms\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nfor n in ('a', 'b', 'c', 'd'): Tag.objects.get_or_create(name=n)\nT = {t.name: t.pk for t in Tag.objects.all()}\nclass PF(forms.ModelForm):\n    class Meta: model = Post; fields = ['title', 'tags']\ndef q(c): return [' '.join(x['sql'].split())[:120] for x in c.captured_queries if 'SAVEPOINT' not in x['sql']]\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:编辑已有对象:标签从 {a, b} 改成 {b, c}。SQL 只动变化的部分(set() 做差集)')
o = run("""
Post.objects.all().delete(); p = Post.objects.create(title='p'); p.tags.set([T['a'], T['b']])
f = PF({'title': 'p', 'tags': [T['b'], T['c']]}, instance=p); f.is_valid()
with CaptureQueriesContext(connection) as c: f.save()
[print('  ', s) for s in q(c)]; print('  之后 tags =', sorted(t.name for t in p.tags.all()))
""")
print(o); R['diff'] = o
print()
print('== 二:提交空的多选:blank=True 时清空;不选则清掉全部')
o = run("""
Post.objects.all().delete(); p = Post.objects.create(title='p'); p.tags.set([T['a'], T['b']])
f = PF({'title': 'p'}, instance=p); print('is_valid =', f.is_valid()); f.save(); print('  没提交 tags 字段(等同于全部取消勾选)后 tags =', list(p.tags.all()))
class Req(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=True)
    class Meta: model = Post; fields = ['title', 'tags']
f = Req({'title': 'p'}); f.is_valid(); print('  required=True 时:', {k: [e.code for e in v.as_data()] for k, v in f.errors.items()})
""")
print(o); R['empty'] = o
print()
print('== 三:非法的选项 id;queryset 限制可选范围')
o = run("""
f = PF({'title': 'p', 'tags': [T['a'], 99999]}); f.is_valid(); print('含不存在的 id:', {k: [(e.code, e.params) for e in v.as_data()] for k, v in f.errors.items()})
class Lim(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.filter(name__in=['a', 'b']))
    class Meta: model = Post; fields = ['title', 'tags']
f = Lim({'title': 'p', 'tags': [T['d']]}); f.is_valid(); print('不在 queryset 里的 id(d):', {k: [e.code for e in v.as_data()] for k, v in f.errors.items()})
""")
print(o); R['invalid'] = o
print()
print('== 四:自定义 through 模型(带额外字段 role):ModelForm 仍能保存,额外字段只能取默认值')
o = run("""
class TF(forms.ModelForm):
    class Meta: model = Team; fields = ['name', 'members']
try:
    print('TeamForm 字段:', list(TF().fields))
except Exception as e: print('构造 TeamForm →', type(e).__name__ + ':', str(e)[:150])
print('Team.members 的 through 是自定义模型:', Team._meta.get_field('members').remote_field.through.__name__)
m = Member.objects.create(name='m1'); t = Team.objects.create(name='t')
f = TF({'name': 't2', 'members': [m.pk]}); print('  TeamForm 提交 members:is_valid =', f.is_valid())
try:
    with CaptureQueriesContext(connection) as c: t2 = f.save()
    print('  save() 成功;SQL:'); [print('    ', s_) for s_ in q(c)]; print('  Membership 里的行:', list(Membership.objects.filter(team=t2).values_list('member__name', 'role')), '(role 用 default)')
except Exception as e: print('  save() →', type(e).__name__ + ':', str(e)[:150])
""")
print(o); R['through'] = o
save('d66', R)
