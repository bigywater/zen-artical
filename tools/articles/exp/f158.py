import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f158'); R = {}
FILES = {
 'myapp.py': '''
from flask import Flask, jsonify, abort, Blueprint
from werkzeug.exceptions import HTTPException
class PaymentError(Exception):
    def __init__(self, code): self.code = code
def create_app(testing=True, handle_500=True):
    app = Flask(__name__); app.config["TESTING"] = testing
    @app.errorhandler(PaymentError)
    def pay(e): return jsonify(error="payment", code=e.code), 402
    @app.errorhandler(404)
    def nf(e): return jsonify(error="not found"), 404
    if handle_500:
        @app.errorhandler(500)
        def ise(e): return jsonify(error="server error"), 500
    @app.get("/pay")
    def pay_view(): raise PaymentError("card_declined")
    @app.get("/boom")
    def boom(): raise RuntimeError("unexpected")
    @app.get("/abort")
    def ab(): abort(403)
    @app.get("/handler-bug")
    def hb(): raise PaymentError("x")
    bp = Blueprint("bp", __name__, url_prefix="/b")
    @bp.errorhandler(ValueError)
    def bpv(e): return jsonify(error="bp value error"), 400
    @bp.get("/v")
    def bv(): raise ValueError("in blueprint")
    @app.get("/outside-bp")
    def ob(): raise ValueError("outside")
    app.register_blueprint(bp)
    return app
''',
 'test_errors.py': '''
import pytest
from myapp import create_app
def test_custom_exception_handler():
    r = create_app().test_client().get("/pay"); print("RESULT custom", r.status_code, r.get_json()); assert r.status_code == 402
def test_404_handler():
    r = create_app().test_client().get("/nope"); print("RESULT 404", r.status_code, r.get_json()); assert r.get_json() == {"error": "not found"}
def test_abort_403_no_handler():
    r = create_app().test_client().get("/abort"); print("RESULT abort403", r.status_code, r.content_type); assert r.status_code == 403
def test_unhandled_exception_propagates_in_testing():
    app = create_app(testing=True)
    with pytest.raises(RuntimeError, match="unexpected"): app.test_client().get("/boom")
    print("RESULT propagate raised RuntimeError in the test")
def test_500_handler_runs_when_not_testing():
    r = create_app(testing=False).test_client().get("/boom"); print("RESULT 500handler", r.status_code, r.get_json()); assert r.get_json() == {"error": "server error"}
def test_override_propagation_inside_testing():
    app = create_app(testing=True); app.config["PROPAGATE_EXCEPTIONS"] = False
    r = app.test_client().get("/boom"); print("RESULT propagate-off", r.status_code, r.get_json()); assert r.status_code == 500
def test_blueprint_handler_scope():
    c = create_app().test_client(); r1 = c.get("/b/v"); print("RESULT bp-inside", r1.status_code, r1.get_json())
    with pytest.raises(ValueError): c.get("/outside-bp")
    print("RESULT bp-outside raised ValueError (blueprint handler does not apply)")
def test_handler_error_format_contract():
    r = create_app().test_client().get("/pay"); j = r.get_json(); print("RESULT contract", sorted(j)); assert set(j) == {"error", "code"}
''',
}
d = mkapp('f158', FILES)
r = subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider', '-v', '-s', '--no-header'], cwd=d, capture_output=True, text=True, env=env(d)); out = tidy(r.stdout + r.stderr)
print('== 一:一组异常处理器测试(pytest -v -s,真实运行)')
for l in out.splitlines():
    if 'RESULT' in l or ' passed' in l or ' failed' in l or 'FAILED' in l: print('  ' + l.replace('test_errors.py::', '')[:200])
R['out'] = [l for l in out.splitlines() if 'RESULT' in l or ' passed' in l or ' failed' in l]
save('f158', R)
