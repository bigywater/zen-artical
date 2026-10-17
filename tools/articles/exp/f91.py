import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f91'); R = {}
import dj, threading
import sqlalchemy as sa
from sqlalchemy.pool import NullPool
pg = dj.PG(9462, name='f91pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
def nconn(): return int(pg.psql("select count(*) from pg_stat_activity where datname='lab' and backend_type='client backend' and pid <> pg_backend_pid()"))
try:
    print('== 一:默认配置的连接池')
    e = sa.create_engine(URL); print('  类型:', type(e.pool).__name__, '| pool_size =', e.pool.size(), '| max_overflow =', e.pool._max_overflow, '| timeout =', e.pool._timeout, '| recycle =', e.pool._recycle, '| pre_ping =', e.pool._pre_ping); R['default'] = [type(e.pool).__name__, e.pool.size(), e.pool._max_overflow, e.pool._timeout, e.pool._recycle, e.pool._pre_ping]
    print('  刚创建:', e.pool.status(), '| PG 连接数', nconn())
    c1 = e.connect(); c2 = e.connect(); c1.execute(sa.text('select 1')); c2.execute(sa.text('select 1')); print('  借出 2 个连接:', e.pool.status(), '| PG 连接数', nconn())
    c1.close(); print('  归还 1 个:', e.pool.status(), '| PG 连接数', nconn()); R['status'] = [e.pool.status(), nconn()]
    c2.close(); e.dispose(); print('  engine.dispose() 之后 PG 连接数', nconn())
    print()
    print('== 二:连接池耗尽:pool_size=2, max_overflow=1, pool_timeout=1 秒,同时借 4 个')
    e = sa.create_engine(URL, pool_size=2, max_overflow=1, pool_timeout=1); cs = [e.connect() for _ in range(3)]; [c.execute(sa.text('select 1')) for c in cs]
    print('  借 3 个(2 + 1 溢出):', e.pool.status(), '| PG 连接数', nconn())
    t0 = time.perf_counter()
    try: e.connect()
    except Exception as ex: print(f'  借第 4 个 → 等了 {ms(t0):.0f} ms 后 {type(ex).__name__}: {str(ex)[:95]}'); R['exhaust'] = [ms(t0), type(ex).__name__, str(ex)[:95]]
    cs[2].close(); n1 = nconn(); print('  归还 1 个连接后 PG 连接数:', n1, '(池里还有空位,这个连接被留在池里,没有关闭)')
    cs[1].close(); n2 = nconn(); print('  再归还 1 个后:', n2, '| 池状态:', e.pool.status())
    cs[0].close(); n3 = nconn(); print(f'  三个都归还后:{n3}(池只保留 pool_size={2} 个,多出的那个溢出连接被真正关闭) | 池状态:', e.pool.status()); R['overflow_closed'] = [n1, n2, n3]
    e.dispose()
    print()
    print('== 三:连接被服务端断开后:没有 pre_ping 与有 pre_ping')
    for label, kw in (('默认(无 pre_ping)', {}), ('pool_pre_ping=True', {'pool_pre_ping': True})):
        e = sa.create_engine(URL, **kw)
        with e.connect() as c: c.execute(sa.text('select 1'))
        pg.psql("select pg_terminate_backend(pid) from pg_stat_activity where datname='lab' and pid <> pg_backend_pid()"); time.sleep(0.3)
        try:
            with e.connect() as c: c.execute(sa.text('select 1')); r_ = '成功(池发现连接坏了,换了一个新的)'
        except Exception as ex: r_ = f'{type(ex).__name__}: {str(ex.orig)[:60]}'
        print(f'  {label:<20} 服务端杀掉空闲连接后下一次查询 → {r_}'); R.setdefault('preping', {})[label] = r_
        if not kw:
            try:
                with e.connect() as c: c.execute(sa.text('select 1')); r2 = '成功'
            except Exception as ex: r2 = type(ex).__name__
            print('    (没有 pre_ping 时,失败那次之后坏连接被丢弃,再查一次 →', r2 + ')'); R['after_fail'] = r2
        e.dispose()
    print()
    print('== 四:每次新建连接 vs 从池里取:NullPool(不池化)与 QueuePool 的单次 "借连接 + select 1" 耗时(200 次中位数)')
    for label, kw in (('QueuePool', {}), ('NullPool', {'poolclass': NullPool})):
        e = sa.create_engine(URL, **kw); L = []
        for _ in range(200):
            t0 = time.perf_counter()
            with e.connect() as c: c.execute(sa.text('select 1'))
            L.append(ms(t0))
        print(f'  {label:<10} 中位数 {median(L):.2f} ms'); R.setdefault('conn_cost', {})[label] = median(L); e.dispose()
    print()
    print('== 五:gunicorn 多个 worker:每个 worker 进程有自己的连接池,PG 上的连接数是各池之和')
    APP = """
import os, time
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
app = Flask(__name__); app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DB']
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 3, 'max_overflow': 2}
db = SQLAlchemy(app)
@app.get('/q')
def q():
    db.session.execute(sa.text('select pg_sleep(0.5)')); return 'ok'
@app.get('/pool')
def pool(): return db.engine.pool.status()
"""
    d = mkapp('f91', {'app.py': APP})
    for workers, threads in ((1, 16), (3, 16)):
        with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--workers', str(workers), '--threads', str(threads), 'app:app'], DB=URL) as s:
            time.sleep(0.5); mx = [0]; stop = threading.Event()
            def mon():
                while not stop.is_set(): mx[0] = max(mx[0], nconn()); time.sleep(0.05)
            m = threading.Thread(target=mon); m.start()
            res = []; ths = [threading.Thread(target=lambda: res.append(s.get('/q', timeout=60)[0])) for _ in range(40)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0; stop.set(); m.join()
            print(f'  {workers} 个 worker × {threads} 线程,40 个并发请求(每个查询 0.5 秒):PG 上最多同时有 {mx[0]} 个连接(每个池上限 3 + 2 = 5,{workers} 个池最多 {workers * 5}),总耗时 {dt:.1f} 秒,状态码 {sorted(set(res))}'); R.setdefault('workers', {})[workers] = [mx[0], dt, sorted(set(res))]
finally:
    pg.stop()
save('f91', R)
