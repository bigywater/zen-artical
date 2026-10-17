import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f167'); R = {}
import dj, threading, http.client as hc
pg = dj.PG(9478, name='f167pg', conf={'max_connections': 20}).start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
APP = '''
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
app = Flask(__name__); app.logger.disabled = True
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_size": int(os.environ["PS"]), "max_overflow": int(os.environ.get("MO", "0")), "pool_timeout": float(os.environ.get("PT", "5"))}
db = SQLAlchemy(app)
@app.errorhandler(Exception)
def err(e): return jsonify(error=type(e).__name__, msg=str(getattr(e, "orig", e)).splitlines()[0][:80]), 503
@app.get("/q")
def q(): db.session.execute(sa.text("select pg_sleep(0.02)")); return "ok"
'''
d = mkapp('f167', {'app.py': APP})
def burst(port, path, total, conc):
    res = []; lock = threading.Lock(); idx = [0]
    def worker():
        while True:
            with lock:
                if idx[0] >= total: return
                idx[0] += 1
            c = hc.HTTPConnection('127.0.0.1', port, timeout=30); t0 = time.perf_counter(); c.request('GET', path); r = c.getresponse(); b = r.read(); res.append((r.status, ms(t0), b)); c.close()
    ths = [threading.Thread(target=worker) for _ in range(conc)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; return time.perf_counter() - t0, res
print('== 一:1 个 gunicorn worker × 32 线程,每个请求在数据库里 20 ms:连接池大小决定实际并发(300 个请求、32 并发)')
print(f'  {"pool_size":>9} {"请求/秒":>8} {"平均 ms":>8} {"p95 ms":>7}  理想上限(pool/0.02s)')
R['pool'] = {}
for ps in (1, 2, 5, 10, 20):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '32', 'app:app'], DB=URL, PS=ps, MO=0, PT=30) as s:
        time.sleep(1.0); burst(s.port, '/q', 40, 8); dt, res = burst(s.port, '/q', 300, 32); lat = sorted(x[1] for x in res)
    rps = 300 / dt; print(f'  {ps:>9} {rps:>8.0f} {sum(lat) / len(lat):>8.1f} {lat[int(len(lat) * 0.95)]:>7.0f}  {ps / 0.02:>8.0f}'); R['pool'][ps] = [rps, sum(lat) / len(lat), lat[int(len(lat) * 0.95)]]
print()
print('== 二:池太小 + 等待超时:pool_size=2、max_overflow=0、pool_timeout=0.5,32 并发的 20 ms 请求')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '32', 'app:app'], DB=URL, PS=2, MO=0, PT=0.5) as s:
    time.sleep(1.0); dt, res = burst(s.port, '/q', 300, 32); ok = sum(1 for x in res if x[0] == 200); errs = [x for x in res if x[0] != 200]; kinds = {}
    for x in errs: kinds[json.loads(x[2])['error']] = kinds.get(json.loads(x[2])['error'], 0) + 1
    print(f'  300 个请求:成功 {ok},失败 {len(errs)}({kinds})'); R['small_timeout'] = [ok, len(errs), kinds]
print()
print('== 三:池大小乘以进程数超过数据库的 max_connections(这里 PostgreSQL max_connections=20,保留 3 个给超级用户):4 个 worker × pool_size 10')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', '-k', 'gthread', '--threads', '16', 'app:app'], DB=URL, PS=10, MO=0, PT=3) as s:
    time.sleep(1.5); dt, res = burst(s.port, '/q', 400, 64); ok = sum(1 for x in res if x[0] == 200); errs = [x for x in res if x[0] != 200]; msgs = {}
    for x in errs: m = json.loads(x[2])['msg'][:70]; msgs[m] = msgs.get(m, 0) + 1
    conns = pg.psql("select count(*) from pg_stat_activity where datname='lab'"); print(f'  400 个请求:成功 {ok},失败 {len(errs)};失败原因:{msgs};此刻 PG 上的连接数 {conns}'); R['over'] = [ok, len(errs), msgs, conns]
pg.stop(); save('f167', R)
