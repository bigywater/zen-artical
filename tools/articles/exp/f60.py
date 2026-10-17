import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f60'); R = {}
import timeit
from flask import Flask, render_template_string
from jinja2 import Environment, DictLoader, StrictUndefined
T = {
 'forms.html': '''{% macro input(name, value="", type="text", cls="input") -%}<input type="{{ type }}" name="{{ name }}" value="{{ value }}" class="{{ cls }}">{%- endmacro %}
{% macro card(title) -%}<div class="card"><h3>{{ title }}</h3>{{ caller() }}</div>{%- endmacro %}
{% macro list_all() -%}args={{ varargs|list }}|kwargs={{ kwargs }}{%- endmacro %}
{% macro fact(n) -%}{% if n <= 1 %}1{% else %}{{ n * fact(n - 1)|int }}{% endif %}{%- endmacro %}
{% macro uses_outer() -%}[{{ outer_var|default("看不到 outer_var") }}]{%- endmacro %}
{% macro with_defaults(a, b=2, c=a) -%}a={{ a }},b={{ b }},c={{ c }}{%- endmacro %}''',
 'use.html': '{% import "forms.html" as f %}{{ f.input("user") }}|{{ f.input("pw", type="password", cls="big") }}',
 'use_from.html': '{% from "forms.html" import input, card as panel %}{{ input("a", "<x>") }}|{% call panel("标题") %}正文{{ 1 + 1 }}{% endcall %}',
 'inline.html': '{% macro greet(name="世界") %}你好,{{ name }}{% endmacro %}{{ greet() }}|{{ greet("ann") }}|{{ greet(name="bob") }}',
 'ctx_main.html': '{% set outer_var = "外层变量" %}{% import "forms.html" as f %}{% import "forms.html" as g with context %}{{ f.uses_outer() }}|{{ g.uses_outer() }}',
 'caller_args.html': '{% macro rows(items) %}{% for i in items %}<tr>{{ caller(i, loop.index) }}</tr>{% endfor %}{% endmacro %}{% call(item, idx) rows([10, 20]) %}<td>{{ idx }}:{{ item }}</td>{% endcall %}',
 'esc.html': '{% macro tag(text) %}<b>{{ text }}</b>{% endmacro %}{{ tag("<i>") }}|{{ tag("<i>")|upper }}|{{ tag("<i>")|string|length }}',
 'macro_attrs.html': '{% macro m(a, b=1) %}{{ varargs }}{{ kwargs }}x{% endmacro %}{{ m.name }}|{{ m.arguments }}|{{ m.defaults }}|{{ m.catch_kwargs }}|{{ m.catch_varargs }}|{{ m.caller }}',
 'scope.html': '{% set x = "外层" %}{% macro m() %}{{ x|default("宏里看不到 x") }}{% endmacro %}{{ m() }}',
 'noparen.html': '{% macro m() %}调用{% endmacro %}{{ m }}',
}
env = Environment(loader=DictLoader(T), autoescape=True); R['out'] = {}
def r(name, **kw):
    try: return env.get_template(name).render(**kw)
    except Exception as e: return f'{type(e).__name__}: {e}'
