import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f18'); R = {}
import uuid
from flask import Flask, url_for
a = Flask('conv'); a.logger.disabled = True
def show(rv): return f'{type(rv).__name__}:{rv!r}'
for name, rule in (('s', '/s/<string:v>'), ('i', '/i/<int:v>'), ('f', '/f/<float:v>'), ('p', '/p/<path:v>'), ('u', '/u/<uuid:v>'), ('d', '/d/<v>'), ('any', '/any/<any(cat,dog):v>'), ('i3', '/i3/<int(fixed_digits=3):v>'), ('ir', '/ir/<int(min=1,max=100):v>'), ('si', '/si/<int(signed=True):v>'), ('sl', '/sl/<string(length=3):v>'), ('sm', '/sm/<string(minlength=2,maxlength=4):v>')):
    a.add_url_rule(rule, name, (lambda n: lambda v: show(v))(name))
c = a.test_client()
def probe(name, vals):
    out = {}
    for v in vals: r = c.get(f'/{name}/{v}'); out[v] = r.get_data(as_text=True) if r.status_code == 200 else str(r.status_code)
    return out
print('== 一:内置转换器:每种转换器能匹配什么、视图里收到什么类型(200 = 匹配,404 = 不匹配)')
R['conv'] = {}
cases = [('s', 'string', ['abc', 'a/b', '', '中文']), ('i', 'int', ['5', '007', '-5', '1.5', 'abc', '99999999999999999999']), ('f', 'float', ['1.5', '1', '-1.5', '.5', '1e3']), ('p', 'path', ['a', 'a/b/c', '/x']), ('u', 'uuid', [str(uuid.UUID(int=1)), 'not-a-uuid', '12345678123456781234567812345678']), ('d', '默认(省略转换器)', ['abc', 'a/b'])]
for name, label, vals in cases:
    o = probe(name, vals); R['conv'][label] = o; print(f'  {label}:'); [print(f'    {v!r:<42} → {r}') for v, r in o.items()]
print()
print('== 二:转换器参数:int 的 min/max/fixed_digits/signed,string 的 length/minlength/maxlength,any')
R['args'] = {}
for name, label, vals in (('i3', 'int(fixed_digits=3)', ['007', '7', '1234']), ('ir', 'int(min=1,max=100)', ['0', '1', '100', '101']), ('si', 'int(signed=True)', ['-5', '5']), ('sl', 'string(length=3)', ['abc', 'ab', 'abcd']), ('sm', 'string(minlength=2,maxlength=4)', ['a', 'ab', 'abcd', 'abcde']), ('any', 'any(cat,dog)', ['cat', 'dog', 'fish'])):
    o = probe(name, vals); R['args'][label] = o; print(f'  {label:<32}' + ' | '.join(f'{v!r} → {r}' for v, r in o.items()))
print()
print('== 三:url_for 反向生成时转换器怎么处理值')
with a.test_request_context():
    R['url_for'] = {}
    for label, f in (('int 5', lambda: url_for('i', v=5)), ('int "007"', lambda: url_for('i', v='007')), ('float 1.5', lambda: url_for('f', v=1.5)), ('float 1', lambda: url_for('f', v=1)), ('path "a/b"', lambda: url_for('p', v='a/b')), ('string "a/b"', lambda: url_for('s', v='a/b')), ('string "中文 空格"', lambda: url_for('s', v='中文 空格')), ('uuid 对象', lambda: url_for('u', v=uuid.UUID(int=255))), ('int "abc"', lambda: url_for('i', v='abc')), ('int 超出 max', lambda: url_for('ir', v=500))):
        try: R['url_for'][label] = f()
        except Exception as e: R['url_for'][label] = f'{type(e).__name__}: {" ".join(str(e).split())[:90]}'
        print(f'    {label:<16} → {R["url_for"][label]}')
print()
print('== 四:转换器类与正则(取自 werkzeug.routing.converters)')
from werkzeug.routing import converters as C
for nm in ('UnicodeConverter', 'IntegerConverter', 'FloatConverter', 'PathConverter', 'UUIDConverter', 'AnyConverter'):
    k = getattr(C, nm); print(f'  {nm:<17} regex = {getattr(k, "regex", "(动态生成)")!r:<40} weight = {getattr(k, "weight", None)}')
R['regex'] = {nm: [str(getattr(getattr(C, nm), 'regex', None)), getattr(getattr(C, nm), 'weight', None)] for nm in ('UnicodeConverter', 'IntegerConverter', 'FloatConverter', 'PathConverter', 'UUIDConverter')}
print('  默认注册的名字:', sorted(a.url_map.converters)); R['names'] = sorted(a.url_map.converters)
save('f18', R)
