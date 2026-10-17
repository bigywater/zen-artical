import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f90'); R = {}
import dj
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
from sqlalchemy.exc import IntegrityError
pg = dj.PG(9461, name='f90pg').start()
try:
    app = Flask('r'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class Acct(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20), unique=True); bal = db.Column(db.Integer, default=0)
    sql = []
    with app.app_context():
        db.drop_all(); db.create_all(); event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append(' '.join(st.split())))
        db.session.add_all([Acct(name='a', bal=100), Acct(name='b', bal=50)]); db.session.commit()
    def state(o):
        i = sa.inspect(o); return [n for n in ('transient', 'pending', 'persistent', 'detached', 'deleted') if getattr(i, n)][0] + (' (expired)' if i.expired else '')
    print('== 一:rollback 之后各种对象的状态')
    with app.app_context():
        a = db.session.get(Acct, 1); a.bal = 999; new = Acct(name='n'); db.session.add(new); db.session.flush(); d = db.session.get(Acct, 2); db.session.delete(d); db.session.flush()
        before = {'a(改了 bal)': state(a), 'new(已 flush 的新对象)': state(new), 'd(已 delete + flush)': state(d)}
        db.session.rollback(); after = {'a(改了 bal)': state(a), 'new(已 flush 的新对象)': state(new), 'd(已 delete + flush)': state(d)}
        for k in before: print(f'  {k:<24} {before[k]:<22} → {after[k]}')
        sql.clear(); print('  rollback 之后访问 a.bal =', a.bal, f'(重新发了 {len(sql)} 条 SELECT;内存里改成 999 的值丢了)'); R['states'] = [before, after]; R['a_bal'] = a.bal
        print('  d 回到数据库里:', db.session.execute(sa.text('select count(*) from acct where id=2')).scalar() == 1)
    print()
    print('== 二:rollback 撤销不了的东西:序列号(自增主键)已经消耗')
    with app.app_context():
        db.session.add(Acct(name='s1')); db.session.flush(); id1 = db.session.execute(sa.text("select max(id) from acct")).scalar(); db.session.rollback()
        db.session.add(Acct(name='s2')); db.session.commit(); id2 = db.session.execute(sa.text("select id from acct where name='s2'")).scalar()
        print(f'  回滚掉的 INSERT 用过 id={id1};下一次成功插入的 id={id2}(中间有空洞)'); R['seq'] = [id1, id2]
    print()
    print('== 三:嵌套事务(保存点):rollback 只回到保存点')
    with app.app_context():
        db.session.add(Acct(name='outer')); sp = db.session.begin_nested(); db.session.add(Acct(name='inner')); sp.rollback(); db.session.commit()
        print('  outer 在库里:', db.session.execute(sa.text("select count(*) from acct where name='outer'")).scalar() == 1, '| inner 在库里:', db.session.execute(sa.text("select count(*) from acct where name='inner'")).scalar() == 1); R['sp'] = [db.session.execute(sa.text("select count(*) from acct where name='outer'")).scalar(), db.session.execute(sa.text("select count(*) from acct where name='inner'")).scalar()]
    print()
    print('== 四:commit 失败之后:session 被自动回滚,但要显式 rollback 才能继续用')
    with app.app_context():
        db.session.add(Acct(name='a')); 
        try: db.session.commit()
        except IntegrityError as e: print('  第一次 commit →', type(e).__name__, '/', type(e.orig).__name__)
        db.session.add(Acct(name='after_fail'))
        try: db.session.commit(); r_ = '成功'
        except Exception as e: r_ = f'{type(e).__name__}: {str(e)[:100]}'
        print('  没 rollback 就继续 commit →', r_); R['pending'] = r_
        import warnings
        with warnings.catch_warnings(record=True) as wl:
            warnings.simplefilter('always'); db.session.rollback()
        for w_ in wl: print('  rollback() 时的警告:', type(w_.message).__name__ + ':', str(w_.message)[:100]); R['warn'] = [type(w_.message).__name__, str(w_.message)[:100]]
        db.session.add(Acct(name='after_fail')); db.session.commit(); print('  rollback 之后重新来 → 成功,库里有 after_fail:', db.session.execute(sa.text("select count(*) from acct where name='after_fail'")).scalar() == 1)
    print()
    print('== 五:底层(Core 连接)出错后:PostgreSQL 事务进入 aborted 状态,不 rollback 什么都执行不了')
    with app.app_context():
        conn = db.engine.connect()
        try: conn.execute(sa.text("insert into acct (name) values ('a')"))
        except Exception as e: print('  违反唯一约束:', type(e.orig).__name__)
        try: conn.execute(sa.text('select 1'))
        except Exception as e: print('  接着执行 select 1 →', type(e.orig).__name__, ':', str(e.orig).splitlines()[0][:80]); R['aborted'] = [type(e.orig).__name__, str(e.orig).splitlines()[0][:80]]
        conn.rollback(); print('  rollback 之后 select 1 →', conn.execute(sa.text('select 1')).scalar()); conn.close()
    print()
    print('== 六:commit 之后的 rollback 没有任何效果')
    with app.app_context():
        x = Acct(name='committed'); db.session.add(x); db.session.commit(); db.session.rollback()
        print('  commit 后再 rollback,库里的 committed:', db.session.execute(sa.text("select count(*) from acct where name='committed'")).scalar()); R['after_commit'] = db.session.execute(sa.text("select count(*) from acct where name='committed'")).scalar()
    print()
    print('== 七:Flask 里没人调用 rollback:视图抛异常或直接结束,请求结束时 session 被清理')
    @app.get('/w')
    def w(): db.session.add(Acct(name='viewlost')); db.session.flush(); raise RuntimeError('x')
    app.config['PROPAGATE_EXCEPTIONS'] = False; r = app.test_client().get('/w')
    with app.app_context(): print(f'  视图 flush 后抛异常(HTTP {r.status_code}),库里的 viewlost:', db.session.execute(sa.text("select count(*) from acct where name='viewlost'")).scalar()); R['view'] = [r.status_code, db.session.execute(sa.text("select count(*) from acct where name='viewlost'")).scalar()]
    print('  同时 PG 里是否留下 idle in transaction 的连接:', pg.psql("select count(*) from pg_stat_activity where datname='lab' and state like 'idle in transaction%' and pid <> pg_backend_pid()")); R['idle_txn'] = pg.psql("select count(*) from pg_stat_activity where datname='lab' and state like 'idle in transaction%' and pid <> pg_backend_pid()")
finally:
    pg.stop()
save('f90', R)
