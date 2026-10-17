import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f94'); R = {}
import dj, threading
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event, orm
from sqlalchemy.orm.exc import StaleDataError
pg = dj.PG(9465, name='f94pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
try:
    app = Flask('o'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = URL; app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 20}; db = SQLAlchemy(app)
    class Plain(db.Model):
        id = db.Column(db.Integer, primary_key=True); n = db.Column(db.Integer, default=0)
    class Versioned(db.Model):
        id = db.Column(db.Integer, primary_key=True); n = db.Column(db.Integer, default=0); ver = db.Column(db.Integer, nullable=False)
        __mapper_args__ = {'version_id_col': ver}
    sql = []
    with app.app_context():
        db.drop_all(); db.create_all(); db.session.add_all([Plain(id=1, n=0), Versioned(id=1, n=0)]); db.session.commit(); event.listen(db.engine, 'before_cursor_execute', lambda c, cur, st, p, ctx, m: sql.append((' '.join(st.split()), p)))
    with app.app_context(): ENGINE = db.engine
    def sess(): return orm.Session(ENGINE)
    print('== 一:丢失更新:两个会话都读到 n=0,各自加 10 再提交(没有任何锁)')
    with app.app_context():
        s1, s2 = sess(), sess(); a = s1.get(Plain, 1); b = s2.get(Plain, 1); a.n += 10; b.n += 10; s1.commit(); s2.commit(); s1.close(); s2.close()
        print('  期望 n = 20,实际库里 n =', pg.psql('select n from plain where id=1')); R['lost'] = pg.psql('select n from plain where id=1')
        sql.clear(); s = sess(); x = s.get(Plain, 1); x.n = 5; s.commit(); print('  ORM 发出的 UPDATE:', [q[0] for q in sql if q[0].startswith('UPDATE')][0]); s.close()
    print()
    print('== 二:version_id_col:UPDATE 带上版本号,没更新到行就报错')
    with app.app_context():
        s1, s2 = sess(), sess(); a = s1.get(Versioned, 1); b = s2.get(Versioned, 1); print('  两个会话读到的版本号:', a.ver, b.ver); a.n += 10; b.n += 10
        sql.clear(); s1.commit(); upd = [q for q in sql if q[0].startswith('UPDATE')][0]; print('  先提交的会话发出的 UPDATE:', upd[0]); R['upd'] = upd[0]
        try: s2.commit(); r_ = '成功'
        except StaleDataError as e: r_ = f'StaleDataError: {str(e)[:120]}'; s2.rollback()
        print('  后提交的会话 →', r_); R['stale'] = r_
        print('  库里 n =', pg.psql('select n from versioned where id=1'), '| ver =', pg.psql('select ver from versioned where id=1')); R['after'] = [pg.psql('select n from versioned where id=1'), pg.psql('select ver from versioned where id=1')]
        s1.close(); s2.close()
    print()
    print('== 三:8 个线程各给同一行加 1,共 20 次:没有锁 vs 乐观锁 + 重试')
    def worker(model, retries, stats):
        for _ in range(20):
            while True:
                s = sess()
                try:
                    o = s.get(model, 1); o.n += 1; time.sleep(0.001); s.commit(); break
                except StaleDataError:
                    s.rollback(); stats['retries'] += 1
                    if not retries: break
                finally: s.close()
    for label, model, retries in (('没有锁(Plain)', Plain, False), ('乐观锁,冲突就放弃(Versioned)', Versioned, False), ('乐观锁 + 重试(Versioned)', Versioned, True)):
        pg.psql(f"update {model.__tablename__} set n=0" + (", ver=1" if model is Versioned else ''))
        stats = {'retries': 0}; ths = [threading.Thread(target=worker, args=(model, retries, stats)) for _ in range(8)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; dt = ms(t0)
        print(f'  {label:<32} 期望 160,最终 n = {pg.psql(f"select n from {model.__tablename__} where id=1"):>3} | 冲突/重试 {stats["retries"]:>3} 次 | {dt:.0f} ms'); R.setdefault('conc', {})[label] = [int(pg.psql(f"select n from {model.__tablename__} where id=1")), stats['retries'], dt]
    print()
    print('== 四:HTTP API 里的乐观锁:ETag + If-Match,版本不符返回 412')
    @app.get('/v/<int:i>')
    def get_v(i):
        o = db.session.get(Versioned, i); r = jsonify(n=o.n); r.headers['ETag'] = f'"{o.ver}"'; return r
    @app.put('/v/<int:i>')
    def put_v(i):
        o = db.session.get(Versioned, i); want = request.headers.get('If-Match', '').strip('"')
        if want != str(o.ver): return jsonify(error='版本已变化'), 412
        o.n = request.json['n']
        try: db.session.commit()
        except StaleDataError: db.session.rollback(); return jsonify(error='并发冲突'), 409
        return jsonify(ok=True)
    c = app.test_client(); pg.psql('update versioned set n=0, ver=1'); r = c.get('/v/1'); et = r.headers['ETag']; print('  GET → ETag:', et)
    r1 = c.put('/v/1', json={'n': 1}, headers={'If-Match': et}); print('  第一个客户端带 If-Match 更新 →', r1.status_code); r2 = c.put('/v/1', json={'n': 2}, headers={'If-Match': et}); print('  第二个客户端用同一个旧 ETag 更新 →', r2.status_code, r2.get_json()); R['http'] = [r1.status_code, r2.status_code]
    print('  重新 GET 得到的新 ETag:', c.get('/v/1').headers['ETag'])
finally:
    pg.stop()
save('f94', R)
