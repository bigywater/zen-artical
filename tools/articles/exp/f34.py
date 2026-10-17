import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f34'); R = {}
import io, json
from flask import Flask, request
app = Flask('afj'); app.logger.disabled = True
@app.route('/all', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def all_():
    try: j = request.json
    except Exception as e: j = f'{type(e).__name__}'
    return {'args': request.args.to_dict(), 'form': request.form.to_dict(), 'files': list(request.files), 'json': j, 'data': request.data.decode('latin-1')[:30], 'values': request.values.to_dict(), 'get_data_len': len(request.get_data())}
@app.post('/pj')
def pj():
    r = {}
    for nm, f in (('request.json', lambda: request.json), ('get_json()', lambda: request.get_json()), ('get_json(silent=True)', lambda: request.get_json(silent=True))):
        try: r[nm] = f()
        except Exception as e: r[nm] = f'{type(e).__name__}({e.code})'
    return r
c = app.test_client()
cases = [
 ('GET ?a=1', lambda: c.get('/all?a=1')),
 ('GET + JSON 正文', lambda: c.open('/all', method='GET', data=json.dumps({'j': 1}), content_type='application/json')),
 ('GET + 表单正文', lambda: c.open('/all', method='GET', data={'f': '1'})),
 ('POST 表单', lambda: c.post('/all', data={'f': '1'})),
 ('POST ?a=1 + 表单', lambda: c.post('/all?a=1', data={'f': '1'})),
 ('POST JSON', lambda: c.post('/all', json={'j': 1})),
 ('POST ?a=1 + JSON', lambda: c.post('/all?a=1', json={'j': 1})),
 ('POST multipart', lambda: c.post('/all', data={'f': '1', 'file': (io.BytesIO(b'xx'), 'a.txt')})),
 ('POST text/plain', lambda: c.post('/all', data='raw text', content_type='text/plain')),
 ('PUT 表单', lambda: c.put('/all', data={'f': '1'})),
 ('PATCH JSON', lambda: c.patch('/all', json={'j': 2})),
 ('DELETE ?a=1', lambda: c.delete('/all?a=1')),
]
print('== 一:同一个视图同时打印 args / form / files / json / data / values;看每种请求把数据放进了哪里')
R['rows'] = {}
for label, f in cases:
    r = f(); d = r.get_json(); R['rows'][label] = d
    print(f'  {label:<18} → {r.status_code} args={d["args"]} form={d["form"]} files={d["files"]} json={d["json"]!r} data={d["data"]!r} values={d["values"]}')
print()
print('== 二:request.json 属性与 request.get_json():属性在不是 JSON 时直接抛异常')
for label, kw in (('JSON', dict(json={'a': 1})), ('表单', dict(data={'a': '1'})), ('空正文无类型', {})):
    r = c.post('/pj', **kw); print(f'  {label:<12}', r.get_json()); R.setdefault('pj', {})[label] = r.get_json()
print()
print('== 三:request.data:只有「Werkzeug 不认识的 Content-Type」才会把正文放在 data;表单与 multipart 会被解析、data 为空')
print('  从第一节:POST 表单 data =', R['rows']['POST 表单']['data'], '| POST JSON data =', R['rows']['POST JSON']['data'], '| text/plain data =', R['rows']['POST text/plain']['data'], '(get_data_len =', R['rows']['POST text/plain']['get_data_len'], ')')
print()
print('== 四:选择取值位置的经验:数据放哪,就从哪读——同名时的优先级')
with app.test_request_context('/all?k=args', method='POST', data={'k': 'form'}): print('  args["k"] =', request.args['k'], '| form["k"] =', request.form['k'], '| values["k"] =', request.values['k'], '(args 在前)'); R['prec'] = [request.args['k'], request.form['k'], request.values['k']]
print()
print('== 五:同名键在 args / json 里是不同的类型:?id=5 是字符串 \'5\',JSON 里 {"id": 5} 是整数 5')
r = c.post('/all?id=5', json={'id': 5}); d = r.get_json(); print('  args["id"] =', repr(d['args']['id']), '| json["id"] =', repr(d['json']['id'])); R['types'] = [d['args']['id'], d['json']['id']]
save('f34', R)
