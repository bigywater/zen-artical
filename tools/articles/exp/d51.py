import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d51'); R = {}
BASE = "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=20)\n    price = models.IntegerField(default=0)\n    note = models.TextField(blank=True)\n"
def setup():
    d = proj('d51', files={'lab/models.py': BASE}, apps=['django.contrib.contenttypes', 'lab'])
    manage(d, 'makemigrations', 'lab'); manage(d, 'migrate'); return d
muts = [
    ('新增字段(有 default)', BASE + "    stock = models.IntegerField(default=0)\n"),
    ('新增字段(null=True)', BASE + "    stock = models.IntegerField(null=True)\n"),
    ('新增字段(没有 default 也不许 NULL)', BASE + "    stock = models.IntegerField()\n"),
    ('max_length 20 → 50', BASE.replace('max_length=20', 'max_length=50')),
    ('字段类型 IntegerField → BigIntegerField', BASE.replace('price = models.IntegerField', 'price = models.BigIntegerField')),
    ('只改 help_text(不影响数据库)', BASE.replace("price = models.IntegerField(default=0)", "price = models.IntegerField(default=0, help_text='单位:分')")),
    ('只改 choices(不影响数据库)', BASE.replace("name = models.CharField(max_length=20)", "name = models.CharField(max_length=20, choices=[('a', 'A')])")),
    ('删除字段', BASE.replace("    note = models.TextField(blank=True)\n", "")),
    ('字段改名 price → cost', BASE.replace('price =', 'cost =')),
    ('模型类改名 Item → Product', BASE.replace('class Item', 'class Product')),
    ('新增 Meta.indexes', BASE + "    class Meta:\n        indexes = [models.Index(fields=['name'])]\n"),
    ('新增 unique_together', BASE + "    class Meta:\n        unique_together = [('name', 'price')]\n"),
    ('新增方法 / @property(纯 Python)', BASE + "    def label(self): return self.name\n    @property\n    def p2(self): return self.price * 2\n"),
    ('改 Meta.ordering', BASE + "    class Meta:\n        ordering = ['name']\n"),
]
print('== 一:一次只改一处模型,看 makemigrations --dry-run 检测到什么,以及 sqlmigrate 会执行多少条 SQL(SQLite)')
print(f'  {"改动":<38} {"检测到的操作":<52} SQL 条数')
R['muts'] = []
for label, src in muts:
    d = setup(); (d / 'lab' / 'models.py').write_text(src)
    rc, out = manage(d, 'makemigrations', 'lab', '--dry-run', '--noinput', stdin=None) if False else manage(d, 'makemigrations', 'lab', '--dry-run', '--noinput')
    ops = [l.strip().lstrip('+-~ ').strip() for l in out.splitlines() if re.match(r'\s+[+\-~] ', l)]
    if not ops: ops = ['(没有检测到变化)' if 'No changes' in out else out.strip().splitlines()[-1][:60]]
    nsql = '-'
    if any('No changes' in out for _ in [0]) is False:
        manage(d, 'makemigrations', 'lab', '--noinput'); mig = sorted((d / 'lab' / 'migrations').glob('0002*.py'))
        if mig:
            rc2, o2 = manage(d, 'sqlmigrate', 'lab', mig[0].stem); nsql = str(len([l for l in o2.splitlines() if l.strip() and not l.startswith('--') and l.strip() not in ('BEGIN;', 'COMMIT;')]))
    R['muts'].append((label, ops, nsql)); print(f'  {label:<38} {"; ".join(ops)[:52]:<52} {nsql}')
print()
print('== 二:重命名的歧义:交互模式会问「是不是改名」,--noinput 时按「删除再新增」处理')
d = setup(); (d / 'lab' / 'models.py').write_text(BASE.replace('price =', 'cost ='))
rc, out = manage(d, 'makemigrations', 'lab', '--dry-run', '--noinput'); print('  --noinput:', [l.strip() for l in out.splitlines() if re.match(r'\s+[+\-~] ', l)]); R['noinput'] = [l.strip() for l in out.splitlines() if re.match(r'\s+[+\-~] ', l)]
import subprocess as sp
r = sp.run([PY, 'manage.py', 'makemigrations', 'lab', '--dry-run'], cwd=d, env=env(d), input='y\n', capture_output=True, text=True, timeout=60)
print('  交互回答 y:', [l.strip() for l in (r.stdout).splitlines() if re.match(r'\s+[+\-~] ', l)], '| 提问原文:', [l for l in r.stdout.splitlines() if 'rename' in l.lower()][:1]); R['answer_y'] = [l.strip() for l in r.stdout.splitlines() if re.match(r'\s+[+\-~] ', l)]; R['question'] = [l for l in r.stdout.splitlines() if 'rename' in l.lower()][:1]
print()
print('== 三:同时改名和改类型时不再被识别为改名')
(d / 'lab' / 'models.py').write_text(BASE.replace('price = models.IntegerField(default=0)', 'cost = models.BigIntegerField(default=0)'))
r = sp.run([PY, 'manage.py', 'makemigrations', 'lab', '--dry-run'], cwd=d, env=env(d), input='y\n', capture_output=True, text=True, timeout=60)
print('  ', [l.strip() for l in r.stdout.splitlines() if re.match(r'\s+[+\-~] ', l)] or r.stdout.strip()[-200:]); R['rename_and_type'] = [l.strip() for l in r.stdout.splitlines() if re.match(r'\s+[+\-~] ', l)]
save('d51', R)
