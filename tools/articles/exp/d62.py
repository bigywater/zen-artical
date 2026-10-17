import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d62'); R = {}
forms = '''
from django import forms
from django.core.exceptions import ValidationError
LOG = []
def log(s): LOG.append(s)
class TracedInt(forms.IntegerField):
    def to_python(self, v): log(f'  {self.label}.to_python({v!r})'); return super().to_python(v)
    def validate(self, v): log(f'  {self.label}.validate({v!r})'); return super().validate(v)
    def run_validators(self, v): log(f'  {self.label}.run_validators({v!r})'); return super().run_validators(v)
class F(forms.Form):
    a = TracedInt(label='a', min_value=1)
    b = TracedInt(label='b', min_value=1)
    def clean_a(self): log('  clean_a()'); return self.cleaned_data['a']
    def clean_b(self): log('  clean_b()'); return self.cleaned_data['b']
    def clean(self):
        log('  clean()(表单级,cleaned_data 里现有的键:%s)' % sorted(self.cleaned_data)); c = super().clean()
        if c.get('a') and c.get('b') and c['a'] > c['b']: raise ValidationError('a 不能大于 b', code='order')
        return c
    def _post_clean(self): log('  _post_clean()'); super()._post_clean()
'''
d = proj('d62', files={'proj/forms.py': forms}, apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom proj.forms import F, LOG\n" + code); return out.rstrip()
print('== 一:一次 is_valid() 里各方法的调用顺序')
o = run("""
f = F({'a': '3', 'b': '5'}); print('构造之后 LOG:', LOG); print('f.is_bound =', f.is_bound, ' hasattr(f, "cleaned_data") =', hasattr(f, 'cleaned_data'))
print('调用 f.errors 之前:', 'errors 是否已计算 =', f._errors is not None)
ok = f.is_valid(); print('is_valid() =', ok, ' 之后 LOG:'); [print(l) for l in LOG]
print('cleaned_data =', f.cleaned_data)
""")
print(o); R['order'] = o
print()
print('== 二:一个字段失败时:它的 clean_<field> 被跳过,表单级 clean() 拿不到它')
o = run("""
LOG.clear(); f = F({'a': '0', 'b': '5'}); ok = f.is_valid(); print('is_valid() =', ok)
[print(l) for l in LOG]; print('errors:', f.errors.as_data()['a'][0].code, '/', dict(f.errors)); print('cleaned_data =', f.cleaned_data)
""")
print(o); R['fail'] = o
print()
print('== 三:表单级错误(NON_FIELD_ERRORS);add_error;两个字段都失败时错误的顺序')
o = run("""
LOG.clear(); f = F({'a': '9', 'b': '5'}); f.is_valid(); print('a > b 时 non_field_errors:', list(f.non_field_errors()), ' code =', f.non_field_errors().as_data()[0].code)
LOG.clear(); f = F({'a': 'x', 'b': ''}); f.is_valid(); print('a="x", b="" :', {k: [e.code for e in v.as_data()] for k, v in f.errors.items()}, ' 顺序 =', list(f.errors))
print('错误对象:', f.errors.as_json()[:120])
""")
print(o); R['nonfield'] = o
print()
print('== 四:未绑定表单、has_changed、disabled 字段、extra 字段')
o = run("""
from django import forms
f = F(); print('未绑定表单 is_valid() =', f.is_valid(), ' errors =', dict(f.errors))
f = F({'a': '3', 'b': '5', 'zzz': 'ignored'}); f.is_valid(); print('多余字段 zzz 进入 cleaned_data 吗:', 'zzz' in f.cleaned_data)
class D(forms.Form):
    x = forms.IntegerField(disabled=True, initial=1)
f = D({'x': '99'}); f.is_valid(); print('disabled 字段:提交 99,cleaned_data =', f.cleaned_data, '(用 initial,忽略提交的值)')
f = F({'a': '3', 'b': '5'}, initial={'a': 3, 'b': 5}); f.is_valid(); print('has_changed() =', f.has_changed(), ' changed_data =', f.changed_data)
""")
print(o); R['misc'] = o
save('d62', R)
