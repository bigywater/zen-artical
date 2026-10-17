import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f95'); R = {}
import dj, threading
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
pg = dj.PG(9466, name='f95pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
try:
    app = Flask('p'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = URL; app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 20}; db = SQLAlchemy(app)
    class Counter(db.Model):
        id = db.Column(db.Integer, primary_key=True); n = db.Column(db.Integer, default=0)
    class Job(db.Model):
        id = db.Column(db.Integer, primary_key=True); state = db.Column(db.String(10), default='new')
    sql = []
    with app.app_context():
        db.drop_all(); db.create_all(); db.session.add_all([Counter(id=1, n=0), Counter(id=2, n=0)] + [Job() for _ in range(9)]); db.session.commit(); ENGINE = db.engine
        event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append(' '.join(st.split())))
    def sess(): return orm.Session(ENGINE)
    print('== 一:with_for_update() 发出的 SQL')
    s = sess(); sql.clear(); s.execute(sa.select(Counter).where(Counter.id == 1).with_for_update()).scalar_one(); print('  ', sql[0].split('%')[0].strip(), '...', sql[0][sql[0].index('FOR'):]); R['sql'] = sql[0][sql[0].index('FOR'):]
    sql.clear(); s.rollback(); s.execute(sa.select(Counter).where(Counter.id == 1).with_for_update(read=True)).scalar_one(); print('  read=True →', sql[0][sql[0].index('FOR'):]); R['sql_read'] = sql[0][sql[0].index('FOR'):]
    sql.clear(); s.rollback(); s.execute(sa.select(Counter).where(Counter.id == 1).with_for_update(nowait=True)).scalar_one(); print('  nowait=True →', sql[0][sql[0].index('FOR'):]); s.rollback()
    sql.clear(); s.execute(sa.select(Counter).where(Counter.id == 1).with_for_update(skip_locked=True)).scalar_one(); print('  skip_locked=True →', sql[0][sql[0].index('FOR'):]); s.close()
    print()
    print('== 二:同样的 8 线程 × 20 次加 1:SELECT ... FOR UPDATE 之后读改写')
    def inc(stats):
        for _ in range(20):
            s = sess()
            try: o = s.execute(sa.select(Counter).where(Counter.id == 1).with_for_update()).scalar_one(); o.n += 1; time.sleep(0.001); s.commit()
            finally: s.close()
    pg.psql('update counter set n=0'); ths = [threading.Thread(target=inc, args=({},)) for _ in range(8)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; dt = ms(t0)
    print(f'  期望 160,最终 n = {pg.psql("select n from counter where id=1")},耗时 {dt:.0f} ms(没有重试,但线程在排队)'); R['inc'] = [int(pg.psql('select n from counter where id=1')), dt]
    print()
    print('== 三:别人持有锁时:默认阻塞;nowait 立即报错;skip_locked 跳过;lock_timeout 限时')
    holder = sess(); holder.execute(sa.select(Counter).where(Counter.id == 1).with_for_update()).scalar_one()
    def attempt(**kw):
        s = sess(); t0 = time.perf_counter()
        try:
            if kw.get('lock_timeout'): s.execute(sa.text(f"set lock_timeout = '{kw['lock_timeout']}'"))
            q = sa.select(Counter).where(Counter.id == 1).with_for_update(**{k: v for k, v in kw.items() if k != 'lock_timeout'}); r = s.execute(q).scalar_one_or_none(); out = '拿到了' if r else '返回空(被跳过)'
        except Exception as e: out = f'{type(e.orig).__name__ if hasattr(e, "orig") else type(e).__name__}'
        s.close(); return out, ms(t0)
    res = {}
    for label, kw in (('nowait=True', {'nowait': True}), ('skip_locked=True', {'skip_locked': True}), ("lock_timeout='500ms'", {'lock_timeout': '500ms'})):
        out, dt = attempt(**kw); print(f'  {label:<22} → {out},用时 {dt:.0f} ms'); res[label] = [out, dt]
    def release(): time.sleep(1.0); holder.commit()
    th = threading.Thread(target=release); th.start(); out, dt = attempt(); th.join(); print(f'  默认(阻塞等待)         → {out},用时 {dt:.0f} ms(等持有者 1 秒后 commit)'); res['默认'] = [out, dt]; R['wait'] = res; holder.close()
    print()
    print('== 四:任务队列:3 个 worker 同时取任务,skip_locked 让它们互不阻塞地拿到不同的行(9 个任务)')
    taken = {0: [], 1: [], 2: []}; barrier = threading.Barrier(3)
    def worker(i):
        s = sess(); barrier.wait()
        for _ in range(3):
            j = s.execute(sa.select(Job).where(Job.state == 'new').order_by(Job.id).limit(1).with_for_update(skip_locked=True)).scalar_one_or_none()
            if j is None: break
            taken[i].append(j.id); j.state = 'done'; time.sleep(0.05); s.commit()
        s.close()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(3)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]
    allids = sorted(sum(taken.values(), [])); print('  每个 worker 拿到的任务:', taken, '| 全部', allids, '| 有没有重复:', len(allids) != len(set(allids)), f'| {ms(t0):.0f} ms'); R['queue'] = [taken, len(allids) == len(set(allids)), len(allids)]
    print()
    print('== 五:死锁:两个事务以相反的顺序锁两行,PostgreSQL 检测到后让其中一个失败')
    def lock_two(first, second, out, key):
        s = sess()
        try:
            s.execute(sa.select(Counter).where(Counter.id == first).with_for_update()).scalar_one(); time.sleep(0.3)
            t0 = time.perf_counter(); s.execute(sa.select(Counter).where(Counter.id == second).with_for_update()).scalar_one(); s.commit(); out[key] = ('成功', ms(t0))
        except Exception as e: out[key] = (type(e.orig).__name__, ms(t0)); s.rollback()
        finally: s.close()
    out = {}; ts = [threading.Thread(target=lock_two, args=(1, 2, out, 'A')), threading.Thread(target=lock_two, args=(2, 1, out, 'B'))]; [t.start() for t in ts]; [t.join() for t in ts]
    print('  相反顺序:', {k: (v[0], f'{v[1]:.0f} ms') for k, v in out.items()}); R['deadlock'] = out
    out2 = {}; ts = [threading.Thread(target=lock_two, args=(1, 2, out2, 'A')), threading.Thread(target=lock_two, args=(1, 2, out2, 'B'))]; [t.start() for t in ts]; [t.join() for t in ts]
    print('  相同顺序(都先 1 后 2):', {k: (v[0]) for k, v in out2.items()}); R['no_deadlock'] = {k: v[0] for k, v in out2.items()}
finally:
    pg.stop()
save('f95', R)
