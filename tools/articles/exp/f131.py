import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f131'); R = {}
import dj, threading, statistics
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from werkzeug.security import generate_password_hash, check_password_hash
pg = dj.PG(9475, name='f131pg').start()
try:
    app = Flask('l'); app.logger.disabled = True; app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'; app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 30}; db = SQLAlchemy(app)
    MAX, LOCK = 5, 2.0
    with app.app_context():
        db.session.execute(sa.text('create table acct (name text primary key, pw text, fails int default 0, locked_until double precision default 0)'))
        for n in ('ann', 'bob'): db.session.execute(sa.text('insert into acct (name, pw) values (:n, :p)'), {'n': n, 'p': generate_password_hash('pw-' + n, method='pbkdf2:sha256:600000')})
        db.session.commit()
    DUMMY = generate_password_hash('dummy', method='pbkdf2:sha256:600000')
    def row(n): return db.session.execute(sa.text('select name, pw, fails, locked_until from acct where name=:n'), {'n': n}).first()
    @app.post('/login')
    def login():
        j = request.get_json(); r = row(j['username']); now = time.time()
        if r and r.locked_until > now: return jsonify(error='invalid credentials or account temporarily locked'), 401
        ok = check_password_hash(r.pw if r else DUMMY, j['password']) and r is not None
        if ok:
            db.session.execute(sa.text('update acct set fails=0, locked_until=0 where name=:n'), {'n': j['username']}); db.session.commit(); return jsonify(ok=True)
        if r:
            db.session.execute(sa.text('update acct set fails = fails + 1, locked_until = case when fails + 1 >= :m then :t else locked_until end where name=:n'), {'n': j['username'], 'm': MAX, 't': now + LOCK}); db.session.commit()
        return jsonify(error='invalid credentials or account temporarily locked'), 401
    @app.post('/login-naive')
    def naive():
        j = request.get_json(); r = row(j['username'])
        if r is None: return jsonify(error='user not found'), 404
        if not check_password_hash(r.pw, j['password']): return jsonify(error='wrong password'), 401
        return jsonify(ok=True)
    @app.post('/login-race')
    def race():
        j = request.get_json(); r = row(j['username'])
        if r.fails >= MAX: return jsonify(error='locked'), 423
        ok = check_password_hash(r.pw, j['password'])
        if not ok: db.session.execute(sa.text('update acct set fails=:f where name=:n'), {'n': j['username'], 'f': r.fails + 1}); db.session.commit()
        return jsonify(ok=ok), (200 if ok else 401)
    @app.post('/login-atomic')
    def atomic():
        j = request.get_json()
        n = db.session.execute(sa.text('update acct set fails = fails + 1 where name=:n and fails < :m returning fails'), {'n': j['username'], 'm': MAX}).first(); db.session.commit()
        if n is None: return jsonify(error='locked'), 423
        r = row(j['username']); ok = check_password_hash(r.pw, j['password'])
        if ok: db.session.execute(sa.text('update acct set fails=0 where name=:n'), {'n': j['username']}); db.session.commit()
        return jsonify(ok=ok), (200 if ok else 401)
    c = app.test_client()
    def post(path, u, p): return c.post(path, json={'username': u, 'password': p})
    print(f'== 一:连续失败 {MAX} 次后锁定 {LOCK:.0f} 秒(演示用),锁定期间连正确的密码也被拒,到期后恢复,成功登录清零计数')
    seq = [post('/login', 'ann', 'bad').status_code for _ in range(MAX)]; print(f'  连续 {MAX} 次错误密码:', seq)
    r = post('/login', 'ann', 'pw-ann'); print('  锁定期间用正确的密码 →', r.status_code, r.get_json()); R['locked'] = [seq, r.status_code, r.get_json()]
    time.sleep(LOCK + 0.2); r = post('/login', 'ann', 'pw-ann'); print(f'  {LOCK:.0f} 秒后用正确的密码 →', r.status_code, r.get_json()); R['unlocked'] = r.status_code
    with app.app_context(): print('  成功之后库里的失败计数:', row('ann').fails); R['reset'] = row('ann').fails
    post('/login', 'bob', 'bad'); post('/login', 'bob', 'bad'); post('/login', 'bob', 'pw-bob')
    with app.app_context(): print('  bob 失败 2 次后成功登录一次,计数:', row('bob').fails, '(中途成功会清零)')
    print()
    print('== 二:响应是否泄漏「用户名存不存在」:朴素实现 vs 统一的响应')
    R['enum'] = {}
    for label, path in (('朴素:不存在 404 / 密码错 401,消息不同', '/login-naive'), ('统一:都是 401 与同一句话', '/login')):
        a = post(path, 'nobody', 'x'); b = post(path, 'bob', 'x'); print(f'  {label}'); print(f'     不存在的用户 → {a.status_code} {a.get_json()}'); print(f'     存在的用户、错误密码 → {b.status_code} {b.get_json()}'); R['enum'][label] = [[a.status_code, a.get_json()], [b.status_code, b.get_json()]]
    print()
    print('== 三:时间差也会泄漏:不存在的用户不做哈希(快)与存在的用户做哈希(慢);统一实现对不存在的用户也算一次哈希(各 10 次中位数)')
    def med(path, u, n=10): L = []; [post(path, u, 'x') for _ in range(2)]; [(lambda t0: (post(path, u, 'x'), L.append(ms(t0))))(time.perf_counter()) for _ in range(n)]; return statistics.median(L)
    R['timing'] = {}
    for label, path in (('朴素', '/login-naive'), ('统一(不存在的用户也算哈希)', '/login')):
        with app.app_context(): db.session.execute(sa.text("update acct set fails=0, locked_until=0")); db.session.commit()
        tn, te = med(path, 'nobody'), med(path, 'bob') if path == '/login-naive' else None
        if te is None:
            tb = []; 
            for _ in range(2): post(path, 'bob', 'x')
            tb = []; 
            for i in range(4): t0 = time.perf_counter(); post(path, 'bob', 'x'); tb.append(ms(t0))
            with app.app_context(): db.session.execute(sa.text("update acct set fails=0, locked_until=0")); db.session.commit()
            te = statistics.median(tb)
        print(f'  {label:<26} 不存在的用户 {tn:7.1f} ms | 存在的用户(错误密码){te:7.1f} ms | 差 {te - tn:6.1f} ms'); R['timing'][label] = [tn, te]
    print()
    print('== 四:并发猜测与计数:读出再写回(非原子)vs 原子 UPDATE ... RETURNING(20 个线程同时发 20 次错误密码,上限 5)')
    R['race'] = {}
    for label, path in (('读出再写回(非原子)', '/login-race'), ('原子 UPDATE ... WHERE fails < 上限', '/login-atomic')):
        with app.app_context(): db.session.execute(sa.text("update acct set fails=0 where name='ann'")); db.session.commit()
        res = []; bar = threading.Barrier(20)
        def w():
            cl = app.test_client(); bar.wait(); res.append(cl.post(path, json={'username': 'ann', 'password': 'bad'}).status_code)
        ths = [threading.Thread(target=w) for _ in range(20)]; [t.start() for t in ths]; [t.join() for t in ths]
        evaluated = sum(1 for s in res if s == 401); print(f'  {label:<30} 真正去校验了密码的尝试 {evaluated} 次(上限 {MAX}),被拒绝 {sum(1 for s in res if s == 423)} 次'); R['race'][label] = [evaluated, sum(1 for s in res if s == 423)]
finally:
    pg.stop()
save('f131', R)
