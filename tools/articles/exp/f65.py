import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f65'); R = {}
import timeit, datetime as dt, time
from jinja2 import Environment, DictLoader
from flask import Flask, render_template_string
N = 1000
rows = [{'id': i, 'name': f'user{i}', 'price': i * 1.5, 'created': dt.datetime(2026, 1, 1) + dt.timedelta(hours=i), 'tags': ['a', 'b', 'c']} for i in range(N)]
class Row:
    def __init__(self, d): self.__dict__.update(d)
    @property
    def label(self): return f'#{self.id} {self.name}'
    def price_text(self): return f'¥{self.price:,.2f}'
objs = [Row(r) for r in rows]
calls = {'n': 0}
def fmt_price(p): calls['n'] += 1; return f'¥{p:,.2f}'
def fmt_date(d): return d.strftime('%Y-%m-%d %H:%M')
T = {
 'plain.html': '{% for r in rows %}<tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.price }}</td></tr>{% endfor %}',
 'func.html': '{% for r in rows %}<tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ fmt_price(r.price) }}</td></tr>{% endfor %}',
 'filter.html': '{% for r in rows %}<tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.price|fmt }}</td></tr>{% endfor %}',
 'precomp.html': '{% for r in rows %}<tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.price_text }}</td></tr>{% endfor %}',
 'method.html': '{% for r in objs %}<tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.price_text() }}</td></tr>{% endfor %}',
 'prop.html': '{% for r in objs %}<tr><td>{{ r.label }}</td><td>{{ r.price }}</td></tr>{% endfor %}',
 'attr_chain.html': '{% for r in rows %}{{ r.tags[0] }}{{ r.tags|length }}{{ r.tags|join(",") }}{% endfor %}',
 'builtin_filters.html': '{% for r in rows %}{{ r.name|upper }}{{ r.name|title }}{{ r.name|length }}{{ r.name|replace("user", "u") }}{% endfor %}',
 'date_filter.html': '{% for r in rows %}{{ r.created|fdate }}{% endfor %}',
 'macro.html': '{% macro cell(v) %}<td>{{ v }}</td>{% endmacro %}{% for r in rows %}<tr>{{ cell(r.id) }}{{ cell(r.name) }}{{ cell(r.price) }}</tr>{% endfor %}',
 'include.html': '{% for r in rows %}<tr>{% include "row.html" %}</tr>{% endfor %}', 'row.html': '<td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.price }}</td>',
 'set.html': '{% for r in rows %}{% set p = r.price * 2 %}{{ p }}{{ p }}{{ p }}{% endfor %}',
 'noset.html': '{% for r in rows %}{{ r.price * 2 }}{{ r.price * 2 }}{{ r.price * 2 }}{% endfor %}',
 'filter_chain.html': '{% for r in rows %}{{ r.name|upper|lower|title|trim }}{% endfor %}',
 'loop_vars.html': '{% for r in rows %}{{ loop.index }}{{ loop.first }}{% endfor %}',
 'no_loop_vars.html': '{% for r in rows %}x{% endfor %}',
 'if_heavy.html': '{% for r in rows %}{% if r.id % 2 == 0 %}{% if r.price > 100 %}a{% else %}b{% endif %}{% else %}c{% endif %}{% endfor %}',
 'select.html': '{% for r in rows|selectattr("price", "gt", 500)|list %}{{ r.id }}{% endfor %}',
 'sort.html': '{% for r in rows|sort(attribute="price", reverse=true) %}{{ r.id }}{% endfor %}',
}
env = None
rows_pre = [dict(r, price_text=fmt_price(r['price'])) for r in rows]
print(f'== 一:渲染 {N} 行的表格,三列输出完全相同,只是第三列(价格文本)的来源不同(ms;3 组取最小,每组 15 次)')
def tm(name, **kw):
    t = env.get_template(name); return min(timeit.timeit(lambda: t.render(**kw), number=15) / 15 * 1e3 for _ in range(3))
T['plain_text.html'] = '{% for r in rows %}<tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.price_text }}</td></tr>{% endfor %}'
env = Environment(loader=DictLoader(T), autoescape=True); env.globals['fmt_price'] = fmt_price; env.filters['fmt'] = fmt_price; env.filters['fdate'] = fmt_date
base = tm('precomp.html', rows=rows_pre); R['base'] = base; R['rows'] = {}
def row(label, name, **kw):
    t = tm(name, **kw); R['rows'][label] = t; print(f'  {label:<44} {t:7.3f} ms  ({t / base:5.2f}×)')
