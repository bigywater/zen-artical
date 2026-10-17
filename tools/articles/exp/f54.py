import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f54'); R = {}
import time, timeit
from flask import Flask, Blueprint, render_template_string, render_template, request, session, g, current_app
app = Flask('cp'); app.logger.disabled = True; app.secret_key = 'k'
calls = {'n': 0}
@app.context_processor
def inject():
    calls['n'] += 1; return {'site_name': 'bigywater', 'now_called': calls['n'], 'util': lambda x: x * 2}
@app.context_processor
def second(): return {'site_name': '被第二个覆盖'}
bp = Blueprint('b', __name__, url_prefix='/b')
@bp.context_processor
def bp_ctx(): return {'bp_only': 'blueprint 的变量'}
@bp.app_context_processor
def bp_app_ctx(): return {'bp_global': 'bp 注册的全局变量'}
@bp.get('/t')
def bpt(): return render_template_string('{{ bp_only|default("无") }}|{{ bp_global|default("无") }}')
@app.get('/t')
def t(): return render_template_string('{{ bp_only|default("无") }}|{{ bp_global|default("无") }}')
app.register_blueprint(bp)
@app.get('/names')
def names(): return render_template_string('{% for k in ("config","request","session","g","url_for","get_flashed_messages","csrf_token") %}{{ k }}={{ k in self._TemplateReference__context.keys() }};{% endfor %}')
@app.get('/override')
def override(): return render_template_string('{{ site_name }}', site_name='视图里传的')
@app.get('/twice')
def twice(): return render_template_string('{{ now_called }}-{% include "inc.html" %}')
c = app.test_client()
print('== 一:模板里不用传就有的变量(默认上下文处理器注入的)')
@app.get('/defaults')
def defaults(): return render_template_string('config={{ config.__class__.__name__ }}|request={{ request.path }}|session={{ session.__class__.__name__ }}|g={{ g.__class__.__name__ }}|url_for={{ url_for("defaults") }}|flashed={{ get_flashed_messages()|length }}')
print('  GET /defaults →', c.get('/defaults').get_data(as_text=True)); R['defaults'] = c.get('/defaults').get_data(as_text=True)
with app.test_request_context('/'):
    ctx = {}; app.update_template_context(ctx); print('  update_template_context 往空字典里放了:', sorted(ctx)); R['default_keys'] = sorted(ctx)
print('  Flask 自带的上下文处理器:', [f.__name__ for f in app.template_context_processors[None]][:1], '+ 你注册的', len(app.template_context_processors[None]) - 1, '个'); R['n_proc'] = len(app.template_context_processors[None])
print()
print('== 二:自己的上下文处理器:返回字典会合并进每次渲染的上下文;多个处理器按注册顺序合并,后注册的覆盖先注册的')
print('  site_name =', c.get('/override').get_data(as_text=True), '(视图里显式传的优先于处理器)'); R['override'] = c.get('/override').get_data(as_text=True)
print('  不传时的 site_name:', render_template_string.__name__, end=' → ')
with app.test_request_context('/'): print(render_template_string('{{ site_name }}')); R['order'] = render_template_string('{{ site_name }}')
print()
print('== 三:每次渲染都会调用(包括 render_template_string、{% include %} 不再调用):看 calls 计数')
calls['n'] = 0
with app.test_request_context('/'):
    for i in range(3): render_template_string('{{ now_called }}')
print('  渲染 3 次后处理器被调用了', calls['n'], '次'); R['calls'] = calls['n']
calls['n'] = 0
with app.test_request_context('/'): render_template_string('{% for i in range(5) %}{{ now_called }}{% endfor %}')
print('  一次渲染里用 5 次变量,处理器只调用', calls['n'], '次'); R['calls_one'] = calls['n']
print()
print('== 四:蓝图的 context_processor 只对蓝图的视图生效;app_context_processor 对全局生效')
print('  GET /b/t(蓝图的视图)→', c.get('/b/t').get_data(as_text=True)); print('  GET /t(应用的视图)→', c.get('/t').get_data(as_text=True)); R['bp'] = [c.get('/b/t').get_data(as_text=True), c.get('/t').get_data(as_text=True)]
print()
print('== 五:处理器里放函数:模板可以直接调用(惰性求值,只有被调用才执行)')
app2 = Flask('cp2'); app2.logger.disabled = True; exp = {'eager': 0, 'lazy': 0}
@app2.context_processor
def eager_proc(): exp['eager'] += 1; return {'e_value': sum(range(1000))}
@app2.context_processor
def lazy_proc():
    def f(): exp['lazy'] += 1; return sum(range(1000))
    return {'l_value': f}
@app2.get('/no-use')
def no_use(): return render_template_string('页面没有用到这两个变量')
@app2.get('/use')
def use(): return render_template_string('{{ l_value() }}')
c2 = app2.test_client()
for _ in range(3): c2.get('/no-use')
print('  渲染 3 次「没用到变量」的页面:eager 处理器执行', exp['eager'], '次(无论用不用都算);lazy 的函数执行', exp['lazy'], '次'); R['lazy'] = [exp['eager'], exp['lazy']]
c2.get('/use'); print('  再渲染 1 次「用到 l_value()」的页面:lazy 函数执行', exp['lazy'], '次'); R['lazy2'] = exp['lazy']
print()
print('== 六:处理器的耗时:每个请求都要执行——放 10 个空处理器 vs 放 10 个数据库式的慢处理器(0.5 ms)')
def timed(app_):
    cc = app_.test_client(); cc.get('/x'); return min(timeit.timeit(lambda: cc.get('/x'), number=1000) / 1000 * 1e6 for _ in range(3))
res = {}
for label, delay, n in (('0 个处理器', 0, 0), ('10 个空处理器', 0, 10), ('10 个各 0.5 ms 的处理器', 0.0005, 10)):
    a = Flask('t'); a.logger.disabled = True
    for i in range(n): a.context_processor((lambda dd: lambda: (time.sleep(dd) if dd else None, {})[1])(delay))
    a.add_url_rule('/x', 'x', lambda: render_template_string('x')); res[label] = timed(a) if delay == 0 else min(timeit.timeit(lambda: a.test_client().get('/x'), number=20) / 20 * 1e6 for _ in range(2))
    print(f'  {label:<24} 每个请求 {res[label]:.0f} µs')
R['cost'] = res
save('f54', R)
