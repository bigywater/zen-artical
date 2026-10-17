import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f101'); R = {}
import datetime as dt, decimal, uuid, time
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
app = Flask('j'); app.logger.disabled = True
@app.get('/dict')
def r_dict(): return {'b': 1, 'a': '中文', 'c': [1, 2]}
@app.get('/jsonify')
def r_jsonify(): return jsonify(b=1, a='中文')
@app.get('/list')
def r_list(): return [1, 2, {'x': 1}]
@app.get('/tuple')
def r_tuple(): return {'id': 7}, 201, {'Location': '/items/7'}
@app.get('/types')
def r_types(): return {'when': dt.datetime(2026, 1, 2, 3, 4, 5), 'day': dt.date(2026, 1, 2), 'price': decimal.Decimal('1.10'), 'id': uuid.UUID('12345678123456781234567812345678')}
@app.get('/set')
def r_set(): return {'s': {1, 2}}
@app.post('/echo')
def echo(): return {'got': request.get_json()}
@app.post('/echo-silent')
def echo_s(): return {'got': request.get_json(silent=True)}
@app.post('/echo-force')
def echo_f(): return {'got': request.get_json(force=True)}
@app.get('/none')
def r_none(): return None
@app.get('/str')
def r_str(): return 'plain'
c = app.test_client(); app.config['PROPAGATE_EXCEPTIONS'] = False
def show(label, r, body=True): print(f'  {label:<34} → {r.status_code} {r.headers.get("Content-Type")}' + (f' | {r.get_data(as_text=True).strip()[:110]}' if body else '')); return r
print('== 一:视图直接返回 dict / list / jsonify')
R['dict'] = show('return {...}', c.get('/dict')).get_data(as_text=True).strip(); show('return jsonify(...)', c.get('/jsonify')); R['list'] = show('return [...](顶层列表)', c.get('/list')).get_data(as_text=True).strip()
r = show('return {...}, 201, {Location}', c.get('/tuple')); print('    Location 头:', r.headers.get('Location')); R['tuple'] = [r.status_code, r.headers.get('Location')]
print('  当前默认值:app.json.sort_keys =', app.json.sort_keys, '| ensure_ascii =', app.json.ensure_ascii, '| compact =', app.json.compact, '| mimetype =', app.json.mimetype); R['defaults'] = [app.json.sort_keys, app.json.ensure_ascii, app.json.compact, app.json.mimetype]
print()
print('== 二:能序列化哪些类型')
r = show('datetime / date / Decimal / UUID', c.get('/types')); R['types'] = r.get_data(as_text=True).strip()
r = show('set(默认不支持)', c.get('/set'), body=False); print('    状态码 500,响应是 HTML 错误页(不是 JSON)'); R['set'] = r.status_code
print()
print('== 三:读请求体:request.get_json() 的各种情况')
cases = [('Content-Type: application/json + 合法 JSON', dict(data='{"a": 1}', content_type='application/json')), ('Content-Type: application/json + 非法 JSON', dict(data='{"a": ', content_type='application/json')),
         ('Content-Type: text/plain + 合法 JSON', dict(data='{"a": 1}', content_type='text/plain')), ('没有 Content-Type + 合法 JSON', dict(data='{"a": 1}')), ('application/json + 空请求体', dict(data='', content_type='application/json'))]
R['body'] = {}
for label, kw in cases:
    r = c.post('/echo', **kw); print(f'  {label:<42} → {r.status_code} {r.get_data(as_text=True).strip()[:60].splitlines()[0] if r.status_code == 200 else r.get_data(as_text=True).strip().replace(chr(10), " ")[:96]}'); R['body'][label] = r.status_code
r = c.post('/echo-silent', data='{"a": ', content_type='application/json'); print('  silent=True + 非法 JSON →', r.status_code, r.get_data(as_text=True).strip()); R['silent'] = [r.status_code, r.get_data(as_text=True).strip()]
r = c.post('/echo-force', data='{"a": 1}', content_type='text/plain'); print('  force=True + text/plain →', r.status_code, r.get_data(as_text=True).strip()); R['force'] = [r.status_code, r.get_data(as_text=True).strip()]
r = c.post('/echo', json={'a': 1}); print('  test_client 的 json= 参数 →', r.status_code, r.get_data(as_text=True).strip())
print()
print('== 四:返回 None 与字符串')
r = show('return None', c.get('/none'), body=False); print('    ', r.get_data(as_text=True).strip().replace('\n', ' ')[:130]); R['none'] = r.status_code
show('return "plain"', c.get('/str'))
print()
print('== 五:自定义 JSON 序列化:子类化 DefaultJSONProvider 支持 set,并改成中文不转义、不排序')
class MyProvider(DefaultJSONProvider):
    ensure_ascii = False; sort_keys = False
    @staticmethod
    def default(o):
        if isinstance(o, (set, frozenset)): return sorted(o)
        return DefaultJSONProvider.default(o)
app2 = Flask('j2'); app2.json = MyProvider(app2)
@app2.get('/x')
def x(): return {'b': 1, 'a': '中文', 's': {2, 1}}
r = app2.test_client().get('/x'); print('  ', r.get_data(as_text=True).strip()); R['custom'] = r.get_data(as_text=True).strip()
print('   (默认 provider 的同一份数据:', c.get('/dict').get_data(as_text=True).strip(), ')')
print()
print('== 六:序列化的开销:返回 1000 个对象的列表,经 Flask 返回与直接 json.dumps(每组 100 次,取 5 组里最小的)')
import json, timeit
data = [{'id': i, 'name': f'user{i}', 'score': i * 1.5, 'tags': ['a', 'b']} for i in range(1000)]
app3 = Flask('j3')
@app3.get('/big')
def big(): return data
c3 = app3.test_client(); c3.get('/big')
t_flask = min(timeit.repeat(lambda: c3.get('/big'), number=100, repeat=5)) / 100 * 1000; t_dumps = min(timeit.repeat(lambda: json.dumps(data), number=100, repeat=5)) / 100 * 1000
print(f'  经 Flask 返回 {t_flask:.2f} ms/次,纯 json.dumps {t_dumps:.2f} ms/次;响应大小 {len(c3.get("/big").data)} 字节'); R['cost'] = [t_flask, t_dumps, len(c3.get('/big').data)]
save('f101', R)
