import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f107'); R = {}
import dj, threading, http.client as hc
pg = dj.PG(9472, name='f107pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
APP = '''
import os, time, json, hashlib
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
app = Flask(__name__); app.logger.disabled = True; app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]; app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_size": 20}
db = SQLAlchemy(app)
with app.app_context():
    db.session.execute(sa.text("drop table if exists orders, idem")); 
    db.session.execute(sa.text("create table orders (id serial primary key, item text)"))
    db.session.execute(sa.text("create table idem (key text primary key, fp text, status int, body text, state text)")); db.session.commit()
SLOW = float(os.environ.get("SLOW", "0"))
def create_order(item):
    time.sleep(SLOW); oid = db.session.execute(sa.text("insert into orders (item) values (:i) returning id"), {"i": item}).scalar(); return oid
@app.post("/orders")
def plain():
    oid = create_order(request.json["item"]); db.session.commit(); return jsonify(id=oid), 201
@app.post("/orders-naive")
def naive():
    key = request.headers["Idempotency-Key"]; row = db.session.execute(sa.text("select status, body from idem where key=:k"), {"k": key}).first(); db.session.commit()
    if row: r = jsonify(json.loads(row.body)); r.status_code = row.status; r.headers["Idempotent-Replayed"] = "true"; return r
    oid = create_order(request.json["item"]); body = json.dumps({"id": oid})
    db.session.execute(sa.text("insert into idem (key, fp, status, body, state) values (:k, '', 201, :b, 'done') on conflict (key) do update set body = excluded.body"), {"k": key, "b": body}); db.session.commit(); return jsonify(id=oid), 201
@app.post("/orders-idem")
def idem():
    key = request.headers.get("Idempotency-Key")
    if not key: return jsonify(error="Idempotency-Key required"), 400
    fp = hashlib.sha256(json.dumps(request.json, sort_keys=True).encode()).hexdigest()
    got = db.session.execute(sa.text("insert into idem (key, fp, state) values (:k, :f, 'processing') on conflict (key) do nothing returning key"), {"k": key, "f": fp}).first(); db.session.commit()
    if not got:
        row = db.session.execute(sa.text("select fp, status, body, state from idem where key=:k"), {"k": key}).first(); db.session.commit()
        if row.fp != fp: return jsonify(error="Idempotency-Key reused with a different request body"), 422
        if row.state == "processing": return jsonify(error="request in progress"), 409
        r = jsonify(json.loads(row.body)); r.status_code = row.status; r.headers["Idempotent-Replayed"] = "true"; return r
    try:
        oid = create_order(request.json["item"]); body = json.dumps({"id": oid})
        db.session.execute(sa.text("update idem set status=201, body=:b, state='done' where key=:k"), {"b": body, "k": key}); db.session.commit(); return jsonify(id=oid), 201
    except Exception:
        db.session.rollback(); db.session.execute(sa.text("delete from idem where key=:k"), {"k": key}); db.session.commit(); raise
@app.get("/count")
def count(): return str(db.session.execute(sa.text("select count(*) from orders")).scalar())
'''
d = mkapp('f107', {'app.py': APP})
def post(port, path, body, headers=None, timeout=10):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=timeout); h = {'Content-Type': 'application/json', **(headers or {})}; t0 = time.perf_counter()
    try: c.request('POST', path, body=json.dumps(body), headers=h); r = c.getresponse(); b = r.read().decode(); return r.status, b.strip(), dict(r.getheaders()), ms(t0)
    except Exception as e: return type(e).__name__, '', {}, ms(t0)
    finally: c.close()
def Srv(**kw): return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '16', 'app:app'], DB=URL, **kw)
try:
    print('== 一:没有幂等键:客户端 0.3 秒超时后重试,而服务端处理要 1 秒')
    with Srv(SLOW=1.0) as s:
        r1 = post(s.port, '/orders', {'item': 'book'}, timeout=0.3); print('  第一次请求:客户端超时 →', r1[0]); r2 = post(s.port, '/orders', {'item': 'book'}, timeout=5); print('  重试:', r2[0], r2[1]); time.sleep(1.2)
        n = s.get('/count')[2].decode(); print('  结果:库里有', n, '个订单(用户只下了一单)'); R['plain'] = int(n)
    print()
    print('== 二:带 Idempotency-Key,顺序重试:第二次直接返回第一次的结果')
    with Srv(SLOW=0.2) as s:
        k = {'Idempotency-Key': 'k-001'}; a = post(s.port, '/orders-idem', {'item': 'book'}, k); b = post(s.port, '/orders-idem', {'item': 'book'}, k)
        print('  第一次:', a[0], a[1], '| 耗时', f'{a[3]:.0f} ms'); print('  第二次:', b[0], b[1], '| Idempotent-Replayed =', b[2].get('Idempotent-Replayed'), f'| 耗时 {b[3]:.0f} ms'); R['seq'] = [a[0], a[1], b[0], b[1], b[2].get('Idempotent-Replayed'), a[3], b[3]]
        print('  库里订单数:', s.get('/count')[2].decode()); R['seq_count'] = s.get('/count')[2].decode()
        c_ = post(s.port, '/orders-idem', {'item': 'pen'}, k); print('  同一个 key 换了请求体 →', c_[0], c_[1]); R['mismatch'] = [c_[0], c_[1]]
        e_ = post(s.port, '/orders-idem', {'item': 'x'}); print('  不带 key →', e_[0], e_[1]); R['nokey'] = e_[0]
    print()
    print('== 三:并发的重复请求(同一个 key 同时发 6 个):「先查再写」的朴素实现 vs 先占位的原子实现')
    for label, path in (('朴素:先查,没有再写', '/orders-naive'), ('原子:先 INSERT key 占位', '/orders-idem')):
        with Srv(SLOW=0.5) as s:
            res = []; ths = [threading.Thread(target=lambda: res.append(post(s.port, path, {'item': 'book'}, {'Idempotency-Key': 'race-1'}, timeout=10))) for _ in range(6)]; [t.start() for t in ths]; [t.join() for t in ths]
            from collections import Counter; cnt = Counter(r[0] for r in res); n = s.get('/count')[2].decode(); print(f'  {label:<24} 状态码分布 {dict(cnt)} | 库里订单数 {n}'); R.setdefault('race', {})[label] = [dict(cnt), int(n)]
finally:
    pg.stop()
save('f107', R)
