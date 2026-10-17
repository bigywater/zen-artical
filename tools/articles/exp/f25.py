import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f25'); R = {}
from flask import Flask, Blueprint
print('== 一:endpoint 冲突:两个视图用了同一个 endpoint 名(最常见:函数同名、或给不同函数用了同一个 endpoint=)')
a = Flask('c1')
@a.route('/a')
def page(): return 'a'
try:
    @a.route('/b')
    def page(): return 'b'
except AssertionError as e: print('  同名函数 → AssertionError:', str(e)); R['ep1'] = str(e)
a.add_url_rule('/same', 'page', page); print('  同一个函数对象用同一个 endpoint 注册第二个 URL → 允许(同一函数)'); R['ep_same_fn'] = True
print()
print('== 二:规则冲突:同一个 URL 被两个不同的端点注册:先注册的永远赢,后一个没有报错')
a = Flask('c2'); a.add_url_rule('/x', 'first', lambda: 'first'); a.add_url_rule('/x', 'second', lambda: 'second')
print('  GET /x →', a.test_client().get('/x').get_data(as_text=True), '| 规则列表:', [(r.rule, r.endpoint) for r in a.url_map.iter_rules() if r.rule == '/x']); R['rule_dup'] = a.test_client().get('/x').get_data(as_text=True)
print()
print('== 三:应用与蓝图注册了同一个 URL')
for first in ('app', 'bp'):
    a = Flask('c3'); bp = Blueprint('bp', __name__)
    bp.add_url_rule('/hello', 'hello', lambda: 'from bp')
    if first == 'app': a.add_url_rule('/hello', 'hello_app', lambda: 'from app'); a.register_blueprint(bp)
    else: a.register_blueprint(bp); a.add_url_rule('/hello', 'hello_app', lambda: 'from app')
    print(f'  先注册{"应用路由" if first == "app" else "蓝图"}、后注册{"蓝图" if first == "app" else "应用路由"} → GET /hello:', a.test_client().get('/hello').get_data(as_text=True)); R.setdefault('bp_app', {})[first] = a.test_client().get('/hello').get_data(as_text=True)
print()
print('== 四:同一个蓝图用两个不同的前缀注册两次:需要 name= 避免 endpoint 冲突')
bp = Blueprint('multi', __name__); bp.add_url_rule('/ping', 'ping', lambda: 'pong'); a = Flask('c4')
a.register_blueprint(bp, url_prefix='/v1')
try: a.register_blueprint(bp, url_prefix='/v2')
except ValueError as e: print('  第二次注册同名蓝图 → ValueError:', ' '.join(str(e).split())[:230]); R['bp2'] = ' '.join(str(e).split())
a.register_blueprint(bp, url_prefix='/v2', name='multi_v2'); print('  加 name="multi_v2" 后:', {p: a.test_client().get(p).status_code for p in ('/v1/ping', '/v2/ping')}, '| endpoints:', sorted(e for e in a.view_functions if 'ping' in e)); R['bp2_ok'] = sorted(e for e in a.view_functions if 'ping' in e)
print()
print('== 五:通配路由吃掉了后面的规则?/<path:p> 与具体路由的优先级,以及 /<slug> 吃掉 /about 这类固定页面吗')
a = Flask('c5'); a.add_url_rule('/<path:p>', 'catch', lambda p: f'catch:{p}'); a.add_url_rule('/about', 'about', lambda: 'about'); a.add_url_rule('/api/users', 'users', lambda: 'users')
print('  ', {p: a.test_client().get(p).get_data(as_text=True) for p in ('/about', '/api/users', '/api/x', '/zzz/yyy')}); R['catch'] = {p: a.test_client().get(p).get_data(as_text=True) for p in ('/about', '/api/users', '/api/x', '/zzz/yyy')}
print()
print('== 六:用脚本在启动时检查冲突:遍历 url_map,找出「同一个 URL 模式 + 同一个方法」被多个端点注册的情况')
def find_conflicts(app):
    seen = {}; out = []
    for r in app.url_map.iter_rules():
        key_rule = __import__('re').sub(r'<[^:>]+:|<', '<', r.rule)
        for m in r.methods - {'HEAD', 'OPTIONS'}:
            k = (key_rule, m)
            if k in seen and seen[k] != r.endpoint: out.append((key_rule, m, seen[k], r.endpoint))
            seen.setdefault(k, r.endpoint)
    return out
a = Flask('c6'); a.add_url_rule('/u/<int:i>', 'u_int', lambda i: 'i'); a.add_url_rule('/u/<name>', 'u_name', lambda name: 'n'); a.add_url_rule('/x', 'x1', lambda: '1'); a.add_url_rule('/x', 'x2', lambda: '2', methods=['POST']); a.add_url_rule('/x', 'x3', lambda: '3')
print('  冲突检查结果:', find_conflicts(a)); R['conf'] = [list(map(str, t)) for t in find_conflicts(a)]
print('  (/u/<int:i> 与 /u/<name> 参数名不同、归一化后模式也不同,没有被报出来;这个简化脚本只能发现「模式与方法完全相同」的冲突)')
print()
print('== 七:flask routes 的排序:--sort rule / endpoint / methods')
d = mkapp('f25', {'ra.py': 'from flask import Flask\napp = Flask(__name__)\n@app.get("/b")\ndef zeta(): return "b"\n@app.get("/a")\ndef alpha(): return "a"\n@app.post("/a")\ndef alpha_post(): return "a"\n'})
for key in ('endpoint', 'rule', 'methods'):
    r = subprocess.run([str(BIN / 'flask'), '--app', 'ra', 'routes', '--sort', key], cwd=d, env=env(d), capture_output=True, text=True); L = [l.split()[0] for l in r.stdout.strip().split('\n')[2:]]; print(f'  --sort {key:<9} → 端点顺序 {L}'); R.setdefault('sort', {})[key] = L
save('f25', R)
