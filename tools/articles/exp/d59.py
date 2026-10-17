import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d59'); R = {}
import psycopg
pg = PG(9434).start()
m = "from django.db import models\nclass Big(models.Model):\n    name = models.CharField(max_length=20)\n    n = models.IntegerField(default=0)\n    note = models.CharField(max_length=20, null=True)\n"
d = proj('d59', files={'lab/models.py': m}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab', 'django.contrib.postgres'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pg.psql("insert into lab_big (name, n, note) select 'row' || g, g, 'x' from generate_series(1, 2000000) g"); pg.psql('analyze lab_big')
print('== 表:lab_big,200 万行;一个后台线程每 5 ms 更新一行(模拟线上写入),记录每次更新的耗时;下面每种迁移操作期间看写入被阻塞多久')
def writer(stop, lat):
    c = psycopg.connect(host='127.0.0.1', port=pg.port, user='lab', dbname='lab', autocommit=True); i = 1
    while not stop.is_set():
        t0 = time.perf_counter(); c.execute('update lab_big set n = n + 1 where id = %s', (i % 1000 + 1,)); lat.append((time.time(), (time.perf_counter() - t0) * 1000)); i += 1; time.sleep(0.005)
    c.close()
def run_mig(label, ops, model_src=None, imports='', name=None):
    n = len(list((d / 'lab' / 'migrations').glob('0*.py'))) + 1; nm = f'{n:04d}_{name or label[:8]}'.replace(' ', '_')
    (d / 'lab' / 'migrations' / f'{nm}.py').write_text(f"from django.db import migrations, models\n{imports}\nclass Migration(migrations.Migration):\n    dependencies = [('lab', '{sorted(p.stem for p in (d / 'lab' / 'migrations').glob('0*.py'))[-1]}')]\n    atomic = {'False' if 'Concurrently' in ops else 'True'}\n    operations = [{ops}]\n")
    stop = threading.Event(); lat = []; th = threading.Thread(target=writer, args=(stop, lat)); th.start(); time.sleep(0.3)
    t0 = time.time(); tp = time.perf_counter(); rc, out = manage(d, 'migrate'); dt = time.perf_counter() - tp; t1 = time.time(); time.sleep(0.3); stop.set(); th.join()
    during = [l for t, l in lat if t0 <= t <= t1 + 0.3]; base = [l for t, l in lat if t < t0]
    mx = max(during) if during else 0
    err = [l for l in out.splitlines() if 'Error' in l]
    print(f'  {label:<46} 迁移总用时 {dt:6.2f} s   期间写入最长一次 {mx:8.0f} ms(平时中位 {sorted(base)[len(base)//2]:.1f} ms){"  错误:" + err[-1][:60] if err else ""}')
    R.setdefault('ops', []).append(dict(label=label, secs=dt, max_write_ms=mx, base_ms=sorted(base)[len(base)//2] if base else 0, err=err[-1][:80] if err else None)); return dt, mx
print(f'  {"操作":<46} 结果')
run_mig('AddField(int, default=0, NOT NULL)', "migrations.AddField('big', 'c1', models.IntegerField(default=0))", name='add_c1')
run_mig('AddField(int, null=True)', "migrations.AddField('big', 'c2', models.IntegerField(null=True))", name='add_c2')
run_mig('AlterField varchar(20) → varchar(60)', "migrations.AlterField('big', 'name', models.CharField(max_length=60))", name='alter_len')
run_mig('AlterField integer → bigint(重写整张表)', "migrations.AlterField('big', 'n', models.BigIntegerField(default=0))", name='alter_bigint')
run_mig('AlterField null → NOT NULL(扫全表)', "migrations.AlterField('big', 'note', models.CharField(max_length=20, default='x'))", name='not_null')
run_mig('AddIndex(普通 CREATE INDEX)', "migrations.AddIndex('big', models.Index(fields=['name'], name='big_name_idx'))", name='add_idx')
run_mig('AddIndexConcurrently(CREATE INDEX CONCURRENTLY)', "AddIndexConcurrently('big', models.Index(fields=['note'], name='big_note_idx'))", imports='from django.contrib.postgres.operations import AddIndexConcurrently', name='add_idx_conc')
pg.stop(); save('d59', R)
