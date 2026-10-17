import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f159'); R = {}
FILES = {
 'shop.py': '''
from flask import Blueprint, jsonify, g, request, current_app, url_for
bp = Blueprint("shop", __name__, url_prefix="/shop")
@bp.before_request
def tag(): g.shop_hook = "ran"
@bp.after_request
def mark(r): r.headers["X-Shop"] = "1"; return r
@bp.get("/items")
def items(): return jsonify(items=["a", "b"], hook=g.get("shop_hook"), endpoint=request.endpoint, self_url=url_for(".items"), cfg=current_app.config.get("CURRENCY", "unset"))
@bp.get("/<int:i>")
def one(i): return jsonify(i=i)
''',
 'conftest.py': '''
import pytest
from flask import Flask
from shop import bp
@pytest.fixture
def app():
    app = Flask(__name__); app.config.update(TESTING=True, CURRENCY="CNY")
    app.register_blueprint(bp)
    @app.get("/other")
    def other(): return "other"
    return app
@pytest.fixture
def client(app): return app.test_client()
''',
 'test_shop.py': '''
import pytest
from flask import Flask, url_for
from shop import bp
def test_route_and_prefix(client):
    r = client.get("/shop/items"); j = r.get_json(); print("RESULT route", r.status_code, j); assert r.status_code == 200
def test_endpoint_name_has_blueprint_prefix(app):
    with app.test_request_context(): print("RESULT url_for", url_for("shop.items"), url_for("shop.one", i=3)); assert url_for("shop.one", i=3) == "/shop/3"
def test_hooks_only_for_blueprint(client):
    r1 = client.get("/shop/items"); r2 = client.get("/other"); print("RESULT hooks", r1.headers.get("X-Shop"), r2.headers.get("X-Shop")); assert r2.headers.get("X-Shop") is None
def test_blueprint_uses_app_config(client):
    print("RESULT cfg", client.get("/shop/items").get_json()["cfg"]); assert client.get("/shop/items").get_json()["cfg"] == "CNY"
def test_register_with_other_prefix():
    app = Flask(__name__); app.config["TESTING"] = True; app.register_blueprint(bp, url_prefix="/v2/store")
    c = app.test_client(); print("RESULT other-prefix", c.get("/v2/store/items").status_code, c.get("/shop/items").status_code); assert c.get("/v2/store/items").status_code == 200 and c.get("/shop/items").status_code == 404
def test_register_twice_needs_different_names():
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/one")
    try: app.register_blueprint(bp, url_prefix="/two"); print("RESULT twice no error")
    except ValueError as e: print("RESULT twice ValueError:", str(e)[:90])
    app.register_blueprint(bp, url_prefix="/two", name="shop2"); c = app.test_client(); print("RESULT twice-named", c.get("/one/items").status_code, c.get("/two/items").status_code)
def test_isolated_app_only_this_blueprint():
    app = Flask(__name__); app.config["TESTING"] = True; app.register_blueprint(bp)
    print("RESULT isolated", sorted(app.blueprints), sorted(r.rule for r in app.url_map.iter_rules() if r.endpoint != "static")); assert list(app.blueprints) == ["shop"]
def test_no_registration_means_404():
    app = Flask(__name__); app.config["TESTING"] = True
    print("RESULT unregistered", app.test_client().get("/shop/items").status_code)
def test_hook_effect_visible_through_g(client):
    with client: client.get("/shop/items"); from flask import g; print("RESULT g", g.shop_hook); assert g.shop_hook == "ran"
''',
}
d = mkapp('f159', FILES)
r = subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider', '-v', '-s', '--no-header'], cwd=d, capture_output=True, text=True, env=env(d)); out = tidy(r.stdout + r.stderr)
print('== 一:一组 Blueprint 测试(pytest -v -s,真实运行)')
for l in out.splitlines():
    if 'RESULT' in l or ' passed' in l or ' failed' in l or 'FAILED' in l or 'Error' in l[:40]: print('  ' + l.replace('test_shop.py::', '')[:230])
R['out'] = [l for l in out.splitlines() if 'RESULT' in l or ' passed' in l or ' failed' in l]
save('f159', R)
