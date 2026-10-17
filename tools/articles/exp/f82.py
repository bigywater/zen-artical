import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f82'); R = {}
import dj
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
pg = dj.PG(9454, name='f82pg').start()
try:
    app = Flask('s'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class Author(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(30))
        books = db.relationship('Book', back_populates='author')
    class Book(db.Model):
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.String(30)); author_id = db.Column(db.ForeignKey('author.id')); author = db.relationship(Author, back_populates='books')
    with app.app_context(): db.create_all()
    def state(o):
        i = sa.inspect(o); return [n for n in ('transient', 'pending', 'persistent', 'detached', 'deleted') if getattr(i, n)][0] + (' (expired)' if i.expired else '')
    def pgstate(): return pg.psql("select coalesce(string_agg(state, ','), '(无连接)') from pg_stat_activity where datname='lab' and pid <> pg_backend_pid() and backend_type='client backend'")
    print('== 一:一个对象的五种状态:transient → pending → persistent → detached,以及 deleted')
    with app.app_context():
        a = Author(name='ann'); seq = [('Author(name=...)', state(a))]
        db.session.add(a); seq.append(('session.add(a)', state(a)))
        db.session.flush(); seq.append(('session.flush()', state(a)))
        db.session.commit(); seq.append(('session.commit()', state(a)))
        _ = a.name; seq.append(('读取 a.name', state(a)))
        db.session.delete(a); seq.append(('session.delete(a)', state(a)))
        db.session.flush(); seq.append(('flush()', state(a)))
        db.session.commit(); seq.append(('commit()', state(a)))
    for k, v in seq: print(f'  {k:<20} → {v}')
    R['states'] = seq
    print()
    print('== 二:事务与连接:Session 是「自动开始事务」的;用 pg_stat_activity 看服务端连接的状态')
    with app.app_context():
        s = db.session(); rows = [('一开始', s.in_transaction(), pgstate())]
        s.execute(sa.text('select 1')); rows.append(('执行了 select 1', s.in_transaction(), pgstate()))
        s.commit(); rows.append(('commit()', s.in_transaction(), pgstate()))
        s.execute(sa.text('select 1')); rows.append(('再执行 select 1', s.in_transaction(), pgstate()))
        s.rollback(); rows.append(('rollback()', s.in_transaction(), pgstate()))
    print(f'  {"动作":<16} {"in_transaction":<15} 服务端连接状态')
    for k, t, st in rows: print(f'  {k:<16} {t!s:<15} {st}')
    R['txn'] = rows
    print('  离开应用上下文之后(session.remove)服务端连接状态:', pgstate())
    print()
    print('== 三:一次 commit 里依次触发的事件(监听 Session 的事件)')
    log = []
    for ev in ('after_begin', 'before_flush', 'after_flush', 'after_flush_postexec', 'before_commit', 'after_commit', 'after_rollback', 'after_soft_rollback'):
        event.listen(db.session.__class__ if False else orm.Session, ev, (lambda ev: lambda *a, **k: log.append(ev))(ev))
    with app.app_context():
        a = Author(name='ev'); db.session.add(a); log.clear(); db.session.commit()
    print('  add 之后 commit():', log); R['events'] = list(log)
    with app.app_context():
        a = db.session.get(Author, a.id) if False else None
        log.clear(); b = Author(name='rb'); db.session.add(b); db.session.flush(); log.append('--'); db.session.rollback()
    print('  add + flush 然后 rollback():', log); R['events_rb'] = list(log)
    print()
    print('== 四:请求结束时 session 被 remove:没 commit 的改动丢弃;请求之外还想用对象会遇到 DetachedInstanceError')
    with app.app_context(): db.session.add(Author(name='bob')); db.session.commit()
    keep = []
    @app.get('/change')
    def change():
        a = db.session.execute(sa.select(Author).where(Author.name == 'bob')).scalar_one(); a.name = 'CHANGED'; keep.append(a); return 'ok'
    @app.get('/commit')
    def commit_():
        a = db.session.execute(sa.select(Author).where(Author.name == 'bob')).scalar_one(); a.name = 'COMMITTED'; db.session.commit(); keep.append(a); return 'ok'
    c = app.test_client(); c.get('/change')
    with app.app_context(): print('  /change 只改了属性没 commit,请求结束后库里 bob 的名字:', db.session.execute(sa.text("select name from author where id=(select min(id) from author where name in ('bob','CHANGED'))")).scalar()); R['lost'] = db.session.execute(sa.text("select name from author where id=(select min(id) from author where name in ('bob','CHANGED'))")).scalar()
    print('  请求结束后拿着视图里的对象 keep[0] 的状态:', state(keep[0]))
    try: print('  读已加载的属性 keep[0].name →', keep[0].name); R['detached_loaded'] = keep[0].name
    except Exception as e: print('  读属性 →', type(e).__name__)
    try: keep[0].books; r_ = '读到了'
    except Exception as e: r_ = f'{type(e).__name__}'
    print('  读没加载过的关系 keep[0].books →', r_); R['detached_lazy'] = r_
    keep.clear(); c.get('/commit')
    print('  /commit 里 commit 之后对象状态:', state(keep[0]))
    try: keep[0].name; r_ = '读到了'
    except Exception as e: r_ = f'{type(e).__name__}'
    print('  请求结束后读过期对象的属性 →', r_); R['expired_detached'] = r_
    print()
    print('== 五:session.close() 把所有对象变成 detached;重新 add 回来')
    with app.app_context():
        a = db.session.execute(sa.select(Author)).scalars().first(); b_ = state(a)
        db.session.close(); print(f'  close() 前 {b_},close() 后 {state(a)}')
        db.session.add(a); print('  重新 session.add(a) 后', state(a)); R['close'] = [b_, 'detached', state(a)]
        print('  session.identity_map 里的对象数:', len(db.session.identity_map))
finally:
    pg.stop()
save('f82', R)
