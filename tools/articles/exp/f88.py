import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f88'); R = {}
import gc, warnings
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
dbf = FT / 'f88.db'; dbf.unlink(missing_ok=True)
app = Flask('i'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{dbf}'; db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20)); score = db.Column(db.Integer, default=0)
sql = []
with app.app_context():
    db.create_all(); db.session.add_all([User(name=f'u{i}') for i in range(5)]); db.session.commit(); db.session.remove()
    event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append(' '.join(st.split())))
def sess(): return orm.Session(db.engine)
with app.app_context():
    print('== 一:同一个 session 里,同一行永远是同一个 Python 对象')
    s = sess(); a = s.execute(sa.select(User).where(User.id == 1)).scalar_one(); sql.clear(); b = s.execute(sa.select(User).where(User.name == 'u0')).scalar_one()
    print(f'  用两种不同的条件查同一行:a is b → {a is b}(第二次仍然发了 {len(sql)} 条 SQL,但返回的是已有对象)'); R['same'] = [a is b, len(sql)]
    print('  不同的 session 里查同一行 → 不同对象:', a is not sess().execute(sa.select(User).where(User.id == 1)).scalar_one()); R['diff_sess'] = True
    print('  identity key:', sa.inspect(a).key)
    print()
    print('== 二:session.get(User, 1) 先看身份映射,命中就不发 SQL')
    sql.clear(); x = s.get(User, 1); print(f'  已经加载过的主键:get 发了 {len(sql)} 条 SQL,x is a → {x is a}'); R['get_hit'] = len(sql)
    sql.clear(); y = s.get(User, 2); print(f'  没加载过的主键:get 发了 {len(sql)} 条 SQL'); R['get_miss'] = len(sql)
    sql.clear(); z = s.get(User, 2); print(f'  再 get 一次:{len(sql)} 条'); R['get_hit2'] = len(sql)
    sql.clear(); n = s.get(User, 999); print(f'  不存在的主键 999:{len(sql)} 条 SQL,返回 {n};再 get 一次 999:', end=' '); sql.clear(); s.get(User, 999); print(f'{len(sql)} 条(不存在的结果不缓存)'); R['get_none'] = len(sql)
    s.close()
    print()
    print('== 三:身份映射是弱引用的:没有人引用且没被修改的对象会被回收')
    s = sess(); objs = s.execute(sa.select(User)).scalars().all(); print('  加载 5 个对象后 identity_map 大小:', len(s.identity_map)); R['wk1'] = len(s.identity_map)
    del objs; gc.collect(); print('  del 掉列表并 gc 之后:', len(s.identity_map)); R['wk2'] = len(s.identity_map)
    objs = s.execute(sa.select(User)).scalars().all(); objs[0].name = 'dirty'; del objs; gc.collect(); print('  改了一个对象再丢掉引用并 gc:', len(s.identity_map), '(被修改的对象 session 持有强引用,直到 flush)'); R['wk3'] = len(s.identity_map)
    s.rollback(); s.close()
    print()
    print('== 四:代价:同一个 session 里重新查询不会刷新已经加载的对象(看到的是旧数据)')
    s = sess(); a = s.execute(sa.select(User).where(User.id == 3)).scalar_one(); print('  session A 读到 score =', a.score)
    with sess() as s2: s2.execute(sa.update(User).where(User.id == 3).values(score=99)); s2.commit()
    a2 = s.execute(sa.select(User).where(User.id == 3)).scalar_one(); print('  另一个 session 把 score 改成 99 并提交之后,session A 重新查询:a2.score =', a2.score, '(a2 is a →', a2 is a, ')'); R['stale'] = a2.score
    a3 = s.execute(sa.select(User).where(User.id == 3).execution_options(populate_existing=True)).scalar_one(); print('  populate_existing=True 重新查询:score =', a3.score); R['populate'] = a3.score
    with sess() as s2: s2.execute(sa.update(User).where(User.id == 3).values(score=100)); s2.commit()
    s.refresh(a); print('  session.refresh(a) 之后:score =', a.score); R['refresh'] = a.score
    with sess() as s2: s2.execute(sa.update(User).where(User.id == 3).values(score=101)); s2.commit()
    s.expire(a); print('  session.expire(a) 之后下一次读取:score =', a.score); R['expire'] = a.score
    s.close()
    print()
    print('== 五:同一个主键的两个对象:add 一个与已有 persistent 对象主键相同的新对象')
    s = sess(); a = s.get(User, 1)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always'); s.add(User(id=1, name='dup'))
        try: s.flush(); r_ = '成功'
        except Exception as e: r_ = f'{type(e).__name__}: {str(e).splitlines()[0][:100]}'
    print('  ', r_); R['dup'] = r_
    s.rollback(); s.close()
print('(以下在 with app.app_context() 之外运行,否则请求会复用外层的应用上下文)') if False else None
print()
print('== 六:Flask 里的边界:每个请求(应用上下文)一个新 session,身份映射是请求内的')
holder = []
@app.get('/u')
def u(): o = db.session.get(User, 1); holder.append(o); return o.name
c = app.test_client(); c.get('/u'); c.get('/u')
print('  两个请求里 get 到的是不是同一个对象:', holder[0] is holder[1]); R['req'] = holder[0] is holder[1]
with app.app_context():
    sql.clear(); db.session.get(User, 1); db.session.get(User, 1); n1 = len(sql)
    print(f'  同一个请求里连续 get 两次,但不保留返回值:共发 {n1} 条 SQL(第一次的对象没人引用,被回收了,第二次只好重新查)')
    sql.clear(); keep = db.session.get(User, 1); db.session.get(User, 1); n2 = len(sql)
    print(f'  保留第一次的返回值再 get:共发 {n2} 条 SQL'); R['ctx'] = [n1, n2]

save('f88', R)
