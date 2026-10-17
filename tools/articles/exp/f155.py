import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f155'); R = {}
import dj
pg = dj.PG(9476, name='f155pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
APPPY = f'''
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(30))
def create_app(url="{URL}"):
    app = Flask(__name__); app.config.update(SQLALCHEMY_DATABASE_URI=url, TESTING=True)
    db.init_app(app)
    @app.post("/items")
    def add():
        db.session.add(Item(name=request.json["name"])); db.session.commit(); return jsonify(count=Item.query.count()), 201
    @app.get("/items")
    def lst(): return jsonify(count=Item.query.count())
    return app
'''
TESTS = '''
def test_adds_one(client):
    assert client.post("/items", json={"name": "a"}).get_json()["count"] == 1
def test_starts_empty(client):
    assert client.get("/items").get_json()["count"] == 0
'''
MANY = '\n'.join(f'def test_n{i}(client):\n    assert client.post("/items", json={{"name": "x"}}).get_json()["count"] == 1\n' for i in range(100))
CONF = {
 'drop_create': '''
import pytest
from myapp import create_app, db
@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context(): db.drop_all(); db.create_all()
    return app
@pytest.fixture
def client(app):
    with app.app_context(): db.drop_all(); db.create_all()
    return app.test_client()
''',
 'truncate': '''
import pytest, sqlalchemy as sa
from myapp import create_app, db
@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context(): db.drop_all(); db.create_all()
    return app
@pytest.fixture
def client(app):
    yield app.test_client()
    with app.app_context(): db.session.remove(); db.session.execute(sa.text("truncate item restart identity")); db.session.commit()
''',
 'nothing': '''
import pytest
from myapp import create_app, db
@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context(): db.drop_all(); db.create_all()
    return app
@pytest.fixture
def client(app): return app.test_client()
''',
 'rollback_naive': '''
import pytest
from myapp import create_app, db
@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context(): db.drop_all(); db.create_all()
    return app
@pytest.fixture
def client(app):
    with app.app_context():
        conn = db.engine.connect(); trans = conn.begin()
        orig = db.session.registry.session_factory.kw.get("bind") if False else None
    c = app.test_client(); yield c
    trans.rollback(); conn.close()
''',
 'savepoint': '''
import pytest
from sqlalchemy.orm import Session, scoped_session
from myapp import create_app, db
@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context(): db.drop_all(); db.create_all()
    return app
@pytest.fixture
def client(app):
    ctx = app.app_context(); ctx.push()
    conn = db.engine.connect(); trans = conn.begin()
    sess = Session(bind=conn, join_transaction_mode="create_savepoint")
    orig_session = db.session
    db.session = scoped_session(lambda: sess)   # 让视图里的 db.session 用这个绑在外层事务上的 session
    yield app.test_client()
    sess.close(); trans.rollback(); conn.close(); db.session = orig_session; ctx.pop()
''',
}
def run(name, extra='', n_tests=None):
    files = {'myapp.py': APPPY, 'conftest.py': CONF[name], 'test_x.py': TESTS + extra}
    d = mkapp(f'f155_{name}', files); t0 = time.perf_counter()
    r = subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--no-header'], cwd=d, capture_output=True, text=True, env=env(d)); t = ms(t0); out = tidy(r.stdout + r.stderr)
    last = [l for l in out.splitlines() if ' passed' in l or ' failed' in l]; return (last[-1].strip() if last else out[-200:]), t, out
print('== 一:两个测试(先加一行,再检查是空的):各种清理策略能不能隔离')
R['iso'] = {}
for name, label in (('nothing', '不清理'), ('drop_create', '每个测试 drop_all + create_all'), ('truncate', '每个测试之后 TRUNCATE'), ('savepoint', '外层事务 + 保存点,测试结束回滚')):
    last, t, out = run(name); print(f'  {label:<34} {last}'); R['iso'][label] = last
print()
print(f'== 二:100 个测试(每个都 POST 一条并提交)的总耗时,PostgreSQL 本机')
R['cost'] = {}
many = '\n' + MANY
for name, label in (('drop_create', '每个测试 drop_all + create_all'), ('truncate', '每个测试之后 TRUNCATE'), ('savepoint', '外层事务 + 保存点回滚')):
    files = {'myapp.py': APPPY, 'conftest.py': CONF[name], 'test_x.py': MANY}
    d = mkapp(f'f155m_{name}', files); t0 = time.perf_counter(); r = subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--no-header'], cwd=d, capture_output=True, text=True, env=env(d)); t = ms(t0); out = tidy(r.stdout + r.stderr)
    last = [l for l in out.splitlines() if ' passed' in l or ' failed' in l]; print(f'  {label:<34} {last[-1].strip() if last else out[-100:]} | 总耗时 {t / 1000:.2f} 秒'); R['cost'][label] = [last[-1].strip() if last else '', t]
print()
print('== 三:保存点方案的要点:应用代码里的 commit() 只提交到保存点,外层事务回滚后数据库里什么都不剩')
files = {'myapp.py': APPPY, 'conftest.py': CONF['savepoint'], 'test_x.py': 'def test_commit_inside(client):\n    assert client.post("/items", json={"name": "z"}).get_json()["count"] == 1\n'}
d = mkapp('f155_check', files); subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--no-header'], cwd=d, capture_output=True, text=True, env=env(d)); left = pg.psql('select count(*) from item'); print('  测试里应用代码 commit 过之后,数据库里实际留下的行数:', left); R['left'] = left
save('f155', R)
pg.stop()
