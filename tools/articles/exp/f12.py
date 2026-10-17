import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f12'); R = {}
import flask, dataclasses
from flask import Flask, make_response, jsonify, Response
a = Flask('mr'); a.logger.disabled = True
def gen(): yield 'a'; yield 'b'; yield 'c'
@dataclasses.dataclass
class P: x: int
cases = {
 'str': lambda: 'hello', 'bytes': lambda: b'raw bytes', 'dict': lambda: {'a': 1, 'b': [1, 2]}, 'list': lambda: [1, 2, {'k': 'v'}],
 '(body, 201)': lambda: ('created', 201), '(body, headers)': lambda: ('h', {'X-A': '1'}), '(body, 202, headers)': lambda: ('both', 202, {'X-B': '2'}),
 '(body, "404 自定义")': lambda: ('nf', '404 自定义短语'), 'generator': lambda: gen(), 'Response': lambda: Response('resp', 200, mimetype='text/plain'),
 'dict + status': lambda: ({'ok': True}, 201), 'dataclass': lambda: P(1),
 'None': lambda: None, 'int': lambda: 5, 'tuple 长度 4': lambda: ('a', 200, {}, 'x'), 'set': lambda: {1, 2},
}
for k, f in cases.items(): a.add_url_rule('/' + str(abs(hash(k)) % 10**8), k, f)
R['rows'] = {}
print('== 一:视图函数返回不同类型时 Flask 生成的响应(status / Content-Type / 正文)')
print(f'  {"返回值":<26} {"状态":<22} {"Content-Type":<32} 正文')
c = a.test_client()
for k, f in cases.items():
    url = [r.rule for r in a.url_map.iter_rules() if r.endpoint == k][0]
    try:
        r = c.get(url); body = r.get_data(as_text=True).replace('\n', '\\n')[:44]; R['rows'][k] = [r.status, r.content_type, body]; print(f'  {k:<26} {r.status:<22} {str(r.content_type):<32} {body}')
    except Exception as e: msg = ' '.join(str(e).split())[:200]; R['rows'][k] = ['异常', type(e).__name__, msg]; print(f'  {k:<26} 抛出 {type(e).__name__}')
print()
print('== 二:返回值非法时 Flask 抛出的 TypeError 原文(直接调用 app.make_response 看;经过 HTTP 时被转成 500)')
R['err'] = {}
for k in ('None', 'int', 'tuple 长度 4', 'set', 'dataclass'):
    with a.test_request_context():
        try: a.make_response(cases[k]()); print(f'  {k}: 没有报错')
        except Exception as e: msg = ' '.join(str(e).split()); R['err'][k] = [type(e).__name__, msg]; print(f'  {k}: {type(e).__name__}: {msg[:330]}')
print()
print('== 三:app.make_response() 的转换步骤;flask.make_response() 里手动设置 cookie 与头')
with a.test_request_context():
    r = a.make_response(('hi', 201, {'X-A': '1'})); print('  app.make_response(("hi", 201, {"X-A": "1"})) →', type(r).__name__, r.status, dict(r.headers))
    r2 = a.make_response({'k': 'v'}); print('  app.make_response({"k": "v"}) →', r2.content_type, r2.get_data(as_text=True).strip())
    r3 = make_response('x'); r3.set_cookie('sid', 'abc', httponly=True); r3.headers['X-C'] = '3'; print('  手动设置 → Set-Cookie:', r3.headers.get('Set-Cookie'), '| X-C:', r3.headers.get('X-C'))
    R['mr'] = [type(r).__name__, r.status, dict(r.headers), r2.content_type, r3.headers.get('Set-Cookie')]
print()
print('== 四:Content-Length:普通响应有,生成器(流式)响应没有')
for k in ('str', 'generator'):
    url = [r.rule for r in a.url_map.iter_rules() if r.endpoint == k][0]; r = c.get(url); print(f'  {k:<10} Content-Length = {r.headers.get("Content-Length")} | Transfer-Encoding = {r.headers.get("Transfer-Encoding")}')
R['cl'] = {k: c.get([r.rule for r in a.url_map.iter_rules() if r.endpoint == k][0]).headers.get('Content-Length') for k in ('str', 'generator')}
print()
print('== 五:app.response_class:换成自己的类,所有 make_response 都会用它(例如统一加一个响应头)')
class MyResponse(Response):
    def __init__(self, *args, **kw): super().__init__(*args, **kw); self.headers['X-Powered-By'] = 'lab'
b = Flask('mr2'); b.response_class = MyResponse
@b.get('/')
def b_idx(): return 'x'
@b.get('/j')
def b_j(): return {'a': 1}
for p in ('/', '/j', '/nope'): r = b.test_client().get(p); print(f'  GET {p:<5} → {r.status} X-Powered-By = {r.headers.get("X-Powered-By")} | 类型 {type(r).__name__}')
R['custom'] = {p: b.test_client().get(p).headers.get('X-Powered-By') for p in ('/', '/j', '/nope')}
save('f12', R)
