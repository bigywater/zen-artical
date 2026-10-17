import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f26'); R = {}
from flask import Flask, Blueprint, request, url_for, current_app
print('== 一:蓝图只是「记录」:路由在 register_blueprint 之前不在 url_map 里')
bp = Blueprint('api', __name__)
@bp.route('/ping')
def ping(): return 'pong'
@bp.before_request
def bp_before(): pass
print('  蓝图对象上记录的延迟函数 deferred_functions 个数:', len(bp.deferred_functions), '| 类型:', [type(f).__name__ for f in bp.deferred_functions][:3]); R['deferred'] = len(bp.deferred_functions)
app = Flask('bpdemo'); app.logger.disabled = True
print('  注册前 app.url_map 的规则:', [str(r) for r in app.url_map.iter_rules() if r.endpoint != 'static'], '| app.blueprints =', dict(app.blueprints))
app.register_blueprint(bp)
print('  注册后 app.url_map 的规则:', [(str(r), r.endpoint) for r in app.url_map.iter_rules() if r.endpoint != 'static'], '| app.blueprints =', {k: type(v).__name__ for k, v in app.blueprints.items()}); R['after'] = [(str(r), r.endpoint) for r in app.url_map.iter_rules() if r.endpoint != 'static']
print()
print('== 二:蓝图注册之后,再给蓝图加路由会报错(Flask 2.2+)')
try:
    @bp.route('/late')
    def late(): return 'late'
except AssertionError as e: print('  AssertionError:', str(e).split('\n')[0]); R['late'] = str(e).split('\n')[0]
print()
print('== 三:endpoint 前缀与相对 url_for;request.blueprint / request.blueprints')
seen = {}
bp2 = Blueprint('shop', __name__, url_prefix='/shop')
@bp2.route('/info')
def info():
    seen['blueprint'] = request.blueprint; seen['blueprints'] = request.blueprints; seen['endpoint'] = request.endpoint; seen['rel'] = url_for('.info'); seen['abs'] = url_for('shop.info'); return 'info'
app.register_blueprint(bp2); app.test_client().get('/shop/info'); print('  请求 /shop/info 时:', seen); R['seen'] = seen
print()
print('== 四:嵌套蓝图(Flask 2.0+):子蓝图的 endpoint 是「父.子.函数」,URL 前缀叠加')
parent = Blueprint('parent', __name__, url_prefix='/p'); child = Blueprint('child', __name__, url_prefix='/c')
@child.route('/x')
def x(): return 'child x'
parent.register_blueprint(child); a2 = Flask('nest'); a2.register_blueprint(parent)
print('  规则:', [(str(r), r.endpoint) for r in a2.url_map.iter_rules() if r.endpoint != 'static'], '| GET /p/c/x →', a2.test_client().get('/p/c/x').get_data(as_text=True)); R['nest'] = [(str(r), r.endpoint) for r in a2.url_map.iter_rules() if r.endpoint != 'static']
with a2.test_request_context('/p/c/x'): print('  请求里 request.blueprints =', request.blueprints, '| request.blueprint =', request.blueprint); R['nest_bps'] = [request.blueprints, request.blueprint]
print()
print('== 五:蓝图自己的钩子、错误处理器、上下文处理器只对本蓝图的请求生效;before_app_request 等 app_ 前缀的对全局生效(上篇已量过顺序,这里验证作用范围)')
ev = []
bp3 = Blueprint('b3', __name__, url_prefix='/b3')
@bp3.before_request
def b3_before(): ev.append('b3.before_request')
@bp3.errorhandler(404)
def b3_404(e): return 'b3 的 404', 404
@bp3.context_processor
def b3_ctx(): return {'who': 'b3'}
@bp3.route('/t')
def t(): from flask import render_template_string; return render_template_string('who={{ who|default("(无)") }}')
a3 = Flask('hooks'); a3.logger.disabled = True; a3.register_blueprint(bp3)
@a3.route('/plain')
def plain(): from flask import render_template_string; return render_template_string('who={{ who|default("(无)") }}')
c = a3.test_client(); ev.clear(); r1 = c.get('/b3/t'); e1 = list(ev); ev.clear(); r2 = c.get('/plain'); e2 = list(ev)
print('  /b3/t   → 回调', e1, '| 模板里 who =', r1.get_data(as_text=True)); print('  /plain  → 回调', e2, '| 模板里', r2.get_data(as_text=True)); R['scope'] = [e1, r1.get_data(as_text=True), e2, r2.get_data(as_text=True)]
print('  蓝图的 errorhandler(404):GET /b3/nope →', c.get('/b3/nope').get_data(as_text=True), '(路由没匹配,不属于任何蓝图,用的是应用的默认 404)'); R['b3_404'] = c.get('/b3/nope').get_data(as_text=True)[:50]
print()
print('== 六:用蓝图拆分应用:一个 app 目录结构与实际运行')
d = __import__('fl').app('f26', {'shop/__init__.py': 'from flask import Blueprint\nbp = Blueprint("shop", __name__, url_prefix="/shop")\nfrom . import views\n', 'shop/views.py': 'from . import bp\n@bp.route("/")\ndef home(): return "shop home"\n@bp.route("/<int:i>")\ndef item(i): return f"item {i}"\n', 'main.py': 'from flask import Flask\nfrom shop import bp as shop_bp\napp = Flask(__name__)\napp.register_blueprint(shop_bp)\n'})
rc, o = py(d, 'from main import app\nc = app.test_client()\nprint(sorted((str(r), r.endpoint) for r in app.url_map.iter_rules() if r.endpoint != "static"))\nprint(c.get("/shop/").get_data(as_text=True), "|", c.get("/shop/3").get_data(as_text=True))\nprint("蓝图对象的 root_path:", app.blueprints["shop"].root_path.replace(__import__("os").getcwd(), "<项目>"))'); pr(o, 5, w=230); R['layout'] = o.split('\n')
save('f26', R)
