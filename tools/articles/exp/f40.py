import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f40'); R = {}
import datetime as dt, decimal, uuid, dataclasses, enum, json
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
app = Flask('js'); app.logger.disabled = True
@dataclasses.dataclass
class P: x: int; y: str
class Color(enum.Enum): RED = 1
class HasHTML:
    def __html__(self): return '<b>x</b>'
class Plain:
    def __init__(self): self.a = 1
@app.get('/j')
def j(): return jsonify(b=2, a=1, 中文='值')
@app.get('/list')
def lst(): return jsonify([1, 2, {'z': 1, 'a': 2}])
@app.get('/one')
def one(): return jsonify({'k': 'v'})
@app.get('/many')
def many(): return jsonify(1, 2, 3)
@app.get('/none')
def none(): return jsonify()
c = app.test_client()
print('== 一:jsonify 的输出:Content-Type、键顺序、非 ASCII、紧凑还是缩进')
for p in ('/j', '/list', '/one', '/many', '/none'):
    r = c.get(p); R.setdefault('out', {})[p] = [r.content_type, r.get_data(as_text=True)]; print(f'  GET {p:<6} → {r.content_type} | {r.get_data(as_text=True)!r}')
print('  app.json 类型:', type(app.json).__name__, '| sort_keys =', app.json.sort_keys, '| ensure_ascii =', app.json.ensure_ascii, '| compact =', app.json.compact, '| mimetype =', app.json.mimetype); R['provider'] = [type(app.json).__name__, app.json.sort_keys, app.json.ensure_ascii, app.json.compact, app.json.mimetype]
print()
print('== 二:debug 与 compact:debug=True 时输出缩进的 JSON(compact 为 None 时由 debug 决定)')
app.debug = True; r = c.get('/j'); print('  app.debug=True:', repr(r.get_data(as_text=True))); R['debug_out'] = r.get_data(as_text=True); app.debug = False
print()
print('== 三:各种 Python 类型的序列化结果(app.json.dumps)')
vals = [('datetime', dt.datetime(2026, 10, 2, 12, 30, 45, tzinfo=dt.timezone.utc)), ('naive datetime', dt.datetime(2026, 10, 2, 12, 30, 45)), ('date', dt.date(2026, 10, 2)), ('time', dt.time(12, 30)), ('UUID', uuid.UUID(int=255)), ('Decimal', decimal.Decimal('1.10')), ('dataclass', P(1, 'a')), ('__html__ 对象', HasHTML()), ('Enum', Color.RED), ('set', {1, 2}), ('tuple', (1, 2)), ('bytes', b'ab'), ('complex', 1 + 2j), ('普通对象', Plain()), ('float nan', float('nan')), ('float inf', float('inf')), ('大整数', 2 ** 70), ('键是 int', {1: 'a'}), ('键是 tuple', {(1, 2): 'a'})]
R['types'] = {}
with app.app_context():
    for k, v in vals:
        try: o = app.json.dumps(v)
        except Exception as e: o = f'{type(e).__name__}: {str(e)[:70]}'
        R['types'][k] = o; print(f'  {k:<14} → {o}')
print()
print('== 四:自定义序列化:换 json provider,让 set、bytes、自定义对象可序列化;sort_keys=False 保持插入顺序')
class MyProvider(DefaultJSONProvider):
    sort_keys = False
    @staticmethod
    def default(o):
        if isinstance(o, set): return sorted(o)
        if isinstance(o, bytes): return o.decode('latin-1')
        if hasattr(o, '__dict__'): return vars(o)
        return DefaultJSONProvider.default(o)
b = Flask('js2'); b.json = MyProvider(b); b.add_url_rule('/x', 'x', lambda: jsonify(z=1, a={3, 1, 2}, raw=b'ab', obj=Plain()))
r = b.test_client().get('/x'); print('  自定义 provider:', r.get_data(as_text=True).strip()); R['custom'] = r.get_data(as_text=True).strip()
print()
print('== 五:返回 dict/list 与 jsonify 的区别:直接返回 dict 内部也是调用 app.json.response()')
a2 = Flask('js3'); a2.add_url_rule('/d', 'd', lambda: {'b': 1, 'a': 2}); a2.add_url_rule('/jj', 'jj', lambda: jsonify({'b': 1, 'a': 2}))
x, y = a2.test_client().get('/d'), a2.test_client().get('/jj'); print('  return dict →', x.get_data(as_text=True).strip(), '| jsonify →', y.get_data(as_text=True).strip(), '| 完全相同:', x.get_data() == y.get_data() and x.headers['Content-Type'] == y.headers['Content-Type']); R['same'] = x.get_data() == y.get_data()
print()
print('== 六:序列化耗时:一个 1000 个对象的列表,flask.json.dumps vs 标准库 json.dumps(sort_keys 影响)')
import timeit
data = [{'id': i, 'name': f'user{i}', 'tags': ['a', 'b'], 'score': i * 1.5, 'active': i % 2 == 0} for i in range(1000)]
with app.app_context():
    t1 = min(timeit.timeit(lambda: app.json.dumps(data), number=200) / 200 * 1e3 for _ in range(3)); app.json.sort_keys = False; t2 = min(timeit.timeit(lambda: app.json.dumps(data), number=200) / 200 * 1e3 for _ in range(3)); app.json.sort_keys = True
t3 = min(timeit.timeit(lambda: json.dumps(data), number=200) / 200 * 1e3 for _ in range(3)); t4 = min(timeit.timeit(lambda: json.dumps(data, separators=(',', ':')), number=200) / 200 * 1e3 for _ in range(3))
print(f'  app.json.dumps(sort_keys=True,默认)  {t1:.3f} ms;sort_keys=False  {t2:.3f} ms;标准库 json.dumps  {t3:.3f} ms;标准库紧凑分隔符 {t4:.3f} ms;输出长度 {len(app.json.dumps(data)) if False else len(json.dumps(data, separators=(",", ":")))} 字节'); R['cost'] = [t1, t2, t3, t4]
save('f40', R)
