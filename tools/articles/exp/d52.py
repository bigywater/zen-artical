import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d52'); R = {}
files = {
    'a/__init__.py': '', 'a/models.py': "from django.db import models\nclass A(models.Model):\n    x = models.IntegerField(default=0)\n",
    'b/__init__.py': '', 'b/models.py': "from django.db import models\nclass B(models.Model):\n    a = models.ForeignKey('a.A', on_delete=models.CASCADE)\n",
    'c/__init__.py': '', 'c/models.py': "from django.db import models\nclass C(models.Model):\n    y = models.IntegerField(default=0)\n",
}
d = proj('d52', files=files, apps=['django.contrib.contenttypes', 'a', 'b', 'c'], with_lab=False)
manage(d, 'makemigrations', 'a', 'b', 'c')
(d / 'a' / 'models.py').write_text("from django.db import models\nclass A(models.Model):\n    x = models.IntegerField(default=0)\n    z = models.IntegerField(default=0)\n"); manage(d, 'makemigrations', 'a')
(d / 'c' / 'models.py').write_text("from django.db import models\nclass C(models.Model):\n    y = models.IntegerField(default=0)\n    w = models.IntegerField(default=0)\n"); manage(d, 'makemigrations', 'c')
def plan(*a): rc, out = manage(d, *a); return [l.strip() for l in out.strip().splitlines() if l.strip()]
print('== 一:全新数据库 migrate --plan(a 有两个迁移,b 依赖 a.0001,c 有两个迁移)')
p = plan('migrate', '--plan'); [print('  ', l) for l in p]; R['plan_all'] = p
print()
print('== 二:migrate 只指定某个 app 时:先做它的依赖,不多做别的')
p = plan('migrate', 'b', '--plan'); print('  migrate b --plan:'); [print('   ', l) for l in p]; R['plan_b'] = p
p = plan('migrate', 'a', '0001', '--plan'); print('  migrate a 0001 --plan:'); [print('   ', l) for l in p]; R['plan_a1'] = p
print()
print('== 三:真的执行后,django_migrations 里 applied 的顺序与时间')
rc, out = manage(d, 'migrate'); rc, out = pyscript(d, "from django.db import connection\nc = connection.cursor(); c.execute('select app, name from django_migrations order by id'); [print(r) for r in c.fetchall()]")
print('  ' + out.strip().replace('\n', '\n  ')); R['applied'] = out.strip()
print()
print('== 四:回退:migrate a 0001 会先回退依赖它的 b(反向依赖),再回退 a.0002')
rc, out = manage(d, 'migrate', 'a', '0001', '--plan'); print('  migrate a 0001 --plan(现在库里全部已应用):'); [print('   ', l.strip()) for l in out.strip().splitlines() if l.strip()]; R['back'] = [l.strip() for l in out.strip().splitlines() if l.strip()]
rc, out = manage(d, 'migrate', 'a', 'zero', '--plan'); print('  migrate a zero --plan:'); [print('   ', l.strip()) for l in out.strip().splitlines() if l.strip()]; R['zero'] = [l.strip() for l in out.strip().splitlines() if l.strip()]
print()
print('== 五:run_before:让别的 app 的迁移排到自己的后面')
p = (d / 'c' / 'migrations' / '0001_initial.py'); t = p.read_text(); p.write_text(t.replace("dependencies = [\n    ]", "dependencies = [\n    ]\n    run_before = [('a', '0002_a_z')]") if 'dependencies = [\n    ]' in t else t)
rc, out = manage(d, 'showmigrations', '--plan'); [print('  ', l.strip()) for l in out.strip().splitlines() if l.strip()]; R['run_before'] = [l.strip() for l in out.strip().splitlines() if l.strip()]
R['mig_names'] = sorted(f.name for f in (d / 'a' / 'migrations').glob('0*.py'))
save('d52', R)
