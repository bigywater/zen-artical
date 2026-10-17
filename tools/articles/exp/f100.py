import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f100'); R = {}
import dj, threading
pg = dj.PG(9470, name='f100pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
APP = '''
import os, time
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError, DBAPIError
app = Flask(__name__); app.logger.disabled = True
opts = {"pool_size": 5, "max_overflow": 0}
if os.environ.get("PRE_PING") == "1": opts["pool_pre_ping"] = True
if os.environ.get("RECYCLE"): opts["pool_recycle"] = int(os.environ["RECYCLE"])
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]; app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts
db = SQLAlchemy(app)
@app.get("/q")
def q():
    db.session.execute(sa.text("select pg_sleep(float8 '0.2')")); return "ok"
@app.get("/q1")
def q1():
    db.session.execute(sa.text("select 1")); return "ok"
@app.get("/retry")
def retry():
    for attempt in (1, 2):
        try:
            db.session.execute(sa.text("select 1")); return f"ok after {attempt} attempt(s)"
        except DBAPIError as e:
            db.session.rollback()
            if attempt == 2 or not e.connection_invalidated: raise
@app.errorhandler(OperationalError)
def oe(e): return jsonify(error="db unavailable", invalidated=bool(e.connection_invalidated)), 503
@app.get("/pid")
def pid(): return str(db.session.execute(sa.text("select pg_backend_pid()")).scalar())
@app.get("/pool")
def pool(): return db.engine.pool.status()
'''
d = mkapp('f100', {'app.py': APP})
def Srv(**kw): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '8', 'app:app'], DB=URL, **kw)
def warm(s, n=5):
    ths = [threading.Thread(target=lambda: s.get('/q')) for _ in range(n)]; [t.start() for t in ths]; [t.join() for t in ths]
def restart_pg():
    subprocess.run([f'{dj.PGBIN}/pg_ctl', '-D', str(pg.dir), '-l', str(pg.dir / 'pg.log'), '-m', 'fast', '-w', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def stop_pg(): subprocess.run([f'{dj.PGBIN}/pg_ctl', '-D', str(pg.dir), '-m', 'fast', '-w', 'stop'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def start_pg(): subprocess.run([f'{dj.PGBIN}/pg_ctl', '-D', str(pg.dir), '-l', str(pg.dir / 'pg.log'), '-o', f'-p {pg.port} -k {pg.sock} -c listen_addresses=127.0.0.1 -c fsync=off', '-w', 'start'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    print('== 一:数据库重启之后,池里已有 5 个空闲连接都变成了坏连接:接着发 8 个串行请求,哪几个失败?')
    R['restart'] = {}
    for label, kw in (('默认(无 pre_ping)', {}), ('pool_pre_ping=True', {'PRE_PING': '1'})):
        with Srv(**kw) as s:
            warm(s); print(f'  [{label}] 重启前池状态:', s.get('/pool')[2].decode()); restart_pg(); codes = [s.get('/q1')[0] for _ in range(8)]
            print(f'  [{label}] 重启后 8 个串行请求的状态码:', codes, '| 失败个数', sum(c != 200 for c in codes)); R['restart'][label] = codes
            body = s.get('/q1')[2].decode()
    print()
    print('== 二:失败的那个请求返回了什么(默认配置)')
    with Srv() as s:
        warm(s); restart_pg(); r = s.get('/q1'); print('  第一个请求:HTTP', r[0], r[2].decode().strip()); R['first_fail'] = [r[0], r[2].decode().strip()]
    print()
    print('== 三:数据库停机期间与恢复:连不上的请求多快失败?恢复之后多快好?(pre_ping=True)')
    with Srv(PRE_PING='1') as s:
        warm(s); stop_pg(); t0 = time.perf_counter(); r = s.get('/q1'); dt = ms(t0); print(f'  数据库停机时:HTTP {r[0]} {r[2].decode().strip()},用时 {dt:.0f} ms'); R['down'] = [r[0], r[2].decode().strip(), dt]
        start_pg(); t_start = time.perf_counter(); n = 0
        while True:
            r = s.get('/q1'); n += 1
            if r[0] == 200 or n > 400: break
            time.sleep(0.05)
        print(f'  启动数据库之后,第 {n} 次请求就恢复了(自 pg_ctl start 返回起 {ms(t_start):.0f} ms),无需重启应用'); R['recover'] = [n, ms(t_start)]
    print()
    print('== 四:请求里自己重试一次(只在连接已失效时重试)')
    with Srv() as s:
        warm(s); restart_pg(); r = s.get('/retry'); print('  默认配置、数据库刚重启:', r[0], r[2].decode().strip()); R['retry'] = [r[0], r[2].decode().strip()]
    print()
    print('== 五:请求执行到一半连接被服务端杀掉(pg_terminate_backend):pre_ping 救不了')
    with Srv(PRE_PING='1') as s:
        warm(s, 1); res = {}
        def slow(): r = s.get('/q'); res['r'] = (r[0], r[2].decode().strip())
        th = threading.Thread(target=slow); th.start(); time.sleep(0.08); pg.psql("select pg_terminate_backend(pid) from pg_stat_activity where datname='lab' and query like '%pg_sleep%' and pid <> pg_backend_pid()"); th.join()
        print('  正在执行的请求:', res['r']); R['inflight'] = res['r']; print('  紧接着的下一个请求:', s.get('/q1')[0])
    print()
    print('== 六:pool_recycle:连接用了太久就换掉(设成 1 秒演示;看服务端后端进程号 pg_backend_pid 变不变)')
    R['recycle'] = {}
    for label, kw in (('没有 pool_recycle', {}), ('pool_recycle=1', {'RECYCLE': '1'})):
        with Srv(**kw) as s:
            p1 = s.get('/pid')[2].decode(); time.sleep(1.3); p2 = s.get('/pid')[2].decode(); print(f'  {label:<18} 第一次后端进程号 {p1},隔 1.3 秒再查 {p2} → {"换了新连接" if p1 != p2 else "还是同一个连接"}'); R['recycle'][label] = [p1, p2]
    print('  (recycle 只在借出连接时按年龄换掉旧连接,不会探测连接是否还活着——那是 pre_ping 的事)')
finally:
    stop_pg()
save('f100', R)
