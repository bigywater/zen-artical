import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import dj, threading, socket as sk, json as _j
tee('f188'); R = {}
pg = dj.PG(9480, name='f188pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
hang = sk.socket(); hang.bind(('127.0.0.1', 0)); hang.listen(16); hport = hang.getsockname()[1]; conns = []
threading.Thread(target=lambda: [conns.append(hang.accept()) for _ in range(50)], daemon=True).start()
HURL = f'postgresql+psycopg://lab@127.0.0.1:{hport}/lab'
APP = '''
import os, time
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
app = Flask(__name__); app.logger.disabled = True
URL = os.environ["DB"]
app.config["SQLALCHEMY_DATABASE_URI"] = URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_size": 2, "max_overflow": 0, "pool_timeout": 3, "pool_pre_ping": True}
db = SQLAlchemy(app)
health_engine = sa.create_engine(URL, pool_size=1, max_overflow=0, pool_timeout=1, pool_pre_ping=True, connect_args={"connect_timeout": 1, "options": "-c statement_timeout=500"})
def resp(fn):
    t0 = time.perf_counter()
    try: fn(); st, body = 200, "ready"
    except Exception as e: st, body = 503, type(e).__name__
    return jsonify(status=body, ms=round((time.perf_counter() - t0) * 1000)), st
@app.get("/slow")
def slow(): db.session.execute(sa.text("select pg_sleep(3)")); return "slow done"
@app.get("/ready-shared")
def ready_shared(): return resp(lambda: db.session.execute(sa.text("select 1")))
@app.get("/ready-own")
def ready_own():
    def f():
        with health_engine.connect() as c: c.execute(sa.text("select 1"))
    return resp(f)
def probe(url, **ca):
    e = sa.create_engine(url, poolclass=sa.pool.NullPool, connect_args=ca)
    with e.connect() as c: c.execute(sa.text("select 1"))
@app.get("/hang-nolimit")
def hang_nolimit(): return resp(lambda: probe(os.environ["HDB"]))
@app.get("/hang-limit")
def hang_limit(): return resp(lambda: probe(os.environ["HDB"], connect_timeout=1))
@app.get("/slowq-nolimit")
def slowq_nolimit():
    def f():
        e = sa.create_engine(URL, poolclass=sa.pool.NullPool)
        with e.connect() as c: c.execute(sa.text("select pg_sleep(3)"))
    return resp(f)
@app.get("/slowq-limit")
def slowq_limit():
    def f():
        e = sa.create_engine(URL, poolclass=sa.pool.NullPool, connect_args={"options": "-c statement_timeout=500"})
        with e.connect() as c: c.execute(sa.text("select pg_sleep(3)"))
    return resp(f)
'''
d = mkapp('f188', {'app.py': APP})
def Srv(): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '8', 'app:app'], DB=URL, HDB=HURL)
def j(r): x = _j.loads(r[2]); return x['status'], x['ms'], r[0]
def stop_pg(): subprocess.run([f'{dj.PGBIN}/pg_ctl', '-D', str(pg.dir), '-m', 'fast', '-w', 'stop'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def start_pg(): subprocess.run([f'{dj.PGBIN}/pg_ctl', '-D', str(pg.dir), '-l', str(pg.dir / 'pg.log'), '-o', f'-p {pg.port} -k {pg.sock} -c listen_addresses=127.0.0.1 -c fsync=off', '-w', 'start'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    with Srv() as s:
        print('== 一:最简单的数据库就绪检查(select 1):数据库正常 / 停掉 / 再启动')
        R['basic'] = {}
        a = j(s.get('/ready-shared')); print(f'  数据库正常:{a[2]} {a[0]}({a[1]} ms)'); R['basic']['up'] = a
        stop_pg(); b = j(s.get('/ready-shared')); print(f'  数据库停掉:{b[2]} {b[0]}({b[1]} ms)'); R['basic']['down'] = b
        start_pg(); time.sleep(0.5); c = j(s.get('/ready-shared')); print(f'  数据库重新启动后:{c[2]} {c[0]}({c[1]} ms)'); R['basic']['back'] = c
        print()
        print('== 二:连接池被慢请求占满(池 2 个连接,pool_timeout=3 秒,2 个 3 秒的 /slow 正在跑),数据库本身其实很健康')
        R['pool'] = {}
        ths = [threading.Thread(target=lambda: s.get('/slow', timeout=10)) for _ in range(2)]; [t.start() for t in ths]; time.sleep(0.5)
        for label, path in (('就绪检查走业务连接池(/ready-shared)', '/ready-shared'), ('就绪检查用独立的 1 连接小池(/ready-own)', '/ready-own')):
            r = j(s.get(path, timeout=10)); print(f'  {label}:HTTP {r[2]} {r[0]},{r[1]} ms'); R['pool'][label] = r
        [t.join() for t in ths]
        print()
        print('== 三:数据库「卡住」:连接建不起来(端口接受连接但不回应)与查询很慢(pg_sleep 3 秒)')
        R['hang'] = {}
        for label, path in (('连不上,不设 connect_timeout', '/hang-nolimit'), ('连不上,connect_timeout=1', '/hang-limit'), ('查询很慢,不设 statement_timeout', '/slowq-nolimit'), ('查询很慢,statement_timeout=500ms', '/slowq-limit')):
            try: r = j(s.get(path, timeout=6)); out = f'HTTP {r[2]} {r[0]},{r[1]} ms'; R['hang'][label] = r
            except Exception as e: out = f'探针客户端 6 秒后放弃({type(e).__name__})'; R['hang'][label] = [None, None, type(e).__name__]
            print(f'  {label:<30}→ {out}')
    save('f188', R)
finally:
    pg.stop()
