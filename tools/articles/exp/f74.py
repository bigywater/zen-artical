import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f74'); R = {}
import sqlite3, re, glob
M1 = '''
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
db = SQLAlchemy(); migrate = Migrate()
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
def create_app():
    app = Flask(__name__); app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
    db.init_app(app); migrate.init_app(app, db); return app
app = create_app()
'''
d = mkapp('f74', {'models.py': M1})
def fl(*args, check=False):
    r = subprocess.run([str(BIN / 'flask'), '--app', 'models', *args], cwd=d, env=env(d), capture_output=True, text=True); out = tidy(r.stdout + r.stderr); return r.returncode, out
def tables(): 
    if not (d / 'instance' / 'app.db').exists(): return None
    con = sqlite3.connect(d / 'instance' / 'app.db'); r = con.execute("select name from sqlite_master where type='table' order by 1").fetchall(); con.close(); return [x[0] for x in r]
def cols(t): con = sqlite3.connect(d / 'instance' / 'app.db'); r = [(x[1], x[2], x[3]) for x in con.execute(f'pragma table_info({t})')]; con.close(); return r
def pr(txt, n=12, w=170): L = txt.split('\n'); print('\n'.join('    ' + l[:w] for l in L[:n])); print(f'    …(共 {len(L)} 行)' if len(L) > n else '', end='')
print('== 一:flask db init:创建 migrations/ 目录')
rc, o = fl('db', 'init'); print(f'  退出码 {rc}'); pr(o, 6); files = sorted(str(p.relative_to(d)) for p in (d / 'migrations').rglob('*') if p.is_file() and '__pycache__' not in str(p)); print('\n  生成的文件:', files); R['init'] = files
print('  此时数据库里的表:', tables(), '(还没有迁移,数据库文件都没创建)'); R['tables0'] = tables()
print()
print('== 二:flask db migrate:对比模型与数据库,自动生成迁移脚本(这一步不改数据库)')
rc, o = fl('db', 'migrate', '-m', 'create user table'); print(f'  退出码 {rc}'); L = [l for l in o.split('\n') if 'Detected' in l or 'Generating' in l]; print('\n'.join('    ' + l.replace(str(d), '<项目>') for l in L)); R['migrate1'] = L
ver = sorted(glob.glob(str(d / 'migrations' / 'versions' / '*.py')))[0]; txt = open(ver).read(); body = txt.split('def upgrade')[1]; print('  迁移脚本里的 upgrade()/downgrade()(节选):'); print('\n'.join('    ' + l for l in ('def upgrade' + body).split('\n') if l.strip())[:900]); R['script1'] = ('def upgrade' + body)[:700]
print('  revision / down_revision:', re.search(r"revision = '(\w+)'", txt).group(1), '/', re.search(r"down_revision = (.+)", txt).group(1)); R['rev1'] = re.search(r"revision = '(\w+)'", txt).group(1)
print('  执行 migrate 之后数据库里的表:', tables(), '(migrate 只生成脚本)'); R['tables1'] = tables()
print()
print('== 三:flask db upgrade:执行迁移;alembic_version 表记录当前版本')
rc, o = fl('db', 'upgrade'); print(f'  退出码 {rc}'); print('\n'.join('    ' + l for l in o.split('\n') if 'Running' in l)); R['upgrade1'] = [l for l in o.split('\n') if 'Running' in l]
print('  数据库里的表:', tables()); print('  user 表的列:', cols('user')); R['tables2'] = tables(); R['cols1'] = cols('user')
con = sqlite3.connect(d / 'instance' / 'app.db'); print('  alembic_version 里的值:', con.execute('select * from alembic_version').fetchall()); con.close()
cur = [l for l in fl('db', 'current')[1].split('\n') if re.match(r'^[0-9a-f]{12}', l)]; print('  flask db current:', cur); R['current1'] = cur
print()
print('== 四:模型改了(加列 email、加表 Post)→ 再 migrate → upgrade')
M2 = M1.replace("    name = db.Column(db.String(50), nullable=False)\n", "    name = db.Column(db.String(50), nullable=False)\n    email = db.Column(db.String(120))\nclass Post(db.Model):\n    id = db.Column(db.Integer, primary_key=True)\n    title = db.Column(db.String(100))\n    user_id = db.Column(db.ForeignKey('user.id'))\n")
(d / 'models.py').write_text(M2)
rc, o = fl('db', 'migrate', '-m', 'add email and post'); print('  migrate:', [l.replace(str(d), '<项目>') for l in o.split('\n') if 'Detected' in l]); R['migrate2'] = [l for l in o.split('\n') if 'Detected' in l]
vers = sorted(glob.glob(str(d / 'migrations' / 'versions' / '*.py')), key=os.path.getmtime); txt2 = open(vers[-1]).read(); print('  第二个迁移脚本 upgrade() 里的操作:', re.findall(r'op\.(\w+)\(', txt2.split('def downgrade')[0])); R['ops2'] = re.findall(r'op\.(\w+)\(', txt2.split('def downgrade')[0]); print('  downgrade() 里的操作:', re.findall(r'op\.(\w+)\(', txt2.split('def downgrade')[1])); R['ops2_down'] = re.findall(r'op\.(\w+)\(', txt2.split('def downgrade')[1])
print('  down_revision 指向第一个迁移:', re.search(r"down_revision = '(\w+)'", txt2).group(1) == R['rev1'])
rc, o = fl('db', 'upgrade'); print('  upgrade 后表:', tables(), '| user 的列:', [c[0] for c in cols('user')]); R['tables3'] = tables(); R['cols2'] = [c[0] for c in cols('user')]
print()
print('== 五:flask db downgrade:回退一步;history 看版本链')
print('  flask db history:'); h = fl('db', 'history')[1]; print('\n'.join('    ' + re.sub(r'\s+', ' ', l)[:110] for l in h.split('\n') if l.strip())); R['history'] = [re.sub(r'\s+', ' ', l)[:110] for l in h.split('\n') if l.strip()]
rc, o = fl('db', 'downgrade'); print('  downgrade 之后表:', tables(), '| user 的列:', [c[0] for c in cols('user')]); R['tables4'] = tables(); R['cols3'] = [c[0] for c in cols('user')]
print()
print('== 六:自动生成的局限:重命名列会被识别成「删除旧列 + 新增新列」(数据会丢)')
fl('db', 'upgrade'); M3 = M2.replace('email = db.Column', 'mail = db.Column'); (d / 'models.py').write_text(M3)
rc, o = fl('db', 'migrate', '-m', 'rename email to mail'); vers = sorted(glob.glob(str(d / 'migrations' / 'versions' / '*.py')), key=os.path.getmtime); txt3 = open(vers[-1]).read(); print('  upgrade() 里的操作:', re.findall(r"op\.(\w+)\(|batch_op\.(\w+)\(", txt3.split('def downgrade')[0])); R['ops3'] = [a or b for a, b in re.findall(r"op\.(\w+)\(|batch_op\.(\w+)\(", txt3.split('def downgrade')[0])]
print('  相关语句:', [l.strip() for l in txt3.split('def downgrade')[0].split('\n') if 'column' in l.lower()][:4]); R['rename_lines'] = [l.strip() for l in txt3.split('def downgrade')[0].split('\n') if 'column' in l.lower()][:4]
print()
print('== 七:多个开发者各自生成迁移 → 出现两个 head,需要 merge')
(d / 'models.py').write_text(M2); sh = lambda *a: subprocess.run([str(BIN / 'flask'), '--app', 'models', *a], cwd=d, env=env(d), capture_output=True, text=True)
for f in glob.glob(str(d / 'migrations' / 'versions' / '*rename*')): os.remove(f)
vers = sorted(glob.glob(str(d / 'migrations' / 'versions' / '*.py')), key=os.path.getmtime); last = re.search(r"revision = '(\w+)'", open(vers[-1]).read()).group(1)
for i in (1, 2): (d / 'migrations' / 'versions' / f'branch{i}_aaaa{i}.py').write_text(f'"""b{i}"""\nrevision = "aaaa{i}"\ndown_revision = "{last}"\nbranch_labels = None\ndepends_on = None\nfrom alembic import op\ndef upgrade(): pass\ndef downgrade(): pass\n')
r = sh('db', 'heads'); print('  flask db heads:', [l.split(' ')[0] for l in (r.stdout + r.stderr).strip().split('\n') if l.strip()]); R['heads'] = len([l for l in (r.stdout + r.stderr).strip().split('\n') if l.strip()])
r = sh('db', 'upgrade'); print('  有两个 head 时 flask db upgrade →', tidy(r.stdout + r.stderr).strip().split('\n')[-1][:150]); R['two_heads'] = tidy(r.stdout + r.stderr).strip().split('\n')[-1][:150]
r = sh('db', 'merge', '-m', 'merge heads', 'aaaa1', 'aaaa2'); print('  flask db merge →', [l.replace(str(d), '<项目>')[:100] for l in (r.stdout + r.stderr).split('\n') if 'Generating' in l]); r = sh('db', 'heads'); print('  合并后 heads 数:', len([l for l in (r.stdout + r.stderr).strip().split('\n') if l.strip()])); R['heads_after'] = len([l for l in (r.stdout + r.stderr).strip().split('\n') if l.strip()])
save('f74', R)
