import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f163'); R = {}
import statistics, timeit
from flask import Flask, render_template, render_template_string, template_rendered, before_render_template
TPL = {
 'list.html': '<ul>{% for it in items %}<li>{{ it.id }}: {{ it.name }}</li>{% endfor %}</ul>',
 'list_safe.html': '<ul>{% for it in items %}<li>{{ it.id }}: {{ it.name|safe }}</li>{% endfor %}</ul>',
 'row.html': '<li>{{ it.id }}: {{ it.name }}</li>',
 'list_include.html': '<ul>{% for it in items %}{% include "row.html" %}{% endfor %}</ul>',
 'macros.html': '{% macro row(it) %}<li>{{ it.id }}: {{ it.name }}</li>{% endmacro %}',
 'list_macro.html': '{% from "macros.html" import row %}<ul>{% for it in items %}{{ row(it) }}{% endfor %}</ul>',
}
d = mkapp('f163', {f'templates/{k}': v for k, v in TPL.items()} | {'x.py': 'pass'})
def mk(auto_reload=False):
    app = Flask('tr', template_folder=str(d / 'templates')); app.logger.disabled = True; app.config['TEMPLATES_AUTO_RELOAD'] = auto_reload; return app
items = [{'id': i, 'name': f'<b>n{i}</b>'} for i in range(1000)]
def med(fn, n=30): fn(); L = []; [L.append(timeit.timeit(fn, number=1) * 1000) for _ in range(n)]; return statistics.median(L)
print('== 一:第一次渲染要编译模板,之后命中缓存(1000 项的列表)')
app = mk()
with app.test_request_context():
    t0 = time.perf_counter(); render_template('list.html', items=items); first = ms(t0); rest = med(lambda: render_template('list.html', items=items))
print(f'  第一次(含编译){first:.2f} ms | 之后的渲染中位数 {rest:.2f} ms | 编译约占 {first - rest:.2f} ms'); R['first'] = [first, rest]
print()
print('== 二:render_template_string 每次都要重新编译;render_template(文件)只编译一次')
with app.test_request_context():
    src = TPL['list.html']; small = [{'id': 1, 'name': 'x'}]
    f = med(lambda: render_template('list.html', items=small)); s = med(lambda: render_template_string(src, items=small))
print(f'  渲染 1 项的小模板:文件模板 {f * 1000:.0f} µs | render_template_string {s * 1000:.0f} µs(约 {s / f:.0f} 倍)'); R['string'] = [f * 1000, s * 1000]
print()
print('== 三:同样 1000 项,不同写法的渲染耗时:直接循环、|safe(跳过转义)、include、macro')
R['styles'] = {}
with app.test_request_context():
    for label, name in (('直接循环(自动转义)', 'list.html'), ('|safe 跳过转义', 'list_safe.html'), ('每项 {% include %}', 'list_include.html'), ('每项调用 macro', 'list_macro.html')):
        t = med(lambda: render_template(name, items=items)); print(f'  {label:<22} {t:7.2f} ms'); R['styles'][label] = t
print()
print('== 四:TEMPLATES_AUTO_RELOAD(debug 下默认开):每次渲染都检查模板文件有没有改过')
R['reload'] = {}
for label, ar in (('auto_reload=False', False), ('auto_reload=True', True)):
    a = mk(ar)
    with a.test_request_context(): t = med(lambda: render_template('list.html', items=small), n=300); print(f'  {label:<20} 小模板渲染 {t * 1000:.0f} µs'); R['reload'][label] = t * 1000
print()
print('== 五:用 Flask 的模板信号统计每个模板的渲染次数与耗时')
a = mk(); STAT = {}
def before(sender, template, context, **kw): context['_t0'] = time.perf_counter()
def after(sender, template, context, **kw): STAT.setdefault(template.name, []).append((time.perf_counter() - context['_t0']) * 1000)
before_render_template.connect(before, a); template_rendered.connect(after, a)
@a.get('/p')
def p(): return render_template('list_include.html', items=items[:200])
c = a.test_client(); c.get('/p'); c.get('/p')
for name, v in STAT.items(): print(f'  {name:<20} 渲染 {len(v)} 次,单次 {statistics.mean(v):.2f} ms'); R.setdefault('signals', {})[name] = [len(v), statistics.mean(v)]
print('  (信号只在顶层 render_template 触发一次;include 进来的 row.html 不单独触发,它的耗时包含在 list_include.html 里)')
save('f163', R)
