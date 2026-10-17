import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f56'); R = {}
import datetime as dt, timeit
from flask import Flask, Blueprint, render_template_string, request, url_for
from jinja2 import DictLoader, pass_context
from markupsafe import Markup
app = Flask('glb'); app.logger.disabled = True; app.secret_key = 'k'
@app.template_global()
def utcnow(): return dt.datetime(2026, 10, 2, 12, 0, 0, tzinfo=dt.timezone.utc)
@app.template_global('site_url')
def make_site_url(path): return 'https://example.test' + path
def initials(name): return ''.join(w[0] for w in name.split()).upper()
app.add_template_global(initials, 'initials')
app.jinja_env.globals['SITE_NAME'] = 'bigywater'
app.jinja_env.globals['VERSION'] = (1, 2, 3)
@app.template_global()
@pass_context
def current_path(ctx): return request.path + '|' + str(ctx.get('title', '无标题'))
bp = Blueprint('b', __name__)
@bp.app_template_global('from_bp')
def from_bp(): return 'bp 注册的全局函数'
app.register_blueprint(bp)
ctx_calls = {'n': 0}
@app.context_processor
def cp():
    ctx_calls['n'] += 1; return {'ctx_var': '来自上下文处理器'}
def R_(tpl, **kw):
    with app.test_request_context('/page'):
        try: return render_template_string(tpl, **kw)
        except Exception as e: return f'{type(e).__name__}: {e}'
print('== 一:全局函数与全局值:调用、取值、链式')
for tpl in ('{{ utcnow().year }}', '{{ site_url("/a") }}', '{{ initials("张 三 四") }}', '{{ SITE_NAME }} v{{ VERSION|join(".") }}', '{{ from_bp() }}', '{{ current_path() }}', '{{ current_path() }}', '{{ utcnow }}'): out = R_(tpl, title='T') if 'current_path' in tpl else R_(tpl); R.setdefault('use', {})[tpl] = out; print(f'  {tpl:<36} → {out}')
print()
print('== 二:全局变量与上下文变量:渲染时传进来的同名变量优先于全局')
@app.get('/shadow')
def shadow(): return render_template_string('{{ SITE_NAME }}', SITE_NAME='被视图覆盖')
print('  视图里传 SITE_NAME → ', app.test_client().get('/shadow').get_data(as_text=True)); R['shadow'] = app.test_client().get('/shadow').get_data(as_text=True)
print()
print('== 三:关键区别——导入的模板(默认不带上下文)能看到全局,看不到上下文处理器注入的变量')
app.jinja_env.loader = DictLoader({'macros.html': '{% macro show() %}全局:{{ SITE_NAME }}|处理器变量:{{ ctx_var|default("看不到") }}|request:{{ request.path|default("看不到") if request is defined else "request 看不到" }}{% endmacro %}{% macro show_ctx() %}处理器变量:{{ ctx_var|default("看不到") }}{% endmacro %}'})
print('  import … 默认(不带 context)      →', R_('{% from "macros.html" import show %}{{ show() }}')); print('  import … with context           →', R_('{% from "macros.html" import show_ctx with context %}{{ show_ctx() }}')); R['import'] = [R_('{% from "macros.html" import show %}{{ show() }}'), R_('{% from "macros.html" import show_ctx with context %}{{ show_ctx() }}')]
print()
print('== 四:Flask 默认就有的全局:jinja_env.globals 里有哪些')
dflt = sorted(k for k in app.jinja_env.globals if k not in ('utcnow', 'site_url', 'initials', 'SITE_NAME', 'VERSION', 'current_path', 'from_bp')); print('  ', dflt); R['defaults'] = dflt
print()
print('== 五:全局函数每次调用都执行;全局值只在注册时求值一次——时间类的值要用函数')
import time
app.jinja_env.globals['STARTED_AT'] = time.time()
a1 = R_('{{ STARTED_AT }}'); time.sleep(0.05); a2 = R_('{{ STARTED_AT }}'); print('  全局值 STARTED_AT 两次渲染相同:', a1 == a2); R['value_same'] = a1 == a2
app.jinja_env.globals['now_ts'] = time.time; b1 = R_('{{ now_ts() }}'); time.sleep(0.05); b2 = R_('{{ now_ts() }}'); print('  全局函数 now_ts() 两次渲染不同:', b1 != b2); R['func_diff'] = b1 != b2
print()
print('== 六:全局 vs 上下文处理器:哪个更适合放什么(用调用次数量化)——处理器每次渲染都执行一次,不管模板用没用到;全局函数只在被调用时执行')
ctx_calls['n'] = 0; glob_calls = {'n': 0}
def counted(): glob_calls['n'] += 1; return 1
app.jinja_env.globals['counted'] = counted
for _ in range(100): R_('不用任何变量')
print(f'  渲染 100 次不使用变量的模板:处理器执行 {ctx_calls["n"]} 次;全局函数执行 {glob_calls["n"]} 次'); R['counts'] = [ctx_calls['n'], glob_calls['n']]
save('f56', R)
