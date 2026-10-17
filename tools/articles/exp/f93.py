import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f93'); R = {}
import dj
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
pg = dj.PG(9464, name='f93pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
pg.psql("create table if not exists note (id serial primary key, title text, ver int default 0, updated timestamptz default now())")
pg.psql("create or replace function touch() returns trigger as $$ begin new.updated = clock_timestamp(); new.ver = old.ver + 1; return new; end $$ language plpgsql")
pg.psql("create trigger note_touch before update on note for each row execute function touch()")
def build(expire):
    app = Flask('e'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = URL
    db = SQLAlchemy(app, session_options={'expire_on_commit': expire})
    class Note(db.Model):
        __tablename__ = 'note'
        id = db.Column(db.Integer, primary_key=True); title = db.Column(db.Text); ver = db.Column(db.Integer, server_default='0'); updated = db.Column(db.DateTime(timezone=True))
    sql = []
    with app.app_context(): event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append(' '.join(st.split())))
    return app, db, Note, sql
try:
    print('== 一:commit 之后再读属性,要不要再发 SQL?')
    R['extra'] = {}
    for expire in (True, False):
        app, db, Note, sql = build(expire)
        with app.app_context():
            n = Note(title='t'); db.session.add(n); db.session.commit(); sql.clear(); t = n.title; i = n.id
            print(f'  expire_on_commit={expire!s:<5} commit 之后读 n.title 与 n.id:新发 {len(sql)} 条 SQL' + (f' → {sql[0][:70]}' if sql else '')); R['extra'][str(expire)] = len(sql)
    print()
    print('== 二:离开 session 之后(请求结束)还能不能读属性?')
    R['detached'] = {}
    for expire in (True, False):
        app, db, Note, sql = build(expire); box = []
        @app.get('/mk')
        def mk(): n = Note(title='x'); db.session.add(n); db.session.commit(); box.append(n); return 'ok'
        app.test_client().get('/mk')
        try: v = box[0].title; r_ = f'读到 {v!r}'
        except Exception as e: r_ = type(e).__name__
        print(f'  expire_on_commit={expire!s:<5} 请求结束后读 box[0].title → {r_}'); R['detached'][str(expire)] = r_
    print()
    print('== 三:陈旧数据:另一个连接改了行(含触发器改的列),本会话 commit 之后看到的值')
    R['stale'] = {}
    for expire in (True, False):
        app, db, Note, sql = build(expire)
        with app.app_context():
            n = Note(title='orig'); db.session.add(n); db.session.commit(); nid = n.id; _ = n.ver
            pg.psql(f"update note set title='changed-by-other' where id={nid}")
            n.title = 'mine'; db.session.commit()
            row = pg.psql(f"select title, ver from note where id={nid}")
            print(f'  expire_on_commit={expire!s:<5} 库里实际: {row} | 本会话对象 n.title = {n.title!r}, n.ver = {n.ver}'); R['stale'][str(expire)] = [row, n.title, n.ver]
    print()
    print('== 四:触发器改了的列(ver、updated)commit 之后对象里是不是新值')
    R['trigger'] = {}
    for expire in (True, False):
        app, db, Note, sql = build(expire)
        with app.app_context():
            n = Note(title='trg'); db.session.add(n); db.session.commit(); v0 = n.ver; n.title = 'trg2'; db.session.commit(); v1 = n.ver; actual = pg.psql(f"select ver from note where id={n.id}")
            print(f'  expire_on_commit={expire!s:<5} 更新并 commit 后对象 n.ver = {v1}(提交前 {v0}),库里实际 ver = {actual}'); R['trigger'][str(expire)] = [v0, v1, actual]
    print()
    print('== 五:代价:commit 1000 个对象之后逐个读属性(各 5 次取中位数)')
    R['cost'] = {}
    for expire in (True, False):
        app, db, Note, sql = build(expire); L = []; nq = 0
        for _ in range(5):
            with app.app_context():
                objs = [Note(title=f't{i}') for i in range(1000)]; db.session.add_all(objs); db.session.commit(); sql.clear(); t0 = time.perf_counter(); [o.title for o in objs]; L.append(ms(t0)); nq = len(sql)
                db.session.execute(sa.delete(Note)); db.session.commit()
        print(f'  expire_on_commit={expire!s:<5} 逐个读 title:{median(L):>7.1f} ms,{nq} 条 SQL'); R['cost'][str(expire)] = [median(L), nq]
finally:
    pg.stop()
save('f93', R)