print(f'  {"预先在 Python 里算好 r.price_text(基线)":<44} {base:7.3f} ms  ( 1.00×)')
row('全局函数 fmt_price(r.price)', 'func.html', rows=rows); row('过滤器 r.price|fmt', 'filter.html', rows=rows); row('对象方法 r.price_text()', 'method.html', objs=objs)
print()
print('== 二:同样输出的不同结构:直接写 vs macro vs include(每行三个单元格)')
base2 = tm('plain.html', rows=rows); R['base2'] = base2; R['struct'] = {}
print(f'  {"直接写":<44} {base2:7.3f} ms  ( 1.00×)')
for label, name in (('macro cell() 每行 3 次调用', 'macro.html'), ('每行 include 一个模板', 'include.html')):
    t = tm(name, rows=rows); R['struct'][label] = t; print(f'  {label:<44} {t:7.3f} ms  ({t / base2:5.2f}×)')
print()
print('== 三:成对对比:{% set %} 算一次用三次 vs 同一个表达式写三遍')
t_set = tm('set.html', rows=rows); t_noset = tm('noset.html', rows=rows); R['set'] = [t_set, t_noset]; print(f'  set:{t_set:.3f} ms;不 set(算三遍):{t_noset:.3f} ms;不 set 是 set 的 {t_noset / t_set:.2f} 倍')
print()
print('== 三b:selectattr / sort 在模板里做 vs 在 Python 里先做好再渲染(输出相同)')
T['sel_pre.html'] = '{% for r in rows %}{{ r.id }}{% endfor %}'; env = Environment(loader=DictLoader(T), autoescape=True); env.globals['fmt_price'] = fmt_price; env.filters['fmt'] = fmt_price; env.filters['fdate'] = fmt_date
t_in = tm('select.html', rows=rows); pre = [r for r in rows if r['price'] > 500]; t_pre = tm('sel_pre.html', rows=pre); R['select'] = [t_in, t_pre]
t_in2 = tm('sort.html', rows=rows); pre2 = sorted(rows, key=lambda r: r['price'], reverse=True); t_pre2 = tm('sel_pre.html', rows=pre2); R['sort'] = [t_in2, t_pre2]
print(f'  selectattr(price>500):模板里做 {t_in:.3f} ms;Python 里先过滤再渲染 {t_pre:.3f} ms(这一步 Python 过滤本身另需约 0.03 ms)'); print(f'  sort(price 降序):模板里做 {t_in2:.3f} ms;Python 里先排序再渲染 {t_pre2:.3f} ms')
print('== 四:调用次数:fmt_price 在 3 行里被调用了几次(验证「函数每行都调用」)')
calls['n'] = 0; env.get_template('func.html').render(rows=rows[:3]); print('  渲染 3 行,全局函数调用', calls['n'], '次'); R['calls3'] = calls['n']
calls['n'] = 0; env.get_template('func.html').render(rows=rows); print(f'  渲染 {N} 行,全局函数调用', calls['n'], '次'); R['callsN'] = calls['n']
print()
print('== 五:把慢函数放进模板的后果:函数里有 0.1 ms 的开销(模拟一次缓存或数据库往返),渲染 200 行')
def slow(p): time.sleep(0.0001); return p
env.globals['slow'] = slow; env2 = Environment(loader=DictLoader({'s.html': '{% for r in rows %}{{ slow(r.price) }}{% endfor %}', 'n.html': '{% for r in rows %}{{ r.price }}{% endfor %}'}), autoescape=True); env2.globals['slow'] = slow
r200 = rows[:200]; ts = min(timeit.timeit(lambda: env2.get_template('s.html').render(rows=r200), number=3) / 3 * 1e3 for _ in range(2)); tn = min(timeit.timeit(lambda: env2.get_template('n.html').render(rows=r200), number=30) / 30 * 1e3 for _ in range(2))
print(f'  不调用慢函数 {tn:.3f} ms;每行调用一次慢函数 {ts:.2f} ms(约 {ts / tn:.0f} 倍);200 行 × 0.1 ms ≈ 20 ms 的纯等待(sleep 实际约 0.15 ms)'); R['slow'] = [tn, ts]
save('f65', R)
