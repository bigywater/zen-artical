import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f55'); R = {}
import datetime as dt
from flask import Flask, Blueprint, render_template_string, request
from jinja2 import pass_context, pass_environment, pass_eval_context
from markupsafe import Markup, escape
app = Flask('flt'); app.logger.disabled = True
@app.template_filter('money')
def money(v, symbol='¥', digits=2): return f'{symbol}{v:,.{digits}f}'
@app.template_filter()
def shout(s): return str(s).upper() + '!'
def reverse_words(s): return ' '.join(reversed(str(s).split()))
app.add_template_filter(reverse_words, 'rw')
app.jinja_env.filters['double'] = lambda x: x * 2
@app.template_filter('bold')
def bold(s): return f'<b>{s}</b>'
@app.template_filter('bold_safe')
def bold_safe(s): return Markup('<b>{}</b>').format(s)
@app.template_filter('bold_wrong')
def bold_wrong(s): return Markup(f'<b>{s}</b>')
@app.template_filter('who')
@pass_context
def who(ctx, s): return f'{s}@{ctx.get("user", "匿名")}'
@app.template_filter('ctx_path')
@pass_context
def ctx_path(ctx, s): return f'{s}:{request.path}'
@app.template_filter('envname')
@pass_environment
def envname(env, s): return f'{s}|autoescape={env.autoescape.__name__ if callable(env.autoescape) else env.autoescape}'
@app.template_filter('boom')
def boom(s): raise ValueError('过滤器里出错了')
@app.template_filter('nonestr')
def nonestr(v): return f'type={type(v).__name__}'
bp = Blueprint('b', __name__)
@bp.app_template_filter('bpf')
def bpf(s): return f'bp:{s}'
app.register_blueprint(bp)
def R_(tpl, **kw):
    with app.test_request_context('/path'):
        try: return render_template_string(tpl, **kw)
        except Exception as e: return f'{type(e).__name__}: {e}'
print('== 一:四种注册方式:装饰器(带名字、不带名字用函数名)、add_template_filter、直接写 jinja_env.filters、蓝图的 app_template_filter')
for tpl in ('{{ 1234567.891|money }}', '{{ 1234567.891|money("$", 0) }}', '{{ "hi"|shout }}', '{{ "a b c"|rw }}', '{{ 21|double }}', '{{ "x"|bpf }}', '{{ 3|money(digits=1)|shout }}'): out = R_(tpl); R.setdefault('reg', {})[tpl] = out; print(f'  {tpl:<38} → {out}')
print()
print('== 二:过滤器接收「被过滤的值」作第一个参数,其余参数来自模板;链式调用左到右')
print('  filters 里自定义的与内置的总数:', len(app.jinja_env.filters), '| 内置', len([k for k in app.jinja_env.filters if k not in ('money', 'shout', 'rw', 'double', 'bold', 'bold_safe', 'bold_wrong', 'who', 'ctx_path', 'envname', 'boom', 'nonestr', 'bpf')]), '个'); R['n_filters'] = len(app.jinja_env.filters)
print()
print('== 三:自动转义与过滤器的返回值:返回普通字符串会被转义;返回 Markup 才被当作 HTML;但 Markup 里拼接用户输入要小心')
user = '<script>alert(1)</script>'
for name in ('bold', 'bold_safe', 'bold_wrong'): out = R_('{{ x|' + name + ' }}', x=user); R.setdefault('esc', {})[name] = out; print(f'  x|{name:<11} (x={user}) → {out}')
print()
print('== 四:带上下文的过滤器:@pass_context 可以读模板变量;@pass_environment 拿到 Environment')
print('  {{ "a"|who }}(模板里有 user=ann)→', R_('{{ "a"|who }}', user='ann')); print('  没有 user →', R_('{{ "a"|who }}')); print('  {{ "a"|ctx_path }} →', R_('{{ "a"|ctx_path }}')); print('  {{ "a"|envname }} →', R_('{{ "a"|envname }}')); R['ctxf'] = [R_('{{ "a"|who }}', user='ann'), R_('{{ "a"|who }}'), R_('{{ "a"|ctx_path }}'), R_('{{ "a"|envname }}')]
print()
print('== 五:边界:None、Undefined、异常')
print('  None 传给过滤器 →', R_('{{ none|nonestr }}')); print('  没定义的变量传给过滤器 →', R_('{{ missing|nonestr }}')); print('  过滤器里抛异常 →', R_('{{ "x"|boom }}')); print('  模板里写了不存在的过滤器 →', R_('{{ "x"|nope }}')); R['edge'] = [R_('{{ none|nonestr }}'), R_('{{ missing|nonestr }}'), R_('{{ "x"|boom }}'), R_('{{ "x"|nope }}')]
print()
print('== 六:注册时机:装饰器注册是 Flask 的「setup 方法」,第一个请求之后不能再用;直接写 jinja_env.filters 不受限制(但不推荐)')
app.add_template_filter(lambda s: s, 'late'); print("  还没处理过请求时 add_template_filter('late') → 成功(test_request_context 与渲染不算「第一个请求」)"); R['before'] = '成功'
app.test_client().get('/nonexistent')
try: app.add_template_filter(lambda s: s, 'late2'); print('  第一个请求之后 add_template_filter → 成功'); R['late2'] = '成功'
except AssertionError as e: print('  第一个请求之后 add_template_filter → AssertionError:', str(e).split('\n')[0][:110]); R['late2'] = str(e).split('\n')[0]
app.jinja_env.filters['direct'] = lambda s: f'direct:{s}'; print('  直接写 jinja_env.filters["direct"] 之后 →', R_('{{ 1|direct }}')); R['direct'] = R_('{{ 1|direct }}')
print()
print('== 七:内置过滤器清单(Jinja 3.1.6 + Flask 添加的 tojson)')
builtin = sorted(k for k in app.jinja_env.filters if k not in ('money', 'shout', 'rw', 'double', 'bold', 'bold_safe', 'bold_wrong', 'who', 'ctx_path', 'envname', 'boom', 'nonestr', 'bpf', 'direct', 'late')); print('  ', len(builtin), '个:', ' '.join(builtin)); R['builtin'] = builtin
save('f55', R)
