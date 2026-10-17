import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f97'); R = {}
import sqlite3, re, glob
MODEL = '''
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
db = SQLAlchemy(); migrate = Migrate(render_as_batch=True)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), server_default='none')
    __VARIANT__
def create_app():
    app = Flask(__name__); app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
    db.init_app(app); migrate.init_app(app, db); return app
app = create_app()
'''
class P:
    """一个独立的迁移项目:先用基线模型 init / migrate / upgrade,再改模型。"""
    n = 0
    def __init__(self):
        P.n += 1; self.d = mkapp(f'f97_{P.n}', {'models.py': MODEL.replace('__VARIANT__', 'pass')})
        self.fl('db', 'init'); self.fl('db', 'migrate', '-m', 'create user table', '--rev-id', 'r001'); self.fl('db', 'upgrade')
    def fl(self, *args):
        r = subprocess.run([str(BIN / 'flask'), '--app', 'models', *args], cwd=self.d, env=env(self.d), capture_output=True, text=True); return r.returncode, tidy(r.stdout + r.stderr)
    def model(self, text): (self.d / 'models.py').write_text(text)
    def newest(self): return sorted(glob.glob(str(self.d / 'migrations' / 'versions' / '*.py')), key=os.path.getmtime)[-1]
    def db(self): return sqlite3.connect(self.d / 'instance' / 'app.db')
    def ops(self, fn='upgrade'):
        t = open(self.newest()).read(); body = t.split(f'def {fn}()')[1].split('\ndef ')[0]; return [l.strip() for l in body.splitlines() if 'op.' in l or 'batch_op.' in l or l.strip().startswith(('\'', 'existing_', 'type_', 'nullable', 'server_default'))]
def case(label, variant=None, text=None):
    p = P(); base = (p.d / 'models.py').read_text()
    p.model(text if text else base.replace('    pass', '    ' + variant if variant else '    pass'))
    rc, o = p.fl('db', 'migrate', '-m', 'x'); det = [l.split('compare.')[-1] for l in o.splitlines() if 'Detected' in l]; return p, det, p.ops(), o
print('== 一:migrate 生成的文件长什么样')
p = P(); f = sorted(glob.glob(str(p.d / 'migrations' / 'versions' / '*.py')))[0]; txt = open(f).read()
print('  文件名:', os.path.basename(f), '(-m "create user table" 变成文件名里的小写下划线;--rev-id r001 指定了 revision id)'); R['fname'] = os.path.basename(f)
head = txt.split('def upgrade')[0]; print('  文件头部:'); print('\n'.join('    ' + l for l in head.strip().splitlines())); R['head'] = head.strip()
print('  文件里的函数:', re.findall(r'^def (\w+)\(', txt, re.M)); R['funcs'] = re.findall(r'^def (\w+)\(', txt, re.M)
print()
print('== 二:自动生成能检测到什么、检测不到什么(每种改动都从同一个基线项目出发,只改一处)')
R['cases'] = {}
tests = [
    ('加一列 age', "age = db.Column(db.Integer)", None),
    ('改列长度 name 50→80', None, 'name = db.Column(db.String(50), nullable=False)->name = db.Column(db.String(80), nullable=False)'),
    ('改 nullable(email 不可空)', None, "email = db.Column(db.String(100), server_default='none')->email = db.Column(db.String(100), server_default='none', nullable=False)"),
    ('改 server_default 的值', None, "server_default='none')->server_default='other')"),
    ('给 email 加索引', None, "email = db.Column(db.String(100), server_default='none')->email = db.Column(db.String(100), server_default='none', index=True)"),
    ('给 email 加 unique=True', None, "email = db.Column(db.String(100), server_default='none')->email = db.Column(db.String(100), server_default='none', unique=True)"),
    ('把 email 改名为 mail', None, "email = db.Column(db.String(100), server_default='none')->mail = db.Column(db.String(100), server_default='none')"),
    ('删掉 email 列', None, "email = db.Column(db.String(100), server_default='none')->"),
]
for label, variant, repl in tests:
    p = P(); base = (p.d / 'models.py').read_text()
    if repl: a, b = repl.split('->'); new = base.replace(a, b)
    else: new = base.replace('    pass', '    ' + variant)
    p.model(new); rc, o = p.fl('db', 'migrate', '-m', 'x'); det = [l.split('compare.')[-1] for l in o.splitlines() if 'Detected' in l]; u = p.ops() if det else []
    print(f'  [{label}] ' + ('检测到: ' + '; '.join(d_[d_.index(']') + 2:] for d_ in det) if det else '没有检测到任何变化(没有生成迁移)' if 'No changes' in o or not det else ''))
    R['cases'][label] = det
