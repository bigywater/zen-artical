import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f51'); R = {}
import time, timeit
import jinja2
from jinja2 import Environment, DictLoader, ChoiceLoader, PrefixLoader, FunctionLoader, FileSystemLoader, TemplateNotFound
from flask import Flask, render_template, render_template_string
d = mkapp('f51', {'templates/hello.html': 'Hello {{ name }}!\n', 'templates/base.html': '<html>{% block body %}{% endblock %}</html>', 'templates/page.html': '{% extends "base.html" %}{% block body %}<p>{{ name }}</p>{% endblock %}'})
sys.path.insert(0, str(d)); os.chdir(d)
app = Flask('ld', root_path=str(d)); app.logger.disabled = True
print('== 一:Flask 的加载器结构:jinja_env.loader 是 DispatchingJinjaLoader,里面再去问应用与各蓝图的加载器')
env = app.jinja_env; print('  app.jinja_env 类型:', type(env).__module__ + '.' + type(env).__name__, '| loader:', type(env.loader).__name__); R['types'] = [type(env).__name__, type(env.loader).__name__]
print('  app.jinja_loader:', type(app.jinja_loader).__name__, '| searchpath:', [p.replace(str(d), '<项目>') for p in app.jinja_loader.searchpath]); R['searchpath'] = [p.replace(str(d), '<项目>') for p in app.jinja_loader.searchpath]
print('  Flask 3.1 对 jinja_env 的默认选项:autoescape =', type(env.autoescape).__name__, '| auto_reload =', env.auto_reload, '| cache_size =', env.cache.capacity, '| trim_blocks =', env.trim_blocks, '| lstrip_blocks =', env.lstrip_blocks, '| undefined =', env.undefined.__name__); R['opts'] = [env.auto_reload, env.cache.capacity, env.trim_blocks, env.undefined.__name__]
print('  jinja_options:', app.jinja_options); R['jinja_options'] = str(app.jinja_options)
print()
print('== 二:加载器的核心方法 get_source(name) → (源码, 文件名, uptodate 函数)')
src_, fn, up = app.jinja_loader.get_source(env, 'hello.html'); print('  源码 =', repr(src_), '| 文件名 =', fn.replace(str(d), '<项目>'), '| uptodate() =', up()); R['gs'] = [src_, up()]
open(d / 'templates' / 'hello.html', 'a').write('x'); print('  文件被修改后 uptodate() =', up(), '(返回 False 表示缓存的编译结果过期了)'); R['gs_after'] = up(); open(d / 'templates' / 'hello.html', 'w').write('Hello {{ name }}!\n')
try: env.get_template('nope.html')
except TemplateNotFound as e: print('  找不到 →', type(e).__name__ + ':', e); R['nf'] = str(e)
print()
print('== 三:各种内置加载器组合(用独立的 jinja2.Environment 演示)')
dl = DictLoader({'a.html': 'A:{{ x }}', 'b.html': 'B'}); e1 = Environment(loader=dl); print('  DictLoader:', e1.get_template('a.html').render(x=1)); R['dict'] = e1.get_template('a.html').render(x=1)
ch = ChoiceLoader([DictLoader({'a.html': '覆盖的 A'}), FileSystemLoader(str(d / 'templates'))]); e2 = Environment(loader=ch); print('  ChoiceLoader:a.html →', e2.get_template('a.html').render(), '| hello.html →', e2.get_template('hello.html').render(name='x').strip()); R['choice'] = [e2.get_template('a.html').render(), e2.get_template('hello.html').render(name='x').strip()]
pl = PrefixLoader({'ui': DictLoader({'btn.html': '<button>'}), 'mail': DictLoader({'btn.html': '邮件按钮'})}); e3 = Environment(loader=pl); print('  PrefixLoader:ui/btn.html →', e3.get_template('ui/btn.html').render(), '| mail/btn.html →', e3.get_template('mail/btn.html').render()); R['prefix'] = [e3.get_template('ui/btn.html').render(), e3.get_template('mail/btn.html').render()]
calls = []
def fl(name): calls.append(name); return (f'来自函数:{name}', None, lambda: True) if name.startswith('dyn/') else None
e4 = Environment(loader=FunctionLoader(fl)); print('  FunctionLoader:dyn/x →', e4.get_template('dyn/x').render(), '| 调用记录', calls); R['func'] = e4.get_template('dyn/x').render()
print()
print('== 四:在 Flask 里换成自己的加载器:ChoiceLoader 加一个目录与一个字典(app.jinja_loader 只管应用自己的目录,蓝图加载器仍然在)')
app2 = Flask('ld2', root_path=str(d)); app2.logger.disabled = True
class Cl(ChoiceLoader): pass
base = app2.jinja_loader
app2.jinja_loader = ChoiceLoader([DictLoader({'hello.html': '被覆盖:{{ name }}'}), base])
@app2.get('/h')
def h(): return render_template('hello.html', name='ann')
@app2.get('/p')
def p(): return render_template('page.html', name='ann')
c2 = app2.test_client(); print('  GET /h →', c2.get('/h').get_data(as_text=True), '| GET /p →', c2.get('/p').get_data(as_text=True)); R['flask_choice'] = [c2.get('/h').get_data(as_text=True), c2.get('/p').get_data(as_text=True)]
print()
print('== 五:模板是怎么变成 Python 的:env.compile(源码, raw=True) 的输出(节选)')
code = env.compile('Hello {{ name }}!{% for i in items %}[{{ i|upper }}]{% endfor %}', raw=True).split('\n'); keep = [l for l in code if l.strip() and not l.startswith('#')]; print('\n'.join('    ' + l for l in keep[:22])); R['compiled'] = keep[:22]
print()
print('== 六:各阶段耗时:词法分析 + 语法分析 + 代码生成 + 编译 vs 渲染(一个 51 行的模板:50 行各含一个过滤器与一个条件,再加一个 20 行的循环)')
tpl_src = '\n'.join(f'<li>{{{{ item{i}|upper }}}} {{% if flag{i} %}}yes{{% else %}}no{{% endif %}}</li>' for i in range(50)) + '\n{% for r in rows %}<tr><td>{{ r.a }}</td><td>{{ r.b|default("-") }}</td></tr>{% endfor %}'
e5 = Environment()
t_parse = min(timeit.timeit(lambda: e5.parse(tpl_src), number=50) / 50 * 1e3 for _ in range(3))
t_compile = min(timeit.timeit(lambda: e5.compile(tpl_src), number=50) / 50 * 1e3 for _ in range(3))
tpl = e5.from_string(tpl_src); ctx = {**{f'item{i}': 'x' for i in range(50)}, **{f'flag{i}': i % 2 for i in range(50)}, 'rows': [{'a': i, 'b': i} for i in range(20)]}
t_render = min(timeit.timeit(lambda: tpl.render(**ctx), number=500) / 500 * 1e3 for _ in range(3))
print(f'  parse(只生成语法树){t_parse:.2f} ms;compile(含代码生成与 Python 编译){t_compile:.2f} ms;已编译后 render {t_render:.3f} ms;编译是渲染的 {t_compile / t_render:.0f} 倍 —— 所以缓存编译结果很重要'); R['cost'] = [t_parse, t_compile, t_render]
save('f51', R)
