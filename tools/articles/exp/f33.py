import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f33'); R = {}
import json
from flask import Flask, request
app = Flask('body'); app.logger.disabled = True
@app.post('/echo')
def echo():
    return {'content_type': request.content_type, 'mimetype': request.mimetype, 'is_json': request.is_json, 'form': request.form.to_dict(flat=False), 'files': list(request.files), 'json': request.get_json(silent=True), 'data_len': len(request.get_data()), 'data_head': request.get_data(as_text=True)[:60]}
@app.post('/j')
def j():
    try: return {'json': request.get_json()}
    except Exception as e: return {'error': type(e).__name__, 'msg': str(e)[:120]}, getattr(e, 'code', 500)
@app.post('/jf')
def jf():
    a = request.get_json(silent=True); b = request.get_json(force=True, silent=True); c_ = request.get_json(silent=True)
    return {'silent_first': a, 'force': b, 'silent_after_force': c_}
c = app.test_client()
print('== 一:四种 Content-Type 的请求体:Flask 分别把它放在哪里')
R['ct'] = {}
rows = [('application/x-www-form-urlencoded', dict(data={'a': '1', 'b': ['x', 'y']})), ('multipart/form-data', dict(data={'a': '1', 'f': (__import__('io').BytesIO(b'FILEDATA'), 'a.txt')}, content_type='multipart/form-data')), ('application/json', dict(data=json.dumps({'a': 1}), content_type='application/json')), ('text/plain', dict(data='plain 文本', content_type='text/plain'))]
for label, kw in rows:
    r = c.post('/echo', **kw); d = r.get_json(); R['ct'][label] = d; print(f'  {label:<36} form={d["form"]} files={d["files"]} json={d["json"]} data_len={d["data_len"]}')
print('  (data_len 为 0 表示请求体已经被 form / files 解析消耗了,get_data() 拿不到)')
print()
print('== 二:request.get_json() 的各种情况:Content-Type 不是 JSON、正文不是合法 JSON、silent=True、force=True')
R['json'] = {}
for label, kw in (('Content-Type: application/json + 合法 JSON', dict(data='{"a": 1}', content_type='application/json')), ('Content-Type: application/json + 非法 JSON', dict(data='{bad', content_type='application/json')), ('Content-Type: text/plain + 合法 JSON', dict(data='{"a": 1}', content_type='text/plain')), ('没有 Content-Type', dict(data='{"a": 1}')), ('application/json + 空正文', dict(data='', content_type='application/json')), ('application/vnd.api+json', dict(data='{"a": 1}', content_type='application/vnd.api+json')), ('application/json; charset=utf-8 + 中文', dict(data='{"名": "张三"}'.encode(), content_type='application/json; charset=utf-8'))):
    r = c.post('/j', **kw); R['json'][label] = [r.status_code, r.get_json()]; print(f'  {label:<40} → {r.status_code} {r.get_json()}')
r = c.post('/jf', data='{"a": 1}', content_type='text/plain'); print('  text/plain + force=True →', r.get_json()); R['force'] = r.get_json()
print()
print('== 三:表单的复选框与多值:同名字段多次出现')
r = c.post('/echo', data={'tags': ['a', 'b', 'c'], 'single': 'x'}); print('  form =', r.get_json()['form']); R['multi'] = r.get_json()['form']
with app.test_request_context('/echo', method='POST', data={'tags': ['a', 'b'], 'single': 'x'}): print('  form["tags"] =', request.form['tags'], '| form.getlist("tags") =', request.form.getlist('tags'), '| form.get("none") =', request.form.get('none')); R['getlist'] = [request.form['tags'], request.form.getlist('tags')]
print()
print('== 四:表单字段太多:MAX_FORM_PARTS、MAX_FORM_MEMORY_SIZE(Flask 3.1 的默认值与超限行为)')
print('  默认值:MAX_FORM_MEMORY_SIZE =', app.config['MAX_FORM_MEMORY_SIZE'], '| MAX_FORM_PARTS =', app.config['MAX_FORM_PARTS']); R['defaults'] = [app.config['MAX_FORM_MEMORY_SIZE'], app.config['MAX_FORM_PARTS']]
app.config['MAX_FORM_PARTS'] = 5
r = c.post('/echo', data={f'k{i}': '1' for i in range(10)}, content_type='multipart/form-data'); print('  MAX_FORM_PARTS=5 时发 10 个 multipart 字段 →', r.status_code); R['parts'] = r.status_code
app.config['MAX_FORM_PARTS'] = 1000; app.config['MAX_FORM_MEMORY_SIZE'] = 100
r = c.post('/echo', data={'big': 'x' * 500}); print('  MAX_FORM_MEMORY_SIZE=100 时发 500 字节的表单字段 →', r.status_code); R['mem'] = r.status_code
r = c.post('/echo', data={'big': 'x' * 500}, content_type='multipart/form-data'); print('  同样 500 字节,multipart 形式 →', r.status_code); R['mem_mp'] = r.status_code
print()
print('== 五:同一个请求体 JSON 与表单不会同时出现;JSON 里的类型保真(整数、布尔、null、嵌套),表单里都是字符串')
r = c.post('/j', data=json.dumps({'n': 1, 'ok': True, 'none': None, 'nested': {'a': [1, 2]}}), content_type='application/json'); print('  JSON 往返:', r.get_json()['json'], '| 类型:', {k: type(v).__name__ for k, v in r.get_json()['json'].items()}); R['types'] = {k: type(v).__name__ for k, v in r.get_json()['json'].items()}
save('f33', R)
