import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f103'); R = {}
import json
from flask import Flask, request, jsonify, abort
app = Flask('v'); app.logger.disabled = True; app.config['PROPAGATE_EXCEPTIONS'] = False; app.config['MAX_CONTENT_LENGTH'] = 1000
@app.get('/int')
def v_int(): return jsonify(n=request.args.get('n', type=int, default='DEFAULT'))
@app.get('/float')
def v_float(): return jsonify(repr=repr(request.args.get('x', type=float)))
@app.get('/bool')
def v_bool(): return jsonify(flag=request.args.get('flag', type=bool))
@app.get('/items/<int:i>')
def v_item(i): return jsonify(i=i)
@app.post('/key')
def v_key(): return jsonify(name=request.json['name'])
@app.post('/size')
def v_size(): return jsonify(n=len(request.get_data()))
@app.post('/form')
def v_form(): return jsonify(k=len(request.form))
@app.get('/list')
def v_list(): return jsonify(ids=request.args.getlist('id', type=int))
def validate(data):
    errs = {}
    if not isinstance(data, dict): return {'_': '请求体必须是 JSON 对象'}
    name = data.get('name')
    if not isinstance(name, str) or not (1 <= len(name) <= 20): errs['name'] = '必填,字符串,1-20 个字符'
    age = data.get('age')
    if not (isinstance(age, int) and not isinstance(age, bool) and 0 <= age <= 150): errs['age'] = '必填,0-150 的整数'
    return errs
@app.post('/user')
def v_user():
    data = request.get_json(silent=True); errs = validate(data)
    if errs: return jsonify(errors=errs), 422
    return jsonify(ok=True, user=data), 201
@app.get('/page')
def v_page():
    limit = max(1, min(request.args.get('limit', 20, type=int), 100)); offset = max(0, request.args.get('offset', 0, type=int)); return jsonify(limit=limit, offset=offset)
c = app.test_client()
def g(p, **kw): r = c.get(p, **kw); return r.status_code, (r.get_json() if r.is_json else r.get_data(as_text=True)[:40])
print('== 一:request.args.get(type=int):转换失败时悄悄回退成默认值(不报错)')
R['int'] = {}
for v in ('12', 'abc', '12abc', ' 12 ', '1_000', '+5', '-5', '١٢', '99999999999999999999', '', '1.5'):
    r = g(f'/int?n={v}'); print(f'  n={v!r:<24} → {r[1]}'); R['int'][v] = r[1]
print('  没有传 n →', g('/int')[1])
print()
print('== 二:type=float 接受 nan 与 inf;type=bool 对 "false" 返回 True')
R['float'] = {}
for v in ('1.5', 'nan', 'inf', '-inf', '1e400', 'abc'): r = g(f'/float?x={v}'); print(f'  x={v!r:<8} → {r[1]}'); R['float'][v] = r[1]['repr']
R['bool'] = {}
for v in ('true', 'false', '0', '1', ''): r = g(f'/bool?flag={v}'); print(f'  flag={v!r:<8} → {r[1]}'); R['bool'][v] = r[1]['flag']
print()
print('== 三:路径转换器 <int:i> 不匹配时是 404,不是 400')
R['conv'] = {}
for v in ('5', '007', 'abc', '-1', '1.5', '٣'): r = g(f'/items/{v}'); print(f'  /items/{v:<5} → {r[0]} {r[1] if r[0] == 200 else ""}'); R['conv'][v] = r[0]
print()
print('== 四:request.json["name"] 缺少键、请求体不是对象 → 500(不是 400);类型错误的值直接放行')
r = c.post('/key', json={}); print('  缺 name(KeyError)→', r.status_code, r.get_data(as_text=True)[:60].replace('\n', ' ')); R['key_missing'] = r.status_code
r = c.post('/key', json={'name': 12345}); print('  name 是整数 12345 →', r.status_code, r.get_json()); R['key_wrongtype'] = [r.status_code, r.get_json()]
r = c.post('/key', json={'name': {'a': [1, 2]}}); print('  name 是嵌套对象 →', r.status_code, r.get_json())
r = c.post('/key', json=[1, 2]); print('  请求体是列表 →', r.status_code, '(', r.get_data(as_text=True)[:50].replace('\n', ' '), ')'); R['key_list'] = r.status_code
print()
print('== 五:手写校验函数,一次返回所有错误(422)')
R['user'] = {}
for label, body in (('合法', {'name': 'ann', 'age': 30}), ('name 缺失、age 越界', {'age': 200}), ('age 是字符串', {'name': 'bob', 'age': '30'}), ('age 是 true', {'name': 'bob', 'age': True}), ('请求体是列表', [1])):
    r = c.post('/user', json=body); print(f'  {label:<18} → {r.status_code} {r.get_json()}'); R['user'][label] = [r.status_code, r.get_json()]
r = c.post('/user', data='{', content_type='application/json'); print('  非法 JSON(silent=True 之后当成 None)→', r.status_code, r.get_json()); R['user_bad'] = [r.status_code, r.get_json()]
print()
print('== 六:分页参数的范围:limit 与 offset 夹到合法区间')
R['page'] = {}
for q in ('', '?limit=5&offset=10', '?limit=0', '?limit=100000', '?limit=-3&offset=-9', '?limit=abc'): r = g('/page' + q); print(f'  /page{q:<22} → {r[1]}'); R['page'][q] = r[1]
print('  getlist:?id=1&id=2&id=x&id=3 →', g('/list?id=1&id=2&id=x&id=3')[1], '(无法转换的元素被悄悄丢掉)'); R['getlist'] = g('/list?id=1&id=2&id=x&id=3')[1]
print()
print('== 七:请求体大小限制 MAX_CONTENT_LENGTH(这里设成 1000 字节)')
for n in (500, 1000, 1001, 5000): r = c.post('/size', data='x' * n, content_type='text/plain'); print(f'  请求体 {n} 字节 → {r.status_code}'); R.setdefault('size', {})[n] = r.status_code
save('f103', R)
