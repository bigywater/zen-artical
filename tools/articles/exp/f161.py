import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f161'); R = {}
import dj, collections
from flask import Flask, g, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event
pg = dj.PG(9477, name='f161pg', conf={'shared_preload_libraries': 'pg_stat_statements', 'pg_stat_statements.track': 'all'}).start()
try:
    out = pg.psql('create extension if not exists pg_stat_statements'); print('  启用 pg_stat_statements:', out or 'ok')
    app = Flask('s'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; db = SQLAlchemy(app)
    class Order(db.Model):
        id = db.Column(db.Integer, primary_key=True); user_id = db.Column(db.Integer, index=True); note = db.Column(db.String(40)); amount = db.Column(db.Integer)
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(20))
    with app.app_context():
        db.create_all(); db.session.execute(sa.text("insert into \"user\" select g, 'u' || g from generate_series(1, 200) g")); db.session.execute(sa.text("insert into \"order\" (user_id, note, amount) select (g % 200) + 1, 'note' || g, g % 1000 from generate_series(1, 300000) g")); db.session.commit()
        db.session.execute(sa.text('analyze')); db.session.commit()
    STATS = collections.defaultdict(lambda: {'n': 0, 'total': 0.0, 'max': 0.0, 'eps': collections.Counter()})
    with app.app_context():
        eng = db.engine
        @event.listens_for(eng, 'before_cursor_execute')
        def b(conn, cur, st, params, ctx, many): conn.info['t0'] = time.perf_counter()
        @event.listens_for(eng, 'after_cursor_execute')
        def a(conn, cur, st, params, ctx, many):
            d = (time.perf_counter() - conn.info['t0']) * 1000; key = ' '.join(st.split())[:90]; s = STATS[key]; s['n'] += 1; s['total'] += d; s['max'] = max(s['max'], d); s['eps'][getattr(g, 'ep', '?') if sa.util.compat else '?'] += 1
    @app.before_request
    def tag(): g.ep = request.endpoint
    @app.get('/user/<int:uid>')
    def user(uid): return jsonify(name=db.session.get(User, uid).name)
    @app.get('/search')
    def search(): n = db.session.execute(sa.select(sa.func.count()).select_from(Order).where(Order.note.like('%9999%'))).scalar(); return jsonify(n=n)
    @app.get('/report/<int:uid>')
    def report(uid):
        tot = 0
        for oid in db.session.execute(sa.select(Order.id).where(Order.user_id == uid).limit(30)).scalars().all(): tot += db.session.execute(sa.select(Order.amount).where(Order.id == oid)).scalar()
        return jsonify(total=tot)
    c = app.test_client(); pg.psql('select pg_stat_statements_reset()')
    for i in range(40): c.get(f'/user/{i + 1}')
    for i in range(5): c.get('/search')
    for i in range(20): c.get(f'/report/{i + 1}')
    print('== 一:应用侧统计:按「去掉参数的语句」聚合,按总耗时排序的前 5(40 次 /user、5 次 /search、20 次 /report)')
    rows = sorted(STATS.items(), key=lambda kv: -kv[1]['total'])[:5]; R['app'] = []
    print(f'  {"次数":>5} {"总耗时 ms":>10} {"平均 ms":>9} {"最大 ms":>9}  语句(截断)  | 来自哪个端点')
    for k, v in rows: print(f'  {v["n"]:>5} {v["total"]:>10.1f} {v["total"] / v["n"]:>9.2f} {v["max"]:>9.1f}  {k[:60]:<60} | {dict(v["eps"])}'); R['app'].append([k[:60], v['n'], v['total'], v['max']])
    print()
    print('== 二:按调用次数排序的前 3:次数多的语句(N+1 的特征)')
    for k, v in sorted(STATS.items(), key=lambda kv: -kv[1]['n'])[:3]: print(f'  {v["n"]:>5} 次 总 {v["total"]:>8.1f} ms 平均 {v["total"] / v["n"]:.2f} ms  {k[:70]}'); R.setdefault('by_count', []).append([k[:70], v['n'], v['total']])
    print()
    print('== 三:服务端统计:pg_stat_statements,按总耗时排序的前 5')
    q = "select calls, round(total_exec_time::numeric, 1) as total, round(mean_exec_time::numeric, 3) as mean, round(max_exec_time::numeric, 1) as max, left(regexp_replace(query, '\\s+', ' ', 'g'), 70) from pg_stat_statements where query not like '%pg_stat_statements%' and dbid = (select oid from pg_database where datname = 'lab') order by total_exec_time desc limit 5"
    res = pg.psql(q); print('  calls | total ms | mean ms | max ms | 语句'); [print('  ' + l) for l in res.splitlines()]; R['pgss'] = res.splitlines()
    print('  (pg_stat_statements 把参数规整成 $1、$2,看的是数据库内部的执行时间,不含网络与 Python 的耗时;应用侧统计含这两部分)')
finally:
    pg.stop()
save('f161', R)
