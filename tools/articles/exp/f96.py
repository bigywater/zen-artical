import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f96'); R = {}
import dj, logging, io
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.record_queries import get_recorded_queries
import sqlalchemy as sa
from sqlalchemy import event
pg = dj.PG(9467, name='f96pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
def mk(**cfg):
    app = Flask('q'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = URL; app.config.update(cfg); db = SQLAlchemy(app)
    class U(db.Model):
        __tablename__ = 'u'; id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20)); pw = db.Column(db.String(40))
    with app.app_context(): db.create_all()
    return app, db, U
def capture(level=logging.INFO):
    buf = io.StringIO(); h = logging.StreamHandler(buf); lg = logging.getLogger('sqlalchemy.engine'); lg.addHandler(h); lg.setLevel(level); return buf, h, lg
def stop(h, lg): lg.setLevel(logging.WARNING); lg.removeHandler(h)
try:
    print('== 一:SQLALCHEMY_ECHO=True 的输出:语句、参数,以及缓存标记(在单独的进程里运行,因为 echo 会给整个进程的 sqlalchemy 日志装上处理器)')
    CODE = """
import sqlalchemy as sa
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
app = Flask('q'); app.config['SQLALCHEMY_DATABASE_URI'] = %r; app.config['SQLALCHEMY_ECHO'] = True; db = SQLAlchemy(app)
class U(db.Model):
    __tablename__ = 'u'; id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20)); pw = db.Column(db.String(40))
with app.app_context():
    db.create_all(); db.session.execute(sa.delete(U)); db.session.commit()
    print('--- 开始业务代码 ---')
    for i in range(2): db.session.add(U(name='n%%d' %% i, pw='secret-hash')); db.session.commit()
    db.session.execute(sa.select(U).where(U.name == 'n0')).scalars().all(); db.session.execute(sa.select(U).where(U.name == 'n1')).scalars().all(); db.session.commit()
""" % URL
    d1 = mkapp('f96echo', {'run.py': 'pass'})
    rc, out = py(d1, CODE)
    if '--- 开始业务代码 ---' not in out: print('子进程失败:', rc, out[-600:]); raise SystemExit
    lines = [l for l in out.splitlines() if l.strip()]; st = lines.index('--- 开始业务代码 ---') + 1; lines = [re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+ ', '', l) for l in lines[st:]]
    for l in lines[:14]: print('   ', l[:150])
    print('    …(共', len(lines), '行)'); R['echo_lines'] = lines[:14]; R['n_lines'] = len(lines)
    print('  出现 "cached since" 的行数:', sum('cached since' in l for l in lines), '| 出现 "generated in" 的行数:', sum('generated in' in l for l in lines)); R['cache_marks'] = [sum('generated in' in l for l in lines), sum('cached since' in l for l in lines)]
    app, db, U = mk()
    print()
    print('== 二:DEBUG 级别还会把返回的行打出来')
    buf, h, lg = capture(logging.DEBUG)
    with app.app_context(): db.session.execute(sa.select(U.id, U.name).order_by(U.id)).all(); db.session.commit()
    stop(h, lg); lines = [l for l in buf.getvalue().splitlines() if l.strip()]; [print('   ', l[:140]) for l in lines if 'Row' in l or 'Col' in l or 'SELECT' in l][:5]; R['debug_rows'] = [l[:100] for l in lines if 'Row' in l][:3]
    print()
    print('== 三:参数里的敏感值:日志默认带参数,hide_parameters=True 可以隐藏')
    for label, kw in (('默认', {}), ('hide_parameters=True', {'SQLALCHEMY_ENGINE_OPTIONS': {'hide_parameters': True}})):
        app2, db2, U2 = mk(**kw); buf, h, lg = capture(logging.INFO)
        with app2.app_context(): db2.session.add(U2(name='alice', pw='hunter2-hash')); db2.session.commit()
        stop(h, lg); txt = buf.getvalue(); print(f'  {label:<22} 日志里能看到 "hunter2-hash":{"hunter2-hash" in txt}'); R.setdefault('hide', {})[label] = 'hunter2-hash' in txt
        print('   ', [l.strip()[:120] for l in txt.splitlines() if 'INSERT' not in l and l.strip()][:2])
    print()
    print('== 四:SQLALCHEMY_RECORD_QUERIES:每个请求(应用上下文)里每条语句的耗时')
    app3, db3, U3 = mk(SQLALCHEMY_RECORD_QUERIES=True)
    with app3.app_context():
        db3.session.execute(sa.text('select 1')); db3.session.execute(sa.text('select pg_sleep(0.2)')); db3.session.commit()
        for q in get_recorded_queries(): print(f'    {q.statement[:30]:<32} {q.duration * 1000:>7.1f} ms')
        R['recorded'] = [(q.statement[:30], q.duration * 1000) for q in get_recorded_queries()]
    print()
    print('== 五:自己用 SQLAlchemy 事件写慢查询日志(只记录超过 100 ms 的)')
    app4, db4, U4 = mk(); slow = []
    with app4.app_context():
        @event.listens_for(db4.engine, 'before_cursor_execute')
        def b(conn, cur, st, p, ctx, many): conn.info['t0'] = time.perf_counter()
        @event.listens_for(db4.engine, 'after_cursor_execute')
        def a(conn, cur, st, p, ctx, many):
            d = (time.perf_counter() - conn.info['t0']) * 1000
            if d > 100: slow.append((round(d), st[:40]))
        db4.session.execute(sa.text('select 1')); db4.session.execute(sa.text('select pg_sleep(0.15)')); db4.session.execute(sa.text('select 2')); db4.session.commit()
    print('  只记下了:', slow); R['slow'] = slow
    print()
    print('== 六:echo 的开销:1000 次简单查询,日志写到内存 vs 不开日志(5 次取中位数)')
    app5, db5, U5 = mk(); res = {}
    for label, lvl in (('不开日志', None), ('INFO(echo)', logging.INFO)):
        L = []
        for _ in range(5):
            if lvl: buf, h, lg = capture(lvl)
            with app5.app_context():
                t0 = time.perf_counter()
                for i in range(1000): db5.session.execute(sa.select(U5.id).where(U5.id == i)).all()
                db5.session.commit(); L.append(ms(t0))
            if lvl: stop(h, lg)
        res[label] = median(L); print(f'  {label:<12} {median(L):>7.1f} ms')
    R['overhead'] = res
finally:
    pg.stop()
save('f96', R)
