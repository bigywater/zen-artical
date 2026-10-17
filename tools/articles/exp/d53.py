import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d53'); R = {}
pg = PG(9430).start()
m1 = "from django.db import models\nclass Person(models.Model):\n    first_name = models.CharField(max_length=20)\n    last_name = models.CharField(max_length=20)\n    display = models.CharField(max_length=50, blank=True)\n    def full_name(self): return f'{self.first_name} {self.last_name}'\n"
d = proj('d53', files={'lab/models.py': m1}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pg.psql("insert into lab_person (first_name, last_name, display) select 'f' || g, 'l' || g, '' from generate_series(1, 100000) g")
mig = '''
import time
from django.db import migrations
from django.db.models import F, Value
from django.db.models.functions import Concat
def via_python_loop(apps, schema_editor):
    Person = apps.get_model('lab', 'Person')
    has_method = hasattr(Person, 'full_name')
    print('  历史模型 Person 是否有自定义方法 full_name:', has_method, ' 类:', Person.__module__ + '.' + Person.__name__)
    t0 = time.perf_counter()
    rows = list(Person.objects.all()[:20000])
    for p in rows: p.display = p.first_name + ' ' + p.last_name
    Person.objects.bulk_update(rows, ['display'], batch_size=2000)
    print('  Python 循环 + bulk_update(20000 行): %.2f s' % (time.perf_counter() - t0))
def via_update(apps, schema_editor):
    Person = apps.get_model('lab', 'Person')
    t0 = time.perf_counter(); n = Person.objects.update(display=Concat(F('first_name'), Value(' '), F('last_name')))
    print('  一条 UPDATE … SET display = first_name || " " || last_name(%d 行): %.2f s' % (n, time.perf_counter() - t0))
def reverse(apps, schema_editor):
    apps.get_model('lab', 'Person').objects.update(display='')
class Migration(migrations.Migration):
    dependencies = [('lab', '0001_initial')]
    operations = [migrations.RunPython(via_python_loop, migrations.RunPython.noop), migrations.RunPython(via_update, reverse)]
'''
(d / 'lab' / 'migrations' / '0002_fill_full.py').write_text(mig)
print('== 一:RunPython 里拿到的是「历史模型」:没有你在 models.py 里定义的方法')
print('== 二:三种回填方式的耗时(10 万行,PostgreSQL)')
rc, out = manage(d, 'migrate'); print(out.strip()); R['run'] = out.strip()
print()
print('== 三:结果检查与回退')
print('  已填充的行数:', pg.psql("select count(*) from lab_person where display <> ''")); R['filled'] = pg.psql("select count(*) from lab_person where display <> ''")
rc, out = manage(d, 'migrate', 'lab', '0001'); print('  migrate lab 0001(回退)→', [l.strip() for l in out.strip().splitlines() if 'Unapplying' in l or 'OK' in l][:2], ' 回退后 display 非空的行数:', pg.psql("select count(*) from lab_person where display <> ''")); R['reversed'] = pg.psql("select count(*) from lab_person where display <> ''")
print()
print('== 四:迁移里 import 了真实模型会怎样:之后模型改了,旧迁移在全新库上跑不起来')
bad = '''
from django.db import migrations
def go(apps, schema_editor):
    from lab.models import Person
    list(Person.objects.all()[:1])
class Migration(migrations.Migration):
    dependencies = [('lab', '0001_initial')]
    operations = [migrations.RunPython(go, migrations.RunPython.noop)]
'''
(d / 'lab' / 'migrations' / '0002_fill_full.py').write_text(bad)
(d / 'lab' / 'models.py').write_text(m1.replace("    display = models.CharField(max_length=50, blank=True)\n", "    display = models.CharField(max_length=50, blank=True)\n    later = models.IntegerField(default=0)\n"))
manage(d, 'makemigrations', 'lab', '--noinput')
pg.psql('drop schema public cascade; create schema public')
rc, out = manage(d, 'migrate'); errs = [l.strip() for l in out.strip().splitlines() if 'Error' in l]; last = errs[-1] if errs else out.strip().splitlines()[-1]; print('  在全新库上从头 migrate(真实模型已多了 later 字段,但 0002 时这一列还不存在):'); print('   ', last[:160]); R['badreal'] = last[:160]
pg.stop(); save('d53', R)
