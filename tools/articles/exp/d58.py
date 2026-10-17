import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d58'); R = {}
def model(fields): return "from django.db import models\nclass P(models.Model):\n" + ''.join(f"    {f}\n" for f in fields)
d = proj('d58', files={'lab/models.py': model(["name = models.CharField(max_length=20)"])}, apps=['django.contrib.contenttypes', 'lab'])
steps = [["name = models.CharField(max_length=20)"], ["name = models.CharField(max_length=20)", "a = models.IntegerField(default=0)"], ["name = models.CharField(max_length=20)", "a = models.IntegerField(default=0)", "b = models.IntegerField(default=0)"], ["name = models.CharField(max_length=40)", "a = models.IntegerField(default=0)", "b = models.IntegerField(default=0)"], ["name = models.CharField(max_length=40)", "a = models.IntegerField(default=0)", "b = models.IntegerField(default=0)", "c = models.IntegerField(default=0)"]]
for i, f in enumerate(steps):
    (d / 'lab' / 'models.py').write_text(model(f)); manage(d, 'makemigrations', 'lab', '--noinput')
names = sorted(x.stem for x in (d / 'lab' / 'migrations').glob('0*.py'))
def ops_of(stem): 
    t = (d / 'lab' / 'migrations' / f'{stem}.py').read_text(); return re.findall(r'migrations\.(\w+)\(', t)
print('== 一:五个迁移,每个的操作:', names)
for n in names: print(f'  {n}: {ops_of(n)}')
R['names'] = names; R['ops_before'] = {n: ops_of(n) for n in names}
print()
print('== 二:squashmigrations lab 0001 0005')
rc, out = manage(d, 'squashmigrations', 'lab', '0001', '0005', '--noinput'); print('  ' + out.strip().replace('\n', '\n  ')); R['squash_out'] = out.strip()
sq = [x for x in (d / 'lab' / 'migrations').glob('*squashed*.py')][0]; body = sq.read_text()
print('  合并后的文件:', sq.name, ' 操作:', re.findall(r'migrations\.(\w+)\(', body), ' replaces:', re.search(r'replaces = (\[.*?\])', body, re.S).group(1).replace('\n', '').replace(' ', '')[:150]); R['sq_name'] = sq.name; R['sq_ops'] = re.findall(r'migrations\.(\w+)\(', body)
print()
print('== 三:三种数据库状态下,新旧迁移文件同时存在时 migrate 用哪一套')
def plan(): rc, out = manage(d, 'migrate', '--plan'); return [l.strip() for l in out.strip().splitlines() if re.match(r'\s*lab\.', l)]
print('  全新数据库:', plan()); R['fresh'] = plan()
manage(d, 'migrate', 'lab', '0003_p_b') if False else None
# 用旧迁移迁到 0003
subprocess_out = manage(d, 'migrate', 'lab', '0003_p_b')
rc, o = pyscript(d, "from django.db import connection\nc = connection.cursor(); c.execute(\"select name from django_migrations where app='lab' order by id\"); print([r[0] for r in c.fetchall()])")
print('  已经应用到 0003 之后 django_migrations:', o.strip()); R['partial'] = o.strip()
print('  这时 migrate --plan:', plan()); R['partial_plan'] = plan()
manage(d, 'migrate'); rc, o = pyscript(d, "from django.db import connection\nc = connection.cursor(); c.execute(\"select name from django_migrations where app='lab' order by id\"); print([r[0] for r in c.fetchall()])")
print('  全部 migrate 之后 django_migrations:', o.strip()); R['done'] = o.strip()
print('  再 migrate --plan:', plan() or '(无事可做)')
print()
print('== 四:全新库上 migrate 用的是合并后的迁移(操作更少,SQL 更少)')
rc, out = manage(d, 'sqlmigrate', 'lab', sq.stem); n_sq = len([l for l in out.splitlines() if l.strip() and not l.startswith('--') and l.strip() not in ('BEGIN;', 'COMMIT;')])
tot = 0
for n in names:
    rc, o = manage(d, 'sqlmigrate', 'lab', n); tot += len([l for l in o.splitlines() if l.strip() and not l.startswith('--') and l.strip() not in ('BEGIN;', 'COMMIT;')])
print(f'  SQL 语句数:五个旧迁移合计 {tot} 条;合并后的 {sq.stem} {n_sq} 条'); R['sql'] = dict(old=tot, squashed=n_sq)
save('d58', R)
