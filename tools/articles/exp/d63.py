import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d63'); R = {}
models = '''
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
def not_forbidden(v):
    if v == 'root': raise ValidationError('用户名 %(v)s 被保留', code='reserved', params={'v': v})
class Acct(models.Model):
    name = models.CharField(max_length=8, validators=[not_forbidden, RegexValidator(r'^[a-z]+$', message='只能小写字母', code='letters')], unique=True)
    age = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(150)], default=1)
'''
d = proj('d63', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom lab.models import Acct\nfrom django import forms\nfrom django.core.exceptions import ValidationError\n" + code); return out.rstrip()
print('== 一:模型字段的 validators 在 save() 时不会运行;full_clean() 才会')
o = run("""
a = Acct(name='ROOT!!!', age=999); a.save(); print('save() 成功,库里存了:', Acct.objects.get(pk=a.pk).name, Acct.objects.get(pk=a.pk).age, '(既违反正则也违反 MaxValue,save() 没有检查)')
try: Acct(name='ROOT!!!', age=999).full_clean()
except ValidationError as e: print('full_clean() →', {k: [x.code for x in v] for k, v in e.error_dict.items()})
""")
print(o); R['save_vs_clean'] = o
print()
print('== 二:所有 validators 都运行、错误累加(不是遇到第一个就停);内置 validator 的 code 与 params')
o = run("""
f = Acct._meta.get_field('name')
for v in ('root', 'ROOT12345'):
    try: f.run_validators(v); print(f'run_validators({v!r}): 通过')
    except ValidationError as e: print(f'run_validators({v!r}) 全部错误:', [(x.code, (x.message % x.params) if x.params else x.message) for x in e.error_list])
try: Acct._meta.get_field('age').run_validators(200)
except ValidationError as e: print('age=200:', [(x.code, x.params) for x in e.error_list])
print('name 字段的 validators 列表(自定义 + 自动加入的 max_length):', [type(v).__name__ if not callable(v) or hasattr(v, 'limit_value') else getattr(v, '__name__', type(v).__name__) for v in f.validators])
""")
print(o); R['run_validators'] = o
print()
print('== 三:ModelForm 会运行模型字段的 validators(在 _post_clean 里调用 instance.full_clean)')
o = run("""
class AF(forms.ModelForm):
    class Meta: model = Acct; fields = ['name', 'age']
f = AF({'name': 'ROOT', 'age': 200}); print('is_valid() =', f.is_valid()); print({k: [(e.code) for e in v.as_data()] for k, v in f.errors.items()})
print('表单字段自带的校验器:', [type(v).__name__ for v in f.fields['age'].validators])
""")
print(o); R['modelform'] = o
print()
print('== 四:unique 校验:full_clean 会查库(validate_unique);save() 才由数据库报 IntegrityError')
o = run("""
Acct.objects.all().delete(); Acct.objects.create(name='dup')
try: Acct(name='dup').full_clean()
except ValidationError as e: print('full_clean():', {k: [x.code for x in v] for k, v in e.error_dict.items()})
from django.db import IntegrityError
try: Acct(name='dup').save()
except IntegrityError as e: print('save() 直接:', type(e).__name__)
""")
print(o); R['unique'] = o
print()
print('== 五:自定义校验器写成可配置的类,并能被迁移序列化(需要 deconstructible)')
o = run("""
from django.utils.deconstruct import deconstructible
@deconstructible
class MaxWords:
    def __init__(self, n): self.n = n
    def __call__(self, v):
        if len(v.split()) > self.n: raise ValidationError('最多 %(n)d 个词', code='max_words', params={'n': self.n})
    def __eq__(self, o): return isinstance(o, MaxWords) and o.n == self.n
print('deconstruct():', MaxWords(3).deconstruct())
try: MaxWords(2)('a b c')
except ValidationError as e: print('校验:', e.code, e.params)
""")
print(o); R['decon'] = o
save('d63', R)
