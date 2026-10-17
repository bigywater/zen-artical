import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d55'); R = {}
pg = PG(9431).start()
m = "from django.db import models\nclass P(models.Model):\n    name = models.CharField(max_length=20)\n"
d = proj('d55', files={'lab/models.py': m}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def q(sql): return pg.psql(sql)
def err(out):
    L = [l.strip() for l in out.strip().splitlines() if 'Error' in l]; return (L[-1] if L else out.strip().splitlines()[-1])[:140]
def mig(name, ops, atomic=None):
    at = '' if atomic is None else f'    atomic = {atomic}\n'
    (d / 'lab' / 'migrations' / f'{name}.py').write_text(f"from django.db import migrations, models\nclass Migration(migrations.Migration):\n{at}    dependencies = [('lab', '0001_initial')]\n    operations = [{ops}]\n")
ops = "migrations.RunSQL('ALTER TABLE lab_p ADD COLUMN c1 integer', 'ALTER TABLE lab_p DROP COLUMN c1'), migrations.RunSQL('THIS IS NOT SQL')"
def state():
    return dict(c1_exists=q("select count(*) from information_schema.columns where table_name='lab_p' and column_name='c1'"), recorded=q("select count(*) from django_migrations where name='0002_fail'"))
print('== 一:默认(atomic = True):第二条操作失败 → 整个迁移回滚,库里没有残留,也没有记录')
mig('0002_fail', ops); rc, out = manage(d, 'migrate'); print('  migrate 结果最后一行:', err(out)); s = state(); print('  c1 列存在:', s['c1_exists'], ' django_migrations 有记录:', s['recorded']); R['atomic'] = dict(last=err(out), **s)
print()
print('== 二:atomic = False:第一条操作已经执行并留下,第二条失败,迁移没有被记录')
mig('0002_fail', ops, atomic=False); rc, out = manage(d, 'migrate'); print('  migrate 结果最后一行:', err(out)); s = state(); print('  c1 列存在:', s['c1_exists'], ' django_migrations 有记录:', s['recorded'], ' ← 库处于「半应用」状态'); R['nonatomic'] = dict(last=err(out), **s)
print('  再跑一次 migrate(第一条操作重复执行):'); rc, out = manage(d, 'migrate'); print('  ', err(out)); R['rerun'] = err(out)
print()
print('== 三:恢复办法:手工把库修到「第二条之前」的状态或「全部完成」的状态,再 migrate 或 --fake')
q('ALTER TABLE lab_p DROP COLUMN c1'); print('  手工撤销第一条(DROP COLUMN c1)后 c1 存在:', state()['c1_exists'])
mig('0002_fail', "migrations.RunSQL('ALTER TABLE lab_p ADD COLUMN c1 integer', 'ALTER TABLE lab_p DROP COLUMN c1')", atomic=False)
rc, out = manage(d, 'migrate'); print('  修好迁移文件之后 migrate:', [l.strip() for l in out.strip().splitlines() if 'Applying' in l or 'OK' in l][:2], ' 记录:', state()['recorded']); R['fixed'] = state()
print()
print('== 四:另一种恢复:数据库里已经有了结果,只需要让 Django 记一笔 → migrate --fake(第 56 篇)')
rc, out = manage(d, 'migrate', 'lab', '0001', '--fake'); print('  migrate lab 0001 --fake:', [l.strip() for l in out.strip().splitlines() if 'Unapplying' in l or 'FAKED' in l][:2], ' c1 列仍存在:', state()['c1_exists'], ' 记录:', state()['recorded']); R['fake'] = state()
pg.stop(); save('d55', R)
