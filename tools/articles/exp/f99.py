import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f99'); R = {}
import dj, warnings, decimal, datetime as dt, threading
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import orm
pg = dj.PG(9469, name='f99pg').start()
dbf = FT / 'f99.db'; dbf.unlink(missing_ok=True)
URLS = {'sqlite': f'sqlite:///{dbf}', 'postgresql': f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'}
def build(kind, **opts):
    app = Flask('x'); app.config['SQLALCHEMY_DATABASE_URI'] = URLS[kind]
    if opts: app.config['SQLALCHEMY_ENGINE_OPTIONS'] = opts
    db = SQLAlchemy(app)
    class T(db.Model):
        __tablename__ = 't'; id = db.Column(db.Integer, primary_key=True); n = db.Column(db.Integer); s = db.Column(db.String(5)); price = db.Column(db.Numeric(8, 2)); at = db.Column(db.DateTime(timezone=True)); flag = db.Column(db.Boolean)
    class Parent(db.Model):
        __tablename__ = 'parent'; id = db.Column(db.Integer, primary_key=True)
    class Child(db.Model):
        __tablename__ = 'child'; id = db.Column(db.Integer, primary_key=True); pid = db.Column(db.ForeignKey('parent.id'))
    with app.app_context(): db.drop_all(); db.create_all()
    return app, db, T, Parent, Child
def tryit(f):
    try: return f()
    except Exception as e: return f'{type(e).__name__}: ' + (str(getattr(e, 'orig', e)).splitlines()[0][:80])
try:
    ENG = {k: build(k) for k in URLS}
    def row(label, fn):
        res = {k: tryit(lambda k=k: fn(*ENG[k])) for k in ENG}; print(f'  {label}'); [print(f'    {k:<11} {v}') for k, v in res.items()]; R[label] = res
    print('== 一:类型严格程度:同样的代码在两个数据库上')
    def a1(app, db, T, P, C):
        with app.app_context():
            db.session.execute(sa.text("insert into t (n) values ('abc')")); db.session.commit(); return '成功,库里 n = ' + repr(db.session.execute(sa.text('select n from t order by id desc limit 1')).scalar())
    row('往 INTEGER 列写字符串 "abc"', a1)
    def a2(app, db, T, P, C):
        with app.app_context(): db.session.add(T(s='abcdefghij')); db.session.commit(); return '成功,存进去的是 ' + repr(db.session.execute(sa.text('select s from t order by id desc limit 1')).scalar())
    row('往 String(5) 列写 10 个字符', a2)
    print()
    print('== 二:Numeric 与时区')
    def b1(app, db, T, P, C):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            with app.app_context(): db.session.add(T(price=decimal.Decimal('0.10') + decimal.Decimal('0.20'))); db.session.commit(); v = db.session.execute(sa.select(T.price).order_by(T.id.desc())).scalars().first()
        return f'读回 {v!r}({type(v).__name__})' + (f',警告:{type(w[0].message).__name__}' if w else '')
    row('Numeric(8,2) 存 Decimal("0.30")', b1)
    def b2(app, db, T, P, C):
        with app.app_context():
            t = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=8))); db.session.add(T(at=t)); db.session.commit(); v = db.session.execute(sa.select(T.at).order_by(T.id.desc())).scalars().first(); return f'存入 12:00+08:00,读回 {v!r}'
    row('DateTime(timezone=True) 存带时区的时间', b2)
    print()
    print('== 三:约束:外键是否生效;LIKE 是否区分大小写')
    def c1(app, db, T, P, C):
        with app.app_context(): db.session.add(C(pid=999)); db.session.commit(); return '成功(外键指向不存在的父行也写进去了)'
    row('插入指向不存在父行的子行(外键违反)', c1)
    def c2(app, db, T, P, C):
        with app.app_context():
            db.session.add(T(s='Hello')); db.session.commit(); n = db.session.execute(sa.select(sa.func.count()).select_from(T).where(T.s.like('hel%'))).scalar(); return f"LIKE 'hel%' 匹配 'Hello' 的行数 = {n}"
    row("WHERE s LIKE 'hel%'(数据是 'Hello')", c2)
    print()
    print('== 四:自增主键:删掉最大 id 的行之后再插入')
    def d1(app, db, T, P, C):
        with app.app_context():
            db.session.execute(sa.delete(P)); db.session.commit(); a = P(); b = P(); db.session.add_all([a, b]); db.session.commit(); ids1 = [a.id, b.id]; db.session.delete(b); db.session.commit(); c = P(); db.session.add(c); db.session.commit(); return f'先插入得到 {ids1},删掉 {ids1[1]} 再插入得到 {c.id}'
    row('主键复用', d1)
    print()
    print('== 五:并发写:两个连接同时写(SQLite 设 timeout=0.5 秒以免等太久)')
    for kind in URLS:
        app, db, T, P, C = build(kind, **({'connect_args': {'timeout': 0.5}} if kind == 'sqlite' else {})); res = {}
        with app.app_context(): ENGINE = db.engine
        def w1():
            s = orm.Session(ENGINE); s.add(T(n=1)); s.flush(); time.sleep(1.0); s.commit(); s.close(); res['w1'] = 'ok'
        def w2():
            time.sleep(0.2); s = orm.Session(ENGINE); t0 = time.perf_counter()
            try: s.add(T(n=2)); s.flush(); s.commit(); res['w2'] = f'ok,等了 {ms(t0):.0f} ms'
            except Exception as e: res['w2'] = f'{type(e).__name__}: {str(e.orig)[:40]},等了 {ms(t0):.0f} ms'; s.rollback()
            s.close()
        ths = [threading.Thread(target=w1), threading.Thread(target=w2)]; [t.start() for t in ths]; [t.join() for t in ths]
        print(f'  {kind:<11} 第二个连接写入(第一个持有未提交的写事务 1 秒):{res["w2"]}'); R.setdefault('concurrent', {})[kind] = res['w2']
finally:
    pg.stop()
save('f99', R)
