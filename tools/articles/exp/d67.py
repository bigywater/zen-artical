import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d67'); R = {}
models = '''
from django.db import models
class Author(models.Model):
    name = models.CharField(max_length=20)
    def __str__(self): return self.name
class Book(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    title = models.CharField(max_length=20)
    editor = models.ForeignKey('Editor', on_delete=models.SET_NULL, null=True, blank=True)
class Editor(models.Model):
    name = models.CharField(max_length=20)
    def __str__(self): return self.name
'''
d = proj('d67', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django import forms\nfrom django.forms import formset_factory, inlineformset_factory, modelformset_factory\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nEd = [Editor.objects.get_or_create(name=f'e{i}')[0] for i in range(20)]\nauthor = Author.objects.first() or Author.objects.create(name='ann')\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:ManagementForm:TOTAL_FORMS / INITIAL_FORMS;缺了它会怎样')
o = run("""
class RF(forms.Form): x = forms.IntegerField()
FS = formset_factory(RF, extra=2)
fs = FS(); print('未绑定 FormSet 的 management_form 初始值:', {k: v for k, v in fs.management_form.initial.items()})
print('渲染出的隐藏字段:', [str(w)[:60] for w in fs.management_form][:2])
data = {'form-TOTAL_FORMS': '2', 'form-INITIAL_FORMS': '0', 'form-0-x': '1', 'form-1-x': '2'}
fs = FS(data); print('有 ManagementForm:is_valid() =', fs.is_valid(), ' cleaned =', [f.cleaned_data for f in fs])
fs = FS({'form-0-x': '1', 'form-1-x': '2'}); print('缺 ManagementForm:is_valid() =', fs.is_valid(), ' non_form_errors =', list(fs.non_form_errors())[:1], ' code =', fs.non_form_errors().as_data()[0].code)
""")
print(o); R['mgmt'] = o
print()
print('== 二:extra / min_num / validate_min / max_num / can_delete;TOTAL_FORMS 由客户端提交')
o = run("""
class RF(forms.Form): x = forms.IntegerField(required=False)
FS = formset_factory(RF, extra=1, min_num=2, validate_min=True, max_num=3, validate_max=True, can_delete=True)
fs = FS(); print('未绑定:表单数 =', len(fs.forms), '(min_num 2 + extra 1)')
fs = FS({'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '0', 'form-0-x': '1'}); print('只提交 1 个:is_valid() =', fs.is_valid(), list(fs.non_form_errors()))
fs = FS({'form-TOTAL_FORMS': '5', 'form-INITIAL_FORMS': '0', **{f'form-{i}-x': str(i) for i in range(5)}}); print('提交 5 个(max_num=3):is_valid() =', fs.is_valid(), list(fs.non_form_errors()))
fs = FS({'form-TOTAL_FORMS': '3', 'form-INITIAL_FORMS': '0', 'form-0-x': '1', 'form-1-x': '2', 'form-2-x': '3', 'form-1-DELETE': 'on'}); fs.is_valid(); print('第 2 个勾选 DELETE:cleaned_data =', [f.cleaned_data for f in fs], ' deleted_forms =', len(fs.deleted_forms))
""")
print(o); R['limits'] = o
print()
print('== 三:InlineFormSet:父对象与外键自动关联,并保存')
o = run("""
Book.objects.all().delete()
BFS = inlineformset_factory(Author, Book, fields=['title'], extra=2, can_delete=True)
data = {'book_set-TOTAL_FORMS': '2', 'book_set-INITIAL_FORMS': '0', 'book_set-0-title': 'b1', 'book_set-1-title': 'b2'}
fs = BFS(data, instance=author); print('is_valid =', fs.is_valid(), ' 表单字段:', list(fs.forms[0].fields))
with CaptureQueriesContext(connection) as c: objs = fs.save()
print('save() 发出的查询数:', len(c), ' 保存的对象:', [(o.title, o.author_id == author.pk) for o in objs])
fs2 = BFS(instance=author); print('再打开编辑页:表单数 =', len(fs2.forms), ' (2 个已有 + extra 2)  INITIAL_FORMS =', fs2.management_form.initial['INITIAL_FORMS'])
""")
print(o); R['inline'] = o
print()
print('== 四:每个表单一个 ModelChoiceField 时的查询次数(20 个 editor 选项)')
o = run("""
Book.objects.all().delete(); Book.objects.bulk_create([Book(author=author, title=f'b{i}') for i in range(10)])
BFS = inlineformset_factory(Author, Book, fields=['title', 'editor'], extra=0)
with CaptureQueriesContext(connection) as c:
    fs = BFS(instance=author); html = str(fs)
print('10 本书、每本一个 editor 下拉框,渲染整个 FormSet 的查询数:', len(c))
sel = [' '.join(x['sql'].split())[:70] for x in c.captured_queries]; from collections import Counter; print('   查询种类:', dict(Counter(sel)))
""")
print(o); R['nplus'] = o
save('d67', R)