print('== 一:定义与调用:位置参数、关键字参数、默认值;import 为命名空间,from … import 取出来')
print('  宏定义(forms.html 节选):', T['forms.html'].split('\n')[0]); 
for n in ('use.html', 'use_from.html', 'inline.html'): out = r(n); R['out'][n] = out; print(f'  {n:<14} → {out}')
print()
print('== 二:call 块与 caller():把一段内容作为参数传给宏;caller 可以带参数')
for n in ('caller_args.html',): out = r(n); R['out'][n] = out; print(f'  {n:<16} → {out}')
print('  card 宏里用 caller() 包裹正文(见 use_from.html 输出)')
print()
print('== 三:可变参数与递归:宏的签名里不能写 *args/**kwargs(语法错误),但宏体里引用 varargs 与 kwargs 就自动接收多余的位置参数与关键字参数;宏可以递归')
try: Environment().from_string('{% macro m(*args) %}{% endmacro %}')
except Exception as e: print('  在签名里写 *args →', type(e).__name__ + ':', e); R['out']['star'] = f'{type(e).__name__}: {e}'
env.globals['meta_info'] = lambda: ''
print('  list_all(1, 2, k=3) →', env.from_string('{% from "forms.html" import list_all %}{{ list_all(1, 2, k=3) }}').render()); R['out']['varargs'] = env.from_string('{% from "forms.html" import list_all %}{{ list_all(1, 2, k=3) }}').render()
print('  fact(5) →', env.from_string('{% from "forms.html" import fact %}{{ fact(5) }}').render()); R['out']['fact'] = env.from_string('{% from "forms.html" import fact %}{{ fact(5) }}').render()
print('  with_defaults(1) →', env.from_string('{% from "forms.html" import with_defaults %}{{ with_defaults(1) }}').render(), '(默认值表达式可以引用前面的参数)'); R['out']['defaults'] = env.from_string('{% from "forms.html" import with_defaults %}{{ with_defaults(1) }}').render()
print('  宏的属性 name / arguments / defaults / catch_kwargs / catch_varargs / caller:', r('macro_attrs.html')); R['out']['attrs'] = r('macro_attrs.html')
print()
print('== 四:作用域:同一模板里定义的宏能读到该模板顶层的变量;被 import 的宏默认读不到调用方的上下文(with context 才行)')
print('  同一个模板里定义的宏读外层的 {% set x %}:', r('scope.html')); R['out']['scope'] = r('scope.html')
print('  import 默认 vs with context:', r('ctx_main.html')); R['out']['ctx'] = r('ctx_main.html')
print()
print('== 五:宏的输出与自动转义:宏返回 Markup(宏体里的 HTML 不会再被转义),参数在宏体里会被转义')
print('  ', r('esc.html')); R['out']['esc'] = r('esc.html'); print('  不加括号 {{ m }} 输出的是宏对象:', r('noparen.html')); R['out']['noparen'] = r('noparen.html')
print()
print('== 六:宏的开销:渲染 500 行表格,每行 3 个单元格——直接写、宏、include 三种写法')
N = 500; rows = [{'a': i, 'b': f'n{i}', 'c': i * 2} for i in range(N)]
T2 = {
 'direct.html': '{% for r in rows %}<tr><td>{{ r.a }}</td><td>{{ r.b }}</td><td>{{ r.c }}</td></tr>{% endfor %}',
 'macro.html': '{% macro cell(v) %}<td>{{ v }}</td>{% endmacro %}{% for r in rows %}<tr>{{ cell(r.a) }}{{ cell(r.b) }}{{ cell(r.c) }}</tr>{% endfor %}',
 'include.html': '{% for r in rows %}<tr>{% include "cell_row.html" %}</tr>{% endfor %}', 'cell_row.html': '<td>{{ r.a }}</td><td>{{ r.b }}</td><td>{{ r.c }}</td>',
 'imported_macro.html': '{% from "cells.html" import cell %}{% for r in rows %}<tr>{{ cell(r.a) }}{{ cell(r.b) }}{{ cell(r.c) }}</tr>{% endfor %}', 'cells.html': '{% macro cell(v) %}<td>{{ v }}</td>{% endmacro %}',
}
e2 = Environment(loader=DictLoader(T2), autoescape=True); R['cost'] = {}
for n, label in (('direct.html', '直接写'), ('macro.html', '同模板里的宏(1500 次调用)'), ('imported_macro.html', 'import 进来的宏(1500 次调用)'), ('include.html', '每行 include 一个模板(500 次)')):
    t = e2.get_template(n); R['cost'][label] = min(timeit.timeit(lambda: t.render(rows=rows), number=30) / 30 * 1e3 for _ in range(3)); print(f'  {label:<30} {R["cost"][label]:.3f} ms/次')
base = R['cost']['直接写']; print('  相对直接写:', {k: f'{v / base:.2f}×' for k, v in R['cost'].items()})
save('f60', R)
