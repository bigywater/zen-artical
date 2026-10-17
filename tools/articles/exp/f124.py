import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f124'); R = {}
import dj, logging, io
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event
pg = dj.PG(9474, name='f124pg').start()
try:
    app = Flask('s'); app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(30)); city = db.Column(db.String(20))
    sql = []
    with app.app_context():
        db.create_all(); db.session.add_all([User(name=n, city='x') for n in ("O'Brien", 'Ann', '50%_off', 'Bob')]); db.session.commit()
        event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append((' '.join(st.split()), p)))
    def t(fn):
        try: return fn()
        except Exception as e: return f'{type(e).__name__}: ' + str(getattr(e, 'orig', e)).splitlines()[0][:70]
    with app.app_context():
        print("== 一:名字里带单引号的正常用户(O'Brien):字符串拼接 SQL 与参数绑定")
        name = "O'Brien"
        r1 = t(lambda: db.session.execute(sa.text(f"select id from \"user\" where name = '{name}'")).all()); print('  f-string 拼接 →', r1); R['concat'] = str(r1)
        db.session.rollback(); sql.clear()
        r2 = db.session.execute(sa.text('select id from "user" where name = :n'), {'n': name}).all(); print('  绑定参数 :n →', r2); print('  发给数据库的语句与参数:', sql[-1]); R['bind'] = [str(r2), str(sql[-1])]
        sql.clear(); r3 = db.session.execute(sa.select(User.id).where(User.name == name)).all(); print('  ORM 表达式 →', r3); print('  发给数据库的语句与参数:', sql[-1]); R['orm'] = [str(r3), str(sql[-1])]
        print('  结论:引号被当作数据,不需要自己转义;拼接则把数据当成了 SQL 的一部分,正常输入也会出错')
        print()
        print('== 二:不能参数化的位置:表名、列名、排序方向——用白名单')
        ALLOWED = {'name': User.name, 'id': User.id}
        def order_by(col, direction):
            c = ALLOWED.get(col)
            if c is None: raise ValueError(f'不允许按 {col!r} 排序')
            return c.desc() if direction == 'desc' else c.asc()
        for col, d in (('name', 'asc'), ('id', 'desc'), ('password', 'asc')):
            try: rows = db.session.execute(sa.select(User.name).order_by(order_by(col, d))).scalars().all(); print(f'  排序列 {col!r} {d} → {rows}'); R.setdefault('order', {})[f'{col} {d}'] = rows
            except ValueError as e: print(f'  排序列 {col!r} {d} → 拒绝:{e}'); R.setdefault('order', {})[f'{col} {d}'] = str(e)
        r = t(lambda: db.session.execute(sa.text('select name from "user" order by :c'), {'c': 'name'}).scalars().all()); print('  把列名当绑定参数 order by :c →', r, '(只是按常量字符串排序,不会按列排序)'); R['order_param'] = str(r)
        print()
        print('== 三:LIKE 里的通配符 % 与 _ 也是数据:要转义;IN 列表用 in_()')
        sql.clear(); term = '50%_off'
        r1 = db.session.execute(sa.select(User.name).where(User.name.like(f'%{term}%'))).scalars().all(); print(f"  like('%{term}%')(不转义,% 与 _ 当通配符)→", r1)
        r2 = db.session.execute(sa.select(User.name).where(User.name.contains(term, autoescape=True))).scalars().all(); print('  contains(term, autoescape=True) →', r2); print('  发出的语句:', sql[-1][0][-70:], sql[-1][1]); R['like'] = [r1, r2]
        r3 = db.session.execute(sa.select(User.name).where(User.name.in_(['Ann', 'Bob', "O'Brien"]))).scalars().all(); print('  in_([...]) →', r3, '| 语句:', sql[-1][0][-60:]); R['in'] = r3
        print()
        print('== 四:text() 里用 :name 绑定时,SQLAlchemy 把值交给驱动(服务端绑定还是客户端拼接?看 PG 日志里的语句)')
        pg.psql("alter system set log_statement = 'all'"); pg.psql('select pg_reload_conf()'); time.sleep(0.5)
        db.session.execute(sa.text('select id from "user" where name = :n'), {'n': "O'Brien"}).all(); db.session.commit(); time.sleep(0.5)
        log = (pg.dir / 'pg.log').read_text().splitlines(); lines = [l for l in log if 'from "user" where name' in l.lower()][-3:]; [print('   PG 日志:', l.split('LOG:')[-1].strip()[:150]) for l in lines]; R['pglog'] = [l.split('LOG:')[-1].strip()[:150] for l in lines]
finally:
    pg.stop()
save('f124', R)
