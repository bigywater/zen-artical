import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f27'); R = {}
from flask import Flask, Blueprint, url_for
def mk(name='bp', bp_prefix=None, reg_prefix=None, routes=('/x',)):
    b = Blueprint(name, __name__, url_prefix=bp_prefix)
    for i, r in enumerate(routes): b.add_url_rule(r, f'v{i}', lambda: 'ok')
    a = Flask('p'); a.logger.disabled = True; a.register_blueprint(b, url_prefix=reg_prefix) if reg_prefix is not None else a.register_blueprint(b); return a
def rules(a): return [str(r) for r in a.url_map.iter_rules() if r.endpoint != 'static']
print('== 一:url_prefix 写在 Blueprint(...) 与写在 register_blueprint(...) 里:后者覆盖前者')
R['p1'] = {}
for label, kw in (('Blueprint(url_prefix="/a")', dict(bp_prefix='/a')), ('register_blueprint(url_prefix="/b")', dict(reg_prefix='/b')), ('两处都写:Blueprint /a + register /b', dict(bp_prefix='/a', reg_prefix='/b')), ('都不写', {})):
    a = mk(**kw); R['p1'][label] = rules(a); print(f'  {label:<42} → {rules(a)}')
print()
print('== 二:前缀与路由拼接时的斜杠:/ 路由、空字符串路由、前缀带尾斜杠')
R['p2'] = {}
for label, kw in (('前缀 /api + 路由 /', dict(bp_prefix='/api', routes=('/',))), ('前缀 /api + 路由 ""(空串)', dict(bp_prefix='/api', routes=('',))), ('前缀 /api/ + 路由 /x', dict(bp_prefix='/api/', routes=('/x',))), ('前缀 /api + 路由 x(无前导斜杠)', dict(bp_prefix='/api', routes=('x',))), ('前缀 api(无前导斜杠)+ 路由 /x', dict(bp_prefix='api', routes=('/x',)))):
    try: a = mk(**kw); R['p2'][label] = rules(a); print(f'  {label:<34} → {rules(a)}')
    except Exception as e: R['p2'][label] = f'{type(e).__name__}: {e}'; print(f'  {label:<34} → {type(e).__name__}: {str(e)[:100]}')
print()
print('== 三:访问行为:/api/(规则是 /api/)与 /api(空串路由,规则是 /api)')
a1 = mk(bp_prefix='/api', routes=('/',)); a2 = mk(bp_prefix='/api', routes=('',)); c1, c2 = a1.test_client(), a2.test_client()
print('  路由 "/" :', {p: c1.get(p).status_code for p in ('/api', '/api/')}); print('  路由 "" :', {p: c2.get(p).status_code for p in ('/api', '/api/')}); R['p3'] = [{p: c1.get(p).status_code for p in ('/api', '/api/')}, {p: c2.get(p).status_code for p in ('/api', '/api/')}]
print()
print('== 四:嵌套蓝图的前缀是逐层叠加的;register_blueprint 里给子蓝图覆盖前缀')
parent = Blueprint('par', __name__, url_prefix='/v1'); child = Blueprint('kid', __name__, url_prefix='/users'); child.add_url_rule('/<int:i>', 'get', lambda i: 'u'); parent.register_blueprint(child); a = Flask('n'); a.register_blueprint(parent)
print('  v1 + users:', rules(a)); R['p4a'] = rules(a)
parent2 = Blueprint('par2', __name__, url_prefix='/v1'); child2 = Blueprint('kid2', __name__, url_prefix='/users'); child2.add_url_rule('/<int:i>', 'get', lambda i: 'u'); parent2.register_blueprint(child2, url_prefix='/people'); a = Flask('n2'); a.register_blueprint(parent2, url_prefix='/v2')
print('  父蓝图注册时改成 /v2、子蓝图注册时改成 /people:', rules(a)); R['p4b'] = rules(a)
print()
print('== 五:url_for 与前缀:同一个蓝图用不同前缀注册两次(name= 区分)')
b = Blueprint('multi', __name__); b.add_url_rule('/ping', 'ping', lambda: 'pong'); a = Flask('mm'); a.register_blueprint(b, url_prefix='/v1'); a.register_blueprint(b, url_prefix='/v2', name='multi2')
with a.test_request_context('/'): print("  url_for('multi.ping') →", url_for('multi.ping'), "| url_for('multi2.ping') →", url_for('multi2.ping')); R['p5'] = [url_for('multi.ping'), url_for('multi2.ping')]
print()
print('== 六:前缀有包含关系的两个蓝图(/a 与 /a/b)声明了同一个最终 URL 时')
b1 = Blueprint('one', __name__, url_prefix='/a'); b1.add_url_rule('/b/c', 'bc', lambda: 'one'); b2 = Blueprint('two', __name__, url_prefix='/a/b'); b2.add_url_rule('/c', 'c', lambda: 'two'); a = Flask('pp'); a.register_blueprint(b1); a.register_blueprint(b2)
print('  规则:', rules(a), '| GET /a/b/c →', a.test_client().get('/a/b/c').get_data(as_text=True), '(两个蓝图声明了同一个最终 URL,先注册的赢)'); R['p6'] = a.test_client().get('/a/b/c').get_data(as_text=True)
save('f27', R)
