import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f53'); R = {}
import timeit
from jinja2 import Environment, DictLoader, TemplateSyntaxError
T = {
 'base.html': '<html>\n<title>{% block title %}默认标题{% endblock %}</title>\n<body>\n{% block content %}基础内容{% endblock %}\n<footer>{% block footer %}© base{% endblock %}</footer>\n</body></html>',
 'child.html': '{% extends "base.html" %}\n{% block title %}子页面 - {{ super() }}{% endblock %}\n{% block content %}<h1>{{ heading }}</h1>{% endblock %}',
 'grand.html': '{% extends "child.html" %}\n{% block content %}{{ super() }}<p>孙页面追加</p>{% endblock %}\n{% block footer %}孙页脚|{{ super() }}{% endblock %}',
 'nested.html': '{% block outer %}[外 {% block inner %}内默认{% endblock %}]{% endblock %}',
 'nested_child.html': '{% extends "nested.html" %}{% block inner %}内被覆盖{% endblock %}',
 'noblock_child.html': '{% extends "base.html" %}只写了文字,没有任何 block',
 'scoped_base.html': '{% for x in items %}{% block item scoped %}默认 {{ x }}{% endblock %}|{% endfor %}',
 'scoped_child.html': '{% extends "scoped_base.html" %}{% block item %}子 {{ x }}{% endblock %}',
 'unscoped_base.html': '{% for x in items %}{% block item %}默认 {{ x|default("未定义") }}{% endblock %}|{% endfor %}',
 'unscoped_child.html': '{% extends "unscoped_base.html" %}{% block item %}子 {{ x|default("未定义") }}{% endblock %}',
 'self_block.html': '<title>{% block title %}页面{% endblock %}</title><h1>{{ self.title() }}</h1>',
 'dyn_child.html': '{% extends layout %}{% block content %}动态布局内容{% endblock %}',
 'alt_layout.html': '<main>{% block content %}{% endblock %}</main>',
 'child_text_before.html': '前面有文字\n{% extends "base.html" %}',
 'vars_base.html': '[{{ shared }}]{% block b %}{% endblock %}',
 'vars_child.html': '{% extends "vars_base.html" %}{% set shared = "子里 set" %}{% block b %}b:{{ shared }}{% endblock %}',
 'inc_main.html': '主{% include "inc_part.html" %}|{% include "inc_part.html" without context %}|{% include "nope.html" ignore missing %}',
 'inc_part.html': '<{{ v|default("无v") }}>',
}
env = Environment(loader=DictLoader(T)); R['out'] = {}
def r(name, **kw):
    try: return env.get_template(name).render(**kw)
    except Exception as e: return f'{type(e).__name__}: {e}'
print('== 一:基本继承:子模板只覆盖想改的 block;super() 取父模板里的内容')
src_ = {k: T[k] for k in ('base.html', 'child.html')}
for k, v in src_.items(): print(f'  [{k}]', v.replace('\n', '\n     '))
out = r('child.html', heading='你好'); print('  渲染 child.html →', repr(out)); R['out']['child'] = out
print()
print('== 二:多级继承:grand → child → base;super() 逐级向上')
out = r('grand.html', heading='你好'); print('  渲染 grand.html →', repr(out)); R['out']['grand'] = out
print()
print('== 三:嵌套 block:覆盖内层 block 时外层仍然保留;子模板里 block 之外的内容会被忽略')
out = r('nested_child.html'); print('  nested_child →', repr(out)); R['out']['nested'] = out
out = r('noblock_child.html'); print('  只有文字的子模板 →', repr(out)); R['out']['noblock'] = out
print()
print('== 四:循环里的 block 与变量作用域:默认看不到循环变量;加 scoped 才行')
out1 = r('unscoped_child.html', items=[1, 2]); out2 = r('scoped_child.html', items=[1, 2]); print('  没有 scoped:', repr(out1)); print('  scoped     :', repr(out2)); R['out']['unscoped'] = out1; R['out']['scoped'] = out2
print()
print('== 五:self.block 名():在同一个模板里复用某个 block 的渲染结果(例如 <title> 与 <h1> 保持一致)')
out = r('self_block.html'); print('  ', repr(out)); R['out']['self'] = out
print()
print('== 六:动态继承:{% extends layout %} 的 layout 是变量(可以是模板名或模板对象)')
for lay in ('alt_layout.html', 'base.html'): out = r('dyn_child.html', layout=lay); print(f'  layout={lay!r:<18} →', repr(out)); R['out'][f'dyn_{lay}'] = out
print('  layout 缺失 →', r('dyn_child.html')[:100]); R['out']['dyn_missing'] = r('dyn_child.html')[:100]
print()
print('== 七:extends 前面写了文字会怎样;子模板顶层的 set 对父模板可见;include 的 context 选项')
print('  extends 前面有文字(不会报错,文字照样输出):', r('child_text_before.html')[:80].replace('\n', '\\n')); R['out']['extends_after_text'] = r('child_text_before.html')[:80]
out = r('vars_child.html'); print('  子模板里 {% set %} 对父模板:', repr(out), '(子模板顶层的 set 在父模板渲染前执行,父模板读到了它)'); R['out']['vars'] = out
out = r('inc_main.html', v=1); print('  include 默认带 context;without context 看不到 v;ignore missing 跳过缺失:', repr(out)); R['out']['include'] = out
print()
print('== 八:继承的深度成本:同一个页面用 0 / 3 / 10 层继承渲染(每层只改一个 block)')
chain = {'L0.html': '<html>{% block b %}内容{% endblock %}</html>'}
for i in range(1, 11): chain[f'L{i}.html'] = '{% extends "L' + str(i - 1) + '.html" %}{% block b %}[L' + str(i) + ']{{ super() }}{% endblock %}'
e2 = Environment(loader=DictLoader(chain)); R['depth'] = {}
for n in (0, 3, 10):
    t = e2.get_template(f'L{n}.html'); tt = min(timeit.timeit(lambda: t.render(), number=3000) / 3000 * 1e6 for _ in range(3)); R['depth'][n] = tt; print(f'  {n:>2} 层继承:渲染 {tt:.1f} µs')
save('f53', R)
