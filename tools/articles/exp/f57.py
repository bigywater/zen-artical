import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f57'); R = {}
import datetime as dt, re
from flask import Flask, render_template_string, request
from jinja2 import pass_context
app = Flask('tst'); app.logger.disabled = True
@app.template_test('prime')
def is_prime(n):
    if not isinstance(n, int) or n < 2: return False
    return all(n % i for i in range(2, int(n ** 0.5) + 1))
@app.template_test()
def adult(user): return user.get('age', 0) >= 18
@app.template_test('longer_than')
def longer_than(s, n): return len(str(s)) > n
def is_weekend(d): return d.weekday() >= 5
app.add_template_test(is_weekend, 'weekend')
app.jinja_env.tests['email'] = lambda s: bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.\w+', str(s)))
@app.template_test('mine')
@pass_context
def mine(ctx, obj): return obj.get('owner') == ctx.get('current_user')
def R_(tpl, **kw):
    with app.test_request_context('/'):
        try: return render_template_string(tpl, **kw)
        except Exception as e: return f'{type(e).__name__}: {e}'
print('== 一:自定义测试:{% if x is name %}、is not、带参数的测试(第一个参数是被测试的值)')
for tpl, kw in (('{% if 7 is prime %}7 是质数{% endif %}', {}), ('{% if 8 is prime %}8 是质数{% else %}8 不是质数{% endif %}', {}), ('{{ 11 is prime }}|{{ 12 is not prime }}', {}), ('{{ "hello" is longer_than(3) }}|{{ "hi" is longer_than 3 }}', {}), ('{{ user is adult }}', {'user': {'age': 20}}), ('{{ d is weekend }}', {'d': dt.date(2026, 10, 3)}), ('{{ "a@b.co" is email }}|{{ "nope" is email }}', {}), ('{{ doc is mine }}|{{ other is mine }}', {'doc': {'owner': 'ann'}, 'other': {'owner': 'bob'}, 'current_user': 'ann'})):
    out = R_(tpl, **kw); R.setdefault('use', {})[tpl] = out; print(f'  {tpl:<58} → {out}')
print()
print('== 二:与 select / reject / selectattr 配合:用测试做过滤')
print('  ', R_('{{ [1,2,3,4,5,6,7,8,9,10]|select("prime")|list }}'), '|', R_('{{ [1,2,3,4,5,6,7,8,9,10]|reject("prime")|list }}'), '|', R_('{{ users|selectattr("age", "ge", 18)|map(attribute="name")|list }}', users=[{'name': 'a', 'age': 10}, {'name': 'b', 'age': 30}]))
R['select'] = [R_('{{ [1,2,3,4,5,6,7,8,9,10]|select("prime")|list }}'), R_('{{ [1,2,3,4,5,6,7,8,9,10]|reject("prime")|list }}')]
print('  select("longer_than", 2):', R_('{{ ["a","abc","abcd","xy"]|select("longer_than", 2)|list }}')); R['select_args'] = R_('{{ ["a","abc","abcd","xy"]|select("longer_than", 2)|list }}')
print()
print('== 三:内置测试与 Python 真假值的区别:defined / undefined / none / true / false / sameas / in / string / number / mapping / iterable / callable / divisibleby / even / odd / lower / upper / eq / ge / lt …')
rows = [('0 is defined', '{{ x is defined }}', {'x': 0}), ('缺失 is defined', '{{ x is defined }}', {}), ('x is none(None)', '{{ x is none }}', {'x': None}), ('x is none(0)', '{{ x is none }}', {'x': 0}), ('if x(0)', '{% if x %}真{% else %}假{% endif %}', {'x': 0}), ('x is true(1)', '{{ x is true }}', {'x': 1}), ('x is true(True)', '{{ x is true }}', {'x': True}), ('"" is string', '{{ x is string }}', {'x': ''}), ('x is number(True)', '{{ x is number }}', {'x': True}), ('4 is divisibleby 2', '{{ 4 is divisibleby 2 }}', {}), ('3 is odd', '{{ 3 is odd }}', {}), ('x is mapping', '{{ x is mapping }}', {'x': {'a': 1}}), ('x is iterable(str)', '{{ x is iterable }}', {'x': 'abc'}), ('x is callable', '{{ x is callable }}', {'x': len}), ('1 is eq 1', '{{ 1 is eq 1 }}', {}), ('3 is ge 2', '{{ 3 is ge 2 }}', {}), ('"a" is in ["a","b"]', '{{ "a" is in ["a","b"] }}', {}), ('x is sameas none', '{{ x is sameas none }}', {'x': None})]
R['builtin'] = {}
for label, tpl, kw in rows: out = R_(tpl, **kw); R['builtin'][label] = out; print(f'  {label:<22} → {out}')
print()
print('== 四:出错的情况:测试不存在、测试里抛异常、参数个数不对')
print('  不存在的测试 →', R_('{{ 1 is nope }}')); print('  缺少必需参数 →', R_('{{ "x" is longer_than }}')); print('  给了多余的参数 →', R_('{{ 7 is prime(1) }}')); R['err'] = [R_('{{ 1 is nope }}'), R_('{{ "x" is longer_than }}'), R_('{{ 7 is prime(1) }}')]
print('  对非整数用 prime(自己的函数返回 False 而不抛)→', R_('{{ "abc" is prime }}'), '| 测试里没处理 None 时的报错(这里的 adult 收到 None):', R_('{{ x is adult }}', x=None)); R['none_adult'] = R_('{{ x is adult }}', x=None)
print()
print('== 五:全部内置测试的清单')
names = sorted(app.jinja_env.tests); print('  共', len(names), '个:', ' '.join(names)); R['names'] = names
print()
print('== 六:测试 vs 过滤器 vs 函数:同一个判断用 {{ n|prime }}(过滤器返回布尔)、{{ prime(n) }}(全局函数)、{{ n is prime }}(测试)三种写法的耗时(2 万次渲染为一组,取 3 组中最小的)')
import timeit
app.add_template_filter(is_prime, 'prime_f'); app.add_template_global(is_prime, 'prime_g')
tp = {}
with app.test_request_context('/'):
    for label, tpl in (('n is prime(测试)', '{{ 97 is prime }}'), ('n|prime_f(过滤器)', '{{ 97|prime_f }}'), ('prime_g(n)(全局函数)', '{{ prime_g(97) }}')):
        t = app.jinja_env.from_string(tpl); tp[label] = min(timeit.timeit(lambda: t.render(), number=20000) / 20000 * 1e6 for _ in range(3)); print(f'  {label:<24} {tp[label]:.2f} µs/次')
R['cost'] = tp
save('f57', R)