print()
print('== 三:一个检测到、但在 SQLite 上执行失败的例子:给列加没有名字的唯一约束')
p = P(); base = (p.d / 'models.py').read_text(); p.model(base.replace("server_default='none')", "server_default='none', unique=True)")); rc, o = p.fl('db', 'migrate', '-m', 'uq'); print('  生成的迁移里的操作:', [x[:100] for x in p.ops() if 'unique' in x.lower() or 'create' in x.lower()]); R['uq_ops'] = [x[:100] for x in p.ops() if 'unique' in x.lower() or 'create' in x.lower()]
rc, o = p.fl('db', 'upgrade'); print('  upgrade →', '成功' if rc == 0 else '失败:' + [l for l in o.splitlines() if 'rror' in l][-1][:150]); R['uq_up'] = [rc, ([l for l in o.splitlines() if 'rror' in l][-1][:150] if rc else '')]
print()
print('== 四:flask db revision 生成空脚本,自己写数据迁移(op.execute)')
p = P(); p.fl('db', 'revision', '-m', 'backfill emails', '--rev-id', 'r900'); f = p.newest(); t = open(f).read()
t = re.sub(r"def upgrade\(\):.*?\n\n\ndef downgrade\(\):.*$", 'def upgrade():\n    op.execute("update user set email = name || \'@example.com\' where email = \'none\'")\n\n\ndef downgrade():\n    op.execute("update user set email = \'none\' where email like \'%@example.com\'")\n', t, flags=re.S); open(f, 'w').write(t)
con = p.db(); con.execute("insert into user (name) values ('bob')"); con.commit(); con.close()
print('  空脚本里原来是 pass;手写的两个函数:'); print('\n'.join('    ' + l for l in ('def upgrade' + open(f).read().split('def upgrade')[1]).strip().splitlines() if l.strip()))
print('  执行前:', p.db().execute('select name, email from user').fetchall()); rc, o = p.fl('db', 'upgrade'); print('  upgrade 后:', p.db().execute('select name, email from user').fetchall(), '| 退出码', rc); R['backfill'] = p.db().execute('select name, email from user').fetchall()
rc, o = p.fl('db', 'downgrade'); print('  downgrade 后:', p.db().execute('select name, email from user').fetchall(), '| 退出码', rc); R['backfill_down'] = p.db().execute('select name, email from user').fetchall()
print()
print('== 五:flask db upgrade --sql:只生成 SQL,不碰数据库(离线模式)')
con = p.db(); before = con.execute('select * from alembic_version').fetchall(); con.close()
rc, o = p.fl('db', 'upgrade', 'r001:r900', '--sql'); lines = [l for l in o.splitlines() if l.strip() and not l.startswith('INFO')]
print('  upgrade r001:r900 --sql 的输出:'); [print('    ', l[:120]) for l in lines[:6]]; R['sql'] = lines[:6]
con = p.db(); after = con.execute('select * from alembic_version').fetchall(); con.close(); print('  数据库的版本号前后:', before, '→', after, '(没变)'); R['sql_unchanged'] = before == after
print()
print('== 六:flask db stamp:只改 alembic_version,不执行迁移')
p = P(); p.fl('db', 'revision', '-m', 'noop', '--rev-id', 'r777'); rc, o = p.fl('db', 'stamp', 'r777'); v = p.db().execute('select * from alembic_version').fetchall(); print('  stamp r777 之后 alembic_version =', v, '(没有执行 r777 的任何操作,只是记账)'); R['stamp'] = v
rc, o = p.fl('db', 'current'); print('  flask db current:', [l for l in o.splitlines() if 'r777' in l]); 
save('f97', R)
