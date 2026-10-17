import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d125'); R = {}
models = "from django.db import models\nclass Person(models.Model):\n    name = models.CharField(max_length=30)\n    secret = models.CharField(max_length=30)\n"
d = proj('d125', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'], middleware=[])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom lab.models import Person\nfrom django.core.exceptions import FieldError\nPerson.objects.all().delete(); Person.objects.bulk_create([Person(name='alice', secret='s-3'), Person(name='bob', secret='s-1'), Person(name='carol', secret='s-2')])\nEVT = []\ndef w(execute, sql, params, many, ctx): EVT.append((sql, params)); return execute(sql, params, many, ctx)\nP = \"x' OR '1'='1\"\n" + code); return out.rstrip()
print("== 一:ORM 过滤:用户输入 P = \"x' OR '1'='1\" 被当作参数传给数据库,不是拼进 SQL")
o = run("""
with connection.execute_wrapper(w): rows = list(Person.objects.filter(name=P))
sql, params = EVT[-1]; print('  发给数据库的 SQL :', sql[sql.index('WHERE'):]); print('  参数(单独传递):', params); print('  返回行数:', len(rows), '(没有叫这个名字的人)')
""")
print(o); R['orm'] = o
print()
print('== 二:raw():f-string 拼接 vs 参数化(同一个输入 P)')
o = run("""
bad = list(Person.objects.raw(f"SELECT * FROM lab_person WHERE name = '{P}'"))
print('  f-string 拼接  → 返回', len(bad), '行(全部):', [p.name for p in bad])
good = list(Person.objects.raw('SELECT * FROM lab_person WHERE name = %s', [P]))
print('  参数化 %s      → 返回', len(good), '行')
""")
print(o); R['raw'] = o
print()
print('== 三:cursor.execute() 同理;以及用户输入作为表名 / 列名时不能靠参数化')
o = run("""
with connection.cursor() as c:
    c.execute(f"SELECT name FROM lab_person WHERE name = '{P}'"); print('  cursor f-string  →', len(c.fetchall()), '行')
    c.execute('SELECT name FROM lab_person WHERE name = %s', [P]); print('  cursor 参数化    →', len(c.fetchall()), '行')
    c.execute('SELECT name FROM lab_person ORDER BY name DESC'); print('  ORDER BY name DESC(列名写在 SQL 里)       →', [r[0] for r in c.fetchall()])
    c.execute('SELECT name FROM lab_person ORDER BY %s DESC', ['name']); print("  ORDER BY %s DESC,参数 'name'(当作字符串) →", [r[0] for r in c.fetchall()], '← 与插入顺序相同,没有按 name 排序:参数是值,不是列名')
""")
print(o); R['cursor'] = o
print()
print('== 四:order_by(用户输入):不是注入,但可以按「任意字段」排序——会泄漏你不想暴露的字段信息')
o = run("""
for val in ('name', '-name', 'secret', 'name; DROP TABLE lab_person', 'nope'):
    try: print(f'  order_by({val!r:<32}) →', [p.name for p in Person.objects.order_by(val)])
    except Exception as e: print(f'  order_by({val!r:<32}) → {type(e).__name__}: {str(e)[:70]}')
ALLOWED = {'name', '-name'}
def safe_order(v): return v if v in ALLOWED else 'name'
print('  白名单之后 safe_order("secret") =', safe_order('secret'))
""")
print(o); R['order'] = o
print()
print('== 五:extra() / RawSQL 里拼接用户输入(同样的 P),与参数化写法')
o = run("""
from django.db.models.expressions import RawSQL
bad = Person.objects.extra(where=[f"name = '{P}'"]); print('  extra(where=[f-string])  →', bad.count(), '行')
good = Person.objects.extra(where=['name = %s'], params=[P]); print('  extra(where, params)     →', good.count(), '行')
""")
print(o); R['extra'] = o
save('d125', R)
