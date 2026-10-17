import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d60'); R = {}
pg = PG(9435).start()
m = "from django.db import models\nclass Big(models.Model):\n    name = models.CharField(max_length=20)\n"
d = proj('d60', files={'lab/models.py': m}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pg.psql("insert into lab_big (name) select 'row' || g from generate_series(1, 2000000) g"); pg.psql('analyze lab_big')
cnt = [1]
def add(field_src, label, extra_import='', name=None):
    n = len(list((d / 'lab' / 'migrations').glob('0*.py'))); prev = sorted(p.stem for p in (d / 'lab' / 'migrations').glob('0*.py'))[-1]; nm = f'{n+1:04d}_{name}'
    (d / 'lab' / 'migrations' / f'{nm}.py').write_text(f"import uuid\nfrom django.db import migrations, models\n{extra_import}\nclass Migration(migrations.Migration):\n    dependencies = [('lab', '{prev}')]\n    operations = [migrations.AddField('big', '{name}', {field_src})]\n")
    t0 = time.perf_counter(); rc, out = manage(d, 'migrate'); dt = time.perf_counter() - t0
    rc2, sqlout = manage(d, 'sqlmigrate', 'lab', nm); sqls = [' '.join(l.split()) for l in sqlout.splitlines() if l.strip() and not l.startswith('--') and l.strip() not in ('BEGIN;', 'COMMIT;')]
    err = [l.strip() for l in out.splitlines() if 'Error' in l]
    print(f'  {label:<50} {dt:6.2f} s {"  错误:" + err[-1][:70] if err else ""}'); [print('      SQL:', s[:150]) for s in sqls]
    R.setdefault('ops', []).append(dict(label=label, secs=dt, sql=sqls, err=err[-1][:80] if err else None)); return nm
print('== 200 万行的表上给 AddField 用不同的默认值:每个操作的耗时和 Django 发出的 SQL')
add("models.IntegerField(default=0)", "AddField(default=0)  常量默认值", name='c_const')
add("models.IntegerField(null=True)", "AddField(null=True)  没有默认值", name='c_null')
add("models.UUIDField(default=uuid.uuid4, null=True)", "AddField(UUID, default=uuid.uuid4 可调用)", name='c_uuid')
print('   → 可调用默认值只算一次:', pg.psql('select count(distinct c_uuid) from lab_big'), '个不同的 uuid(共 200 万行)'); R['uuid_distinct'] = pg.psql('select count(distinct c_uuid) from lab_big')
add("models.IntegerField(db_default=5)", "AddField(db_default=5)  数据库层面的默认值", name='c_dbdef')
print('   → 之后表上该列的默认值:', pg.psql("select column_default from information_schema.columns where table_name='lab_big' and column_name='c_dbdef'")); R['dbdef_kept'] = pg.psql("select column_default from information_schema.columns where table_name='lab_big' and column_name='c_dbdef'")
add("models.FloatField(db_default=models.functions.Random())", "AddField(db_default=Random())  volatile 函数默认值", extra_import='import django.db.models.functions', name='c_random')
print('   → 各行的值是否不同:', pg.psql('select count(distinct c_random) > 1000000 from lab_big')); R['random_distinct'] = pg.psql('select count(distinct c_random) from lab_big')
print()
print('== 分三步的安全做法:①AddField(null=True) ②分批回填 ③AlterField 改成 NOT NULL')
add("models.IntegerField(null=True)", "步骤一:AddField(null=True)", name='s_null')
t0 = time.perf_counter(); tot = 0
import psycopg
c = psycopg.connect(host='127.0.0.1', port=pg.port, user='lab', dbname='lab', autocommit=True)
for lo in range(1, 2000001, 100000): c.execute('update lab_big set s_null = 1 where id >= %s and id < %s', (lo, lo + 100000))
print(f'  步骤二:分 20 批(每批 10 万行,每批自己提交)回填:{time.perf_counter() - t0:.2f} s'); R['backfill'] = time.perf_counter() - t0
n = len(list((d / 'lab' / 'migrations').glob('0*.py'))); prev = sorted(p.stem for p in (d / 'lab' / 'migrations').glob('0*.py'))[-1]
(d / 'lab' / 'migrations' / f'{n+1:04d}_s_notnull.py').write_text(f"from django.db import migrations, models\nclass Migration(migrations.Migration):\n    dependencies = [('lab', '{prev}')]\n    operations = [migrations.AlterField('big', 's_null', models.IntegerField(default=1))]\n")
t0 = time.perf_counter(); rc, out = manage(d, 'migrate'); print(f'  步骤三:AlterField → NOT NULL:{time.perf_counter() - t0:.2f} s'); R['notnull'] = time.perf_counter() - t0
pg.stop(); save('d60', R)
