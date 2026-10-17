import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f83'); R = {}
import dj, threading
pg = dj.PG(9455, name='f83pg').start()
APP = '''
import os, time
from flask import Flask, jsonify, request, abort
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
app = Flask(__name__); app.logger.disabled = True
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]
db = SQLAlchemy(app)
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(30), unique=True); qty = db.Column(db.Integer, default=0)
with app.app_context(): db.drop_all(); db.create_all(); db.session.add(Item(name="seed", qty=10)); db.session.commit()
def txid(): return db.session.execute(sa.text("select txid_current()")).scalar()
@app.get("/two-commits")
def two():
    db.session.add(Item(name=request.args["n"] + "-1")); db.session.commit(); t1 = txid()
    db.session.add(Item(name=request.args["n"] + "-2")); db.session.commit(); t2 = txid()
    return jsonify(t1=t1, t2=t2)
@app.get("/no-commit")
def nocommit(): db.session.add(Item(name=request.args["n"])); return "ok"
@app.get("/commit-then-fail")
def ctf():
    db.session.add(Item(name=request.args["n"] + "-a")); db.session.commit()
    db.session.add(Item(name=request.args["n"] + "-b")); raise RuntimeError("boom")
@app.get("/atomic")
def atomic():
    n = request.args["n"]; db.session.add(Item(name=n + "-a")); db.session.add(Item(name="seed"))
    db.session.commit(); return "ok"
@app.get("/continue-after-error")
def cae():
    n = request.args["n"]; out = {}
    try: db.session.add(Item(name="seed")); db.session.flush()
    except IntegrityError: out["first"] = "IntegrityError"
    try: db.session.execute(sa.select(Item)).all(); out["second"] = "ok"
    except Exception as e: out["second"] = type(e).__name__
    db.session.rollback()
    out["after_rollback"] = len(db.session.execute(sa.select(Item)).all()) > 0
    return jsonify(out)
@app.get("/begin-twice")
def bt():
    db.session.execute(sa.select(Item)).all(); out = {}
    try: db.session.begin()
    except Exception as e: out["begin"] = f"{type(e).__name__}: {str(e)[:70]}"
    return jsonify(out)
@app.get("/savepoint")
def sp():
    n = request.args["n"]; db.session.add(Item(name=n + "-keep"))
    try:
        with db.session.begin_nested(): db.session.add(Item(name="seed"))
    except IntegrityError: pass
    db.session.commit(); return "ok"
@app.get("/hold")
def hold():
    db.session.execute(sa.update(Item).where(Item.name == "seed").values(qty=Item.qty + 1)); time.sleep(float(request.args["s"])); db.session.commit(); return "held"
@app.get("/touch")
def touch():
    db.session.execute(sa.update(Item).where(Item.name == "seed").values(qty=Item.qty + 1)); db.session.commit(); return "touched"
@app.get("/hold-readonly")
def hold_ro():
    db.session.execute(sa.select(Item)).all(); time.sleep(float(request.args["s"])); return "read"
if os.environ.get("AUTO") == "1":
    @app.after_request
    def finish(resp):
        if resp.status_code < 400: db.session.commit()
        else: db.session.rollback()
        return resp
    @app.get("/auto-ok")
    def auto_ok(): db.session.add(Item(name=request.args["n"])); return "ok"
    @app.get("/auto-400")
    def auto_400(): db.session.add(Item(name=request.args["n"])); abort(400)
    @app.get("/auto-500")
    def auto_500(): db.session.add(Item(name=request.args["n"])); raise RuntimeError("x")
'''
d = mkapp('f83', {'app.py': APP})
DB = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
def Srv(**kw): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '8', 'app:app'], DB=DB, **kw)
def names(): return pg.psql("select string_agg(name, ',' order by id) from item")
try:
    print('== 一:默认:视图里没 commit 就丢;每次 commit 是一个独立的事务')
    with Srv() as s:
        r = s.get('/two-commits?n=x'); j = json.loads(r[2]); print('  /two-commits 里两次 commit 后各自的 txid_current():', j, '→ 两个不同的事务' if j['t1'] != j['t2'] else '')
        R['two'] = j
        s.get('/no-commit?n=lost'); print('  /no-commit 只 add 不 commit,库里的行:', names()); R['nocommit'] = names()
    print()
    print('== 二:出错时哪些写入留下:commit 之后才出错的保留,commit 之前出错的丢失')
    with Srv() as s:
        r = s.get('/commit-then-fail?n=y'); print('  /commit-then-fail → HTTP', r[0], '| 库里的行:', names()); R['ctf'] = [r[0], names()]
    print()
    print('== 三:一次 commit 里同时写两行,第二行违反唯一约束:整个事务一起回滚(原子性)')
    with Srv() as s:
        r = s.get('/atomic?n=z'); print('  /atomic → HTTP', r[0], '| 库里有没有 z-a:', 'z-a' in (names() or '')); R['atomic'] = [r[0], 'z-a' in (names() or '')]
    print()
    print('== 四:出错之后继续用同一个 session:flush 出错后事务已失效,不 rollback 就继续查询会怎样')
    with Srv() as s:
        r = s.get('/continue-after-error?n=q'); print('  ', r[2].decode().strip()); R['cae'] = json.loads(r[2])
        r = s.get('/begin-twice'); print('  已经执行过查询(事务已自动开始)再调 db.session.begin():', r[2].decode().strip()); R['begin'] = json.loads(r[2])
        s.get('/savepoint?n=sp'); print('  begin_nested(保存点)里违反唯一约束:只回滚保存点,外层的 sp-keep 仍被提交:', 'sp-keep' in (names() or '')); R['savepoint'] = 'sp-keep' in (names() or '')
    print()
    print('== 五:事务边界与锁:A 请求更新一行后睡 1.5 秒才 commit,B 请求更新同一行要等多久?只读的长事务会不会挡住写?')
    with Srv() as s:
        res = {}
        def A(): res['A'] = s.get('/hold?s=1.5')[3]
        th = threading.Thread(target=A); th.start(); time.sleep(0.3); t0 = time.perf_counter(); s.get('/touch'); tb = ms(t0); th.join()
        print(f'  B 更新同一行:等了 {tb:.0f} ms(A 总共 {res["A"]:.0f} ms)'); R['lock'] = [tb, res['A']]
        th = threading.Thread(target=lambda: s.get('/hold-readonly?s=1.5')); th.start(); time.sleep(0.3); t0 = time.perf_counter(); s.get('/touch'); tr = ms(t0); th.join()
        print(f'  有请求在做只读查询后睡 1.5 秒(没 commit,连接 idle in transaction):B 更新只用了 {tr:.0f} ms'); R['ro'] = tr
    print()
    print('== 六:统一边界:after_request 里「状态码 < 400 就 commit,否则 rollback」')
    with Srv(AUTO='1') as s:
        for p in ('auto-ok', 'auto-400', 'auto-500'):
            r = s.get(f'/{p}?n={p}'); print(f'  /{p:<9} → HTTP {r[0]} | 是否留下 {p}:', p in (names() or '')); R.setdefault('auto', {})[p] = [r[0], p in (names() or '')]
finally:
    pg.stop()
save('f83', R)
