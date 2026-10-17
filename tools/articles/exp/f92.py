import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f92'); R = {}
import dj, threading
pg = dj.PG(9463, name='f92pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
APP = '''
import os, time
from flask import Flask, jsonify, request, stream_with_context, Response
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import event
app = Flask(__name__); app.logger.disabled = True
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_size": int(os.environ.get("PS", "2")), "max_overflow": 0, "pool_timeout": float(os.environ.get("PT", "1"))}
db = SQLAlchemy(app)
ev = []
with app.app_context():
    @event.listens_for(db.engine, "checkout")
    def co(dbapi, rec, proxy): ev.append("checkout")
    @event.listens_for(db.engine, "checkin")
    def ci(dbapi, rec): ev.append("checkin")
def out(): return db.engine.pool.checkedout()
@app.get("/steps")
def steps():
    log = [("开始", out())]
    db.session.execute(sa.text("select 1")); log.append(("执行 select 1", out()))
    db.session.commit(); log.append(("commit()", out()))
    db.session.execute(sa.text("select 1")); log.append(("再执行 select 1", out()))
    db.session.close(); log.append(("session.close()", out()))
    db.session.execute(sa.text("select 1")); log.append(("又执行 select 1(请求结束前)", out()))
    return jsonify(log)
@app.get("/out")
def outp(): return str(out())
@app.get("/leak")
def leak():
    c = db.engine.connect(); c.execute(sa.text("select 1")); return "leaked"
@app.get("/noleak")
def noleak():
    with db.engine.connect() as c: c.execute(sa.text("select 1"))
    return "ok"
@app.get("/hold")
def hold():
    db.session.execute(sa.text("select 1")); time.sleep(float(request.args["s"])); return "held"
@app.get("/release")
def release():
    db.session.execute(sa.text("select 1")); db.session.commit(); time.sleep(float(request.args["s"])); return "released"
@app.get("/stream")
def stream():
    db.session.execute(sa.text("select 1"))
    @stream_with_context
    def gen():
        for i in range(3): yield f"{i}\\n"; time.sleep(float(request.args["s"]))
    return Response(gen())
@app.get("/stream2")
def stream2():
    @stream_with_context
    def gen():
        db.session.execute(sa.text("select 1"))
        for i in range(3): yield f"{i}\\n"; time.sleep(float(request.args["s"]))
    return Response(gen())
@app.get("/events")
def events():
    ev.clear(); db.session.execute(sa.text("select 1")); db.session.commit(); db.session.execute(sa.text("select 2")); return jsonify(list(ev))
@app.get("/events-after")
def events_after(): return jsonify(list(ev))
'''
d = mkapp('f92', {'app.py': APP})
def Srv(**kw): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '16', 'app:app'], DB=URL, **kw)
try:
    print('== 一:一个请求里连接什么时候借出、什么时候归还(pool.checkedout())')
    with Srv(PS=5) as s:
        r = json.loads(s.get('/steps')[2]); [print(f'  {k:<28} 借出的连接数 = {v}') for k, v in r]; R['steps'] = r
        print('  请求结束之后(teardown)借出的连接数 =', s.get('/out')[2].decode()); R['after_req'] = s.get('/out')[2].decode()
        s.get('/events'); print('  池事件顺序(checkout / checkin):', json.loads(s.get('/events-after')[2])); R['events'] = json.loads(s.get('/events-after')[2])
    print()
    print('== 二:泄漏:视图里 db.engine.connect() 之后不关闭(pool_size=2, max_overflow=0, pool_timeout=1)')
    with Srv(PS=2) as s:
        codes = []
        for i in range(4): codes.append(s.get('/leak')[0])
        print('  连续 4 次请求 /leak 的状态码:', codes, '| 借出的连接数:', s.get('/out')[2].decode()); R['leak'] = [codes, s.get('/out')[2].decode()]
    with Srv(PS=2) as s:
        codes = [s.get('/noleak')[0] for _ in range(6)]; print('  用 with 管理的 /noleak 连续 6 次:', codes, '| 借出的连接数:', s.get('/out')[2].decode()); R['noleak'] = codes
    print()
    print('== 三:请求里做慢操作时还抓着连接:3 个并发请求,pool_size=2、pool_timeout=3,每个请求查一次然后睡 1 秒')
    for p in ('hold', 'release'):
        with Srv(PS=2, PT=3) as s:
            res = []; t0 = time.perf_counter()
            def one(): r = s.get(f'/{p}?s=1', timeout=20); res.append((r[0], r[3]))
            ths = [threading.Thread(target=one) for _ in range(3)]; [t.start() for t in ths]; [t.join() for t in ths]
            print(f'  /{p:<8} 3 个并发请求:各自耗时 {sorted(round(x[1]) for x in res)} ms,总耗时 {ms(t0):.0f} ms,状态码 {sorted(set(x[0] for x in res))}'); R.setdefault('slow', {})[p] = [sorted(round(x[1]) for x in res), ms(t0)]
    print()
    print('== 四:流式响应(stream_with_context):连接在什么时候占着?')
    with Srv(PS=5) as s:
        for path, label in (('/stream?s=0.6', '视图里先查询,再返回生成器'), ('/stream2?s=0.6', '生成器里(流式过程中)才查询')):
            th = threading.Thread(target=lambda: s.get(path, timeout=20)); th.start(); time.sleep(0.5)
            during = s.get('/out')[2].decode(); th.join(); time.sleep(0.2); after = s.get('/out')[2].decode()
            print(f'  {label}:流式响应进行中另一个请求看到的借出连接数 = {during},流结束后 = {after}'); R.setdefault('stream', {})[label] = [during, after]
finally:
    pg.stop()
save('f92', R)
