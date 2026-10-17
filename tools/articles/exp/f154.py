import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f154'); R = {}
FILES = {
 'myapp.py': '''
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(30))
def create_app(config=None):
    app = Flask(__name__); app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True, SECRET_KEY="k"); app.config.update(config or {})
    db.init_app(app)
    @app.post("/items")
    def add():
        db.session.add(Item(name=request.json["name"])); db.session.commit(); return jsonify(count=Item.query.count()), 201
    @app.get("/items")
    def lst(): return jsonify(count=Item.query.count())
    return app
''',
 'conftest.py': '''
import pytest
from myapp import create_app, db
@pytest.fixture
def app():
    app = create_app()
    with app.app_context(): db.create_all()
    yield app
@pytest.fixture
def client(app): return app.test_client()
''',
 'test_a.py': '''
def test_add_one(client):
    assert client.post("/items", json={"name": "a"}).get_json()["count"] == 1
def test_starts_empty(client):
    assert client.get("/items").get_json()["count"] == 0
def test_config_override():
    from myapp import create_app
    assert create_app({"SECRET_KEY": "other"}).config["SECRET_KEY"] == "other"
''',
}
d = mkapp('f154', FILES)
def pytest_run(*args, files=None, d=d):
    r = subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider'] + list(args), cwd=d, capture_output=True, text=True, env=env(d)); return r.returncode, tidy(r.stdout + r.stderr)
print('== 一:函数级 fixture:每个测试一个全新的应用与内存数据库(pytest -v)')
rc, out = pytest_run('-v', '--no-header'); lines = [l for l in out.splitlines() if 'PASSED' in l or 'FAILED' in l or 'passed' in l or 'failed' in l]; [print('  ' + l) for l in lines]; R['v'] = lines
print()
print('== 二:--setup-show:fixture 的创建与清理顺序')
rc, out = pytest_run('--setup-show', '-q', 'test_a.py::test_add_one'); lines = [l for l in out.splitlines() if 'SETUP' in l or 'TEARDOWN' in l or '::' in l]; [print('  ' + l) for l in lines]; R['setup_show'] = lines
print()
print('== 三:把 app 改成 session 级(整个测试会话共用一个应用与数据库):测试之间互相污染')
FILES2 = dict(FILES); FILES2['conftest.py'] = FILES['conftest.py'].replace('@pytest.fixture\ndef app():', '@pytest.fixture(scope="session")\ndef app():')
d2 = mkapp('f154b', FILES2); rc, out = pytest_run('-v', '--no-header', d=d2); lines = [l for l in out.splitlines() if 'PASSED' in l or 'FAILED' in l or ' passed' in l or ' failed' in l or 'assert' in l.lower()]; [print('  ' + l[:150]) for l in lines]; R['session_scope'] = lines
print('  (按文件里的顺序,test_add_one 先加了一行,test_starts_empty 看到了它留下的数据)')
print()
print('== 四:随机/反序执行暴露顺序依赖:同样 session 级 fixture,倒序运行')
rc, out = pytest_run('-v', '--no-header', 'test_a.py::test_starts_empty', 'test_a.py::test_add_one', d=d2); lines = [l for l in out.splitlines() if 'PASSED' in l or 'FAILED' in l or ' passed' in l or ' failed' in l]; [print('  ' + l[:150]) for l in lines]; R['reverse'] = lines
print()
print('== 五:创建应用的代价:每个测试一个新应用 vs 整个会话一个(各跑 200 个简单测试)')
many = '\n'.join(f'def test_n{i}(client):\n    assert client.get("/items").status_code == 200\n' for i in range(200))
R['cost'] = {}
for label, files_ in (('函数级 app(每个测试新建)', dict(FILES, **{'test_many.py': many})), ('会话级 app,每个测试清空数据', None)):
    if files_ is None:
        files_ = dict(FILES); files_['conftest.py'] = '''
import pytest
from myapp import create_app, db
@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context(): db.create_all()
    return app
@pytest.fixture
def client(app):
    yield app.test_client()
    with app.app_context(): db.session.rollback(); db.drop_all(); db.create_all()
'''; files_['test_many.py'] = many
    dd = mkapp('f154c', files_); t0 = time.perf_counter(); rc, out = pytest_run('-q', 'test_many.py', d=dd); t = ms(t0); last = [l for l in out.splitlines() if 'passed' in l][-1]; print(f'  {label:<28} {last.strip()} | 总耗时(含启动 pytest){t / 1000:.2f} 秒'); R['cost'][label] = [last.strip(), t]
save('f154', R)
