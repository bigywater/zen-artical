import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d57'); R = {}
m = "from django.db import models\nclass P(models.Model):\n    name = models.CharField(max_length=20)\n"
d = proj('d57', files={'lab/models.py': m}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def mig(name, ops): (d / 'lab' / 'migrations' / f'{name}.py').write_text(f"from django.db import migrations, models\nclass Migration(migrations.Migration):\n    dependencies = [('lab', '0001_initial')]\n    operations = [{ops}]\n")
def last(out): return [l.strip() for l in out.strip().splitlines() if l.strip()][-1][:200]
print('== 一:两个分支各加一个迁移,都依赖 0001(两个叶子节点)')
mig('0002_add_a', "migrations.AddField('p', 'a', models.IntegerField(default=1))"); mig('0002_add_b', "migrations.AddField('p', 'b', models.IntegerField(default=2))")
rc, out = manage(d, 'migrate'); print('  migrate →', last(out)); R['migrate'] = last(out)
rc, out = manage(d, 'makemigrations', '--dry-run'); print('  makemigrations →', last(out)); R['make'] = last(out)
rc, out = manage(d, 'showmigrations', 'lab'); print('  showmigrations lab:'); [print('   ', l) for l in out.strip().splitlines()]; R['show'] = out.strip()
print()
print('== 二:makemigrations --merge 生成合并迁移')
rc, out = manage(d, 'makemigrations', '--merge', '--noinput'); print('  ' + out.strip().replace('\n', '\n  ')); R['merge_out'] = out.strip()
mf = sorted((d / 'lab' / 'migrations').glob('0003_merge*.py'))[0]; print('  ' + mf.name + ' 的内容:'); body = mf.read_text(); print('    ' + '\n    '.join(l for l in body.splitlines() if l.strip())); R['merge_file'] = body
rc, out = manage(d, 'migrate'); print('  migrate →', [l.strip() for l in out.strip().splitlines() if 'Applying' in l]); R['applied'] = [l.strip() for l in out.strip().splitlines() if 'Applying' in l]
print()
print('== 三:合并只是让图变成一条线——两个分支的操作是否兼容它不管:两边给同一个字段 x 加不同类型(一个 IntegerField,一个 TextField)')
pg = PG(9433).start()
R['clash'] = {}
for label, dbs in (('SQLite', None), ('PostgreSQL', pg.databases())):
    d2 = proj('d57b', files={'lab/models.py': m}, apps=['django.contrib.contenttypes', 'lab'], databases=dbs); manage(d2, 'makemigrations', 'lab'); manage(d2, 'migrate')
    (d2 / 'lab' / 'migrations' / '0002_x_int.py').write_text("from django.db import migrations, models\nclass Migration(migrations.Migration):\n    dependencies = [('lab', '0001_initial')]\n    operations = [migrations.AddField('p', 'x', models.IntegerField(default=1))]\n")
    (d2 / 'lab' / 'migrations' / '0002_x_text.py').write_text("from django.db import migrations, models\nclass Migration(migrations.Migration):\n    dependencies = [('lab', '0001_initial')]\n    operations = [migrations.AddField('p', 'x', models.TextField(default='t'))]\n")
    rc, out = manage(d2, 'makemigrations', '--merge', '--noinput'); rc, out = manage(d2, 'migrate')
    errs = [l.strip() for l in out.strip().splitlines() if 'Error' in l]; applied = [l.strip() for l in out.strip().splitlines() if 'Applying' in l]
    if label == 'SQLite': rc, o = pyscript(d2, "from django.db import connection\nc = connection.cursor(); c.execute('pragma table_info(lab_p)'); print([(r[1], r[2]) for r in c.fetchall()])"); coltype = o.strip()
    else: coltype = pg.psql("select column_name || ':' || data_type from information_schema.columns where table_name='lab_p' order by ordinal_position").replace('\n', ', ')
    print(f'  [{label}] 合并后 migrate:', '报错:' + errs[-1][:110] if errs else '没有报错;执行了 ' + str(len(applied)) + ' 个迁移', '| lab_p 的列:', coltype); R['clash'][label] = dict(error=errs[-1][:110] if errs else None, applied=len(applied), cols=coltype)
pg.stop()
save('d57', R)
