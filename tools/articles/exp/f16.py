import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f16'); R = {}
import inspect
from flask import Flask
print('== 一:@app.route() 做了什么:装饰器返回原函数,同时往 url_map 与 view_functions 里各写一项')
app = Flask('r')
src('''
    @app.route("/hello", methods=["GET"])
    def hello(): return "hi"
''')
before = (len(list(app.url_map.iter_rules())), len(app.view_functions))
@app.route('/hello', methods=['GET'])
def hello(): return 'hi'
after = (len(list(app.url_map.iter_rules())), len(app.view_functions)); print('  注册前 → 后:规则数', before[0], '→', after[0], '| view_functions 数', before[1], '→', after[1]); R['counts'] = [before, after]
print('  装饰器返回的是原函数:', hello.__name__, '| callable:', callable(hello), '| 类型:', type(hello).__name__)
rule = [r for r in app.url_map.iter_rules() if r.endpoint == 'hello'][0]
print('  Rule 对象:rule =', rule.rule, '| endpoint =', rule.endpoint, '| methods =', sorted(rule.methods), '| strict_slashes =', rule.strict_slashes, '| view_functions["hello"] is hello:', app.view_functions['hello'] is hello)
R['rule'] = [rule.rule, rule.endpoint, sorted(rule.methods)]
print()
print('== 二:route 只是 add_url_rule 的语法糖:两种写法的结果完全一样')
a1 = Flask('r1'); a2 = Flask('r2')
@a1.route('/x', methods=['POST'])
def f(): return 'x'
def f2(): return 'x'
a2.add_url_rule('/x', endpoint='f', view_func=f2, methods=['POST'])
r1 = [(r.rule, r.endpoint, sorted(r.methods)) for r in a1.url_map.iter_rules() if r.endpoint == 'f']; r2 = [(r.rule, r.endpoint, sorted(r.methods)) for r in a2.url_map.iter_rules() if r.endpoint == 'f']
print('  @route 的规则  :', r1); print('  add_url_rule :', r2); print('  相同:', r1 == r2); R['same'] = r1 == r2
src_ = inspect.getsource(Flask.route).split('\n'); body = [l for l in inspect.getsource(Flask.route.__wrapped__ if hasattr(Flask.route, '__wrapped__') else Flask.route).split('\n')]
from flask.sansio.scaffold import Scaffold
code = inspect.getsource(Scaffold.route).split('\n'); i0 = [i for i, l in enumerate(code) if 'def decorator' in l][0]
print('  Scaffold.route 里的 decorator(原样):'); print('\n'.join('    ' + l[4:] if l.startswith('    ') else '    ' + l for l in code[i0:i0 + 6])); R['route_src'] = code[i0:i0 + 6]
print()
print('== 三:endpoint 默认取函数名;同名函数会冲突;endpoint 可以自己指定')
a = Flask('e')
@a.route('/a')
def view(): return 'a'
try:
    @a.route('/b')
    def view(): return 'b'
except AssertionError as e: print('  两个同名函数 → AssertionError:', str(e)[:160]); R['dup'] = str(e)
@a.route('/c', endpoint='c_custom')
def another(): return 'c'
print('  自定义 endpoint 后 view_functions 的键:', sorted(a.view_functions)); R['endpoints'] = sorted(a.view_functions)
print()
print('== 四:同一个函数挂多个路径;同一个路径挂多个方法;methods 默认只有 GET(并自动加 HEAD、OPTIONS)')
a = Flask('m')
@a.route('/one')
@a.route('/two')
@a.route('/three', methods=['POST'])
def multi(): return 'multi'
for r in sorted(a.url_map.iter_rules(), key=lambda r: r.rule):
    if r.endpoint == 'multi': print(f'  {r.rule:<7} → {sorted(r.methods)}')
R['multi'] = {r.rule: sorted(r.methods) for r in a.url_map.iter_rules() if r.endpoint == 'multi'}
c = a.test_client(); print('  请求:', {p: c.get(p).status_code for p in ('/one', '/two', '/three')}, '| POST /three:', c.post('/three').status_code); R['status'] = {p: c.get(p).status_code for p in ('/one', '/two', '/three')}
print()
print('== 五:路由注册的时机:导入模块时(装饰器执行时)就注册;第一个请求之后再注册会报错')
a = Flask('late'); a.get('/ok')(lambda: 'ok'); a.test_client().get('/ok')
try: a.get('/late')(lambda: 'late')
except AssertionError as e: print('  AssertionError:', str(e).split('\n')[0]); R['late'] = str(e).split('\n')[0]
print()
print('== 六:flask routes 命令:列出注册的路由')
d = __import__('fl').app('f16', {'ra.py': 'from flask import Flask\napp = Flask(__name__)\n@app.get("/users/<int:uid>")\ndef user(uid): return str(uid)\n@app.route("/items", methods=["GET", "POST"])\ndef items(): return "items"\n'})
r = subprocess.run([str(BIN / 'flask'), '--app', 'ra', 'routes'], cwd=d, env=env(d), capture_output=True, text=True); print(r.stdout.rstrip()); R['routes'] = r.stdout.rstrip().split('\n')
save('f16', R)
