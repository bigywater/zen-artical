import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f98'); R = {}
import sqlite3, re, glob, dj
pg = dj.PG(9468, name='f98pg').start()
MODEL = '''
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
db = SQLAlchemy(); migrate = Migrate(render_as_batch=True)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
def create_app():
    app = Flask(__name__); app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]
    db.init_app(app); migrate.init_app(app, db); return app
app = create_app()
'''
class P:
    n = 0
    def __init__(self, kind):
        P.n += 1; self.kind = kind; self.d = mkapp(f'f98_{P.n}', {'models.py': MODEL})
        self.url = f'sqlite:///app.db' if kind == 'sqlite' else f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
        if kind == 'pg': pg.psql('drop schema public cascade; create schema public')
        self.fl('db', 'init'); self.fl('db', 'migrate', '-m', 'base', '--rev-id', 'r001'); self.fl('db', 'upgrade')
    def fl(self, *args):
        r = subprocess.run([str(BIN / 'flask'), '--app', 'models', *args], cwd=self.d, env=env(self.d, DB=self.url), capture_output=True, text=True); return r.returncode, tidy(r.stdout + r.stderr)
    def q(self, sql):
        if self.kind == 'pg': return pg.psql(sql)
        con = sqlite3.connect(self.d / 'instance' / 'app.db'); r = con.execute(sql).fetchall(); con.commit(); con.close(); return r
    def rev(self, rid, up, down, msg='m'):
        self.fl('db', 'revision', '-m', msg, '--rev-id', rid); f = [x for x in glob.glob(str(self.d / 'migrations' / 'versions' / f'{rid}_*.py'))][0]; t = open(f).read()
        t = re.sub(r"def upgrade\(\):.*?\n\n\ndef downgrade\(\):.*$", 'def upgrade():\n' + up + '\n\n\ndef downgrade():\n' + down + '\n', t, flags=re.S); open(f, 'w').write(t)
    def cols(self): return [c[1] for c in self.q('pragma table_info(user)')] if self.kind == 'sqlite' else pg.psql("select column_name from information_schema.columns where table_name='user' order by ordinal_position").splitlines()
    def ver(self): r = self.q('select version_num from alembic_version'); return r if self.kind == 'pg' else [x[0] for x in r]
def last_err(o):
    L = [l for l in o.splitlines() if re.match(r'(sqlalchemy\.exc\.|psycopg\.|sqlite3\.|ERROR|ValueError|NotImplemented)', l)]; return L[-1][:170] if L else o.splitlines()[-1][:150]
try:
    print('== 一:downgrade 之后数据没了:加一列并写入数据,downgrade 删列,再 upgrade 加回来')
    p = P('sqlite'); p.rev('r002', "    op.add_column('user', sa.Column('score', sa.Integer(), nullable=True))", "    with op.batch_alter_table('user') as b:\n        b.drop_column('score')")
    p.fl('db', 'upgrade'); p.q("insert into user (name, score) values ('ann', 42)"); print('  upgrade 后:', p.q('select name, score from user')); 
    p.fl('db', 'downgrade'); print('  downgrade 后的列:', p.cols()); p.fl('db', 'upgrade'); after = p.q('select name, score from user'); print('  再 upgrade 后:', after, '(score 的值丢了)'); R['dataloss'] = after
    print()
    print('== 二:迁移到一半失败:同一个迁移里先加一列(成功)、再加一个 NOT NULL 列(表里有数据,失败)。SQLite 与 PostgreSQL 的差别')
    UP = "    op.add_column('user', sa.Column('a_col', sa.Integer(), nullable=True))\n    op.add_column('user', sa.Column('b_col', sa.Integer(), nullable=False))"
    DOWN = "    op.drop_column('user', 'b_col')\n    op.drop_column('user', 'a_col')"
    R['half'] = {}
    for kind in ('pg', 'sqlite'):
        p = P(kind); p.q("insert into \"user\" (name) values ('x')" if kind == 'pg' else "insert into user (name) values ('x')"); p.rev('r002', UP, DOWN)
        rc, o = p.fl('db', 'upgrade'); print(f'  [{kind}] upgrade 退出码 {rc}:{last_err(o)}'); print(f'  [{kind}] 失败之后的列: {p.cols()} | alembic_version: {p.ver()}')
        rc2, o2 = p.fl('db', 'upgrade'); print(f'  [{kind}] 修好问题前直接再 upgrade 一次 → 退出码 {rc2}:{last_err(o2)}'); R['half'][kind] = dict(rc=rc, err=last_err(o), cols=p.cols(), ver=str(p.ver()), rc2=rc2, err2=last_err(o2))
    print()
    print('== 三:不可逆的迁移:downgrade 里主动报错,比悄悄丢数据好')
    p = P('sqlite'); p.rev('r002', "    op.execute(\"update user set name = upper(name)\")", "    raise NotImplementedError('这个迁移不可逆:原来的大小写已经丢了')", 'upper')
    rc, o = p.fl('db', 'upgrade'); rc, o = p.fl('db', 'downgrade'); print('  downgrade →', f'退出码 {rc}:', last_err(o)); print('  版本记录仍在 r002:', p.ver()); R['irrev'] = [rc, last_err(o), p.ver()]
    print()
    print('== 四:downgrade 的几种目标:-1、具体 revision、base')
    p = P('sqlite'); p.rev('r002', "    op.add_column('user', sa.Column('c2', sa.Integer()))", "    with op.batch_alter_table('user') as b:\n        b.drop_column('c2')"); p.rev('r003', "    op.add_column('user', sa.Column('c3', sa.Integer()))", "    with op.batch_alter_table('user') as b:\n        b.drop_column('c3')"); p.fl('db', 'upgrade'); print('  upgrade 后版本:', p.ver(), '列:', p.cols())
    p.fl('db', 'downgrade', '--', '-1'); print('  downgrade -- -1 后:', p.ver(), p.cols())
    p.fl('db', 'upgrade'); p.fl('db', 'downgrade', 'r001'); print('  downgrade r001 后:', p.ver(), p.cols())
    p.fl('db', 'upgrade'); p.fl('db', 'downgrade', 'base'); print('  downgrade base 后:', p.ver(), '| 表:', [r[0] for r in p.q("select name from sqlite_master where type='table' order by 1")]); R['targets'] = p.ver()
finally:
    pg.stop()
save('f98', R)
