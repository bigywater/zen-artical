import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d38'); R = {}
fields = '''
import os
from django import forms
from django.db import models
def log(s):
    with open(os.environ.get('FLD_LOG', os.devnull), 'a') as f: f.write(s + '\\n')
class CSVField(models.TextField):
    """把 list[str] 存成 'a,b,c' 文本的字段"""
    def __init__(self, *args, separator=',', **kwargs):
        self.separator = separator; super().__init__(*args, **kwargs)
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.separator != ',': kwargs['separator'] = self.separator
        return name, path, args, kwargs
    def from_db_value(self, value, expression, connection):
        log('from_db_value(%r)' % (value,)); return None if value is None else (value.split(self.separator) if value else [])
    def to_python(self, value):
        log('to_python(%r)' % (value,))
        if isinstance(value, list) or value is None: return value
        return value.split(self.separator) if value else []
    def get_prep_value(self, value):
        log('get_prep_value(%r)' % (value,))
        if value is None: return None
        return value if isinstance(value, str) else self.separator.join(value)
    def value_to_string(self, obj): log('value_to_string'); return self.get_prep_value(self.value_from_object(obj))
    def formfield(self, **kwargs): return super().formfield(**{'form_class': forms.CharField, **kwargs})
'''
models = "from django.db import models\nfrom lab.fields import CSVField\nclass Post(models.Model):\n    title = models.CharField(max_length=20)\n    tags = CSVField(default=list)\n"
d = proj('d38', files={'lab/fields.py': fields, 'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
LG = str(DJ / 'd38' / 'fld.log')
def run(code, **kw): open(LG, 'w').close(); rc, out = pyscript(d, "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom lab.models import Post\ndef L():\n    x = open(__import__('os').environ['FLD_LOG']).read().splitlines(); open(__import__('os').environ['FLD_LOG'], 'w').close(); return x\n" + code, FLD_LOG=LG); return out.rstrip()
print('== 一:一个自定义字段各个方法被调用的时刻(每一步前清空日志)')
o = run("""
L()
p = Post(title='t', tags=['a', 'b']); print('构造 Post(tags=["a","b"])   →', L())
p.save(); print('save()                        →', L())
q = Post.objects.get(pk=p.pk); print('Post.objects.get(pk)          →', L(), ' tags =', q.tags)
print('Post.objects.filter(tags="a,b") →', end=' '); list(Post.objects.filter(tags='a,b')); print(L())
print('Post.objects.filter(tags=["a","b"]) →', end=' '); list(Post.objects.filter(tags=['a', 'b'])); print(L())
print('values_list("tags")           →', end=' '); r = list(Post.objects.values_list('tags', flat=True)); print(L(), r)
print('full_clean()                  →', end=' '); p.full_clean(); print(L())
from django.core import serializers
print('serializers.serialize("json") →', end=' '); s = serializers.serialize('json', [p]); print(L(), ' 输出:', s[:120])
""")
print(o); R['calls'] = o
print()
print('== 二:migration 里这个字段长什么样;deconstruct;数据库列类型')
rc, out = manage(d, 'sqlmigrate', 'lab', '0001'); print('  sqlmigrate:'); [print('   ', l) for l in out.strip().splitlines()]; R['sqlmigrate'] = out.strip()
mig = (d / 'lab' / 'migrations' / '0001_initial.py').read_text(); line = [l for l in mig.splitlines() if 'tags' in l][0].strip(); print('  迁移文件里:', line); R['mig_line'] = line
o = run("""
from lab.fields import CSVField
f = CSVField(separator=';'); print('deconstruct(separator=";") →', f.deconstruct()[1:]); print('deconstruct(默认)          →', CSVField().deconstruct()[1:])
""")
print(o); R['decon'] = o
print()
print('== 三:改了字段参数 → makemigrations 是否检测;忘了写 deconstruct 会怎样')
(d / 'lab' / 'models.py').write_text("from django.db import models\nfrom lab.fields import CSVField\nclass Post(models.Model):\n    title = models.CharField(max_length=20)\n    tags = CSVField(default=list, separator=';')\n")
rc, out = manage(d, 'makemigrations', 'lab', '--dry-run', '-v', '3'); ol = [l for l in out.splitlines() if 'tags' in l or 'AlterField' in l or 'Alter' in l]; print('  改 separator=";" 后 makemigrations:', ol[:3] or out.strip()[:100]); R['alter'] = ol[:3]
(d / 'lab' / 'fields.py').write_text(fields.replace("        if self.separator != ',': kwargs['separator'] = self.separator\n", ""))
rc, out = manage(d, 'makemigrations', 'lab', '--dry-run'); print('  同样的修改,但 deconstruct 里没有写 separator:', out.strip().splitlines()[-1] if out.strip() else '(无输出)'); R['nodecon'] = out.strip().splitlines()[-1] if out.strip() else ''
save('d38', R)
