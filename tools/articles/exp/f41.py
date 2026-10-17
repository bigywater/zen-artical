import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f41'); R = {}
import dataclasses, json
from flask import Flask, Response, jsonify, make_response
@dataclasses.dataclass
class User: id: int; name: str
class Pyd:
    def __init__(self, **kw): self.d = kw
    def model_dump(self): return self.d
class ApiResponse(Response):
    default_mimetype = 'application/json'
    charset = 'utf-8'
    @classmethod
    def force_type(cls, response, environ=None):
        if isinstance(response, (User, Pyd)):
            body = json.dumps(dataclasses.asdict(response) if dataclasses.is_dataclass(response) else response.model_dump(), ensure_ascii=False)
            return cls(body, mimetype='application/json')
        return super().force_type(response, environ)
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw); self.headers['X-Api-Version'] = '1'
app = Flask('cr'); app.logger.disabled = True; app.response_class = ApiResponse
@app.get('/user')
def user(): return User(1, '张三')
@app.get('/pyd')
def pyd(): return Pyd(a=1, b=[1, 2])
@app.get('/str')
def s_(): return 'plain string'
@app.get('/dict')
def d_(): return {'k': 'v'}
@app.get('/tuple')
def t_(): return User(2, 'b'), 201, {'X-T': '1'}
@app.get('/boom')
def boom(): raise ValueError('x')
app2 = Flask('cr2'); app2.logger.disabled = True
@app2.get('/user')
def user2(): return User(1, 'a')
c = app.test_client()
print('== 一:没有自定义类时,返回一个 dataclass 对象会报错(TypeError → 500)')
r = app2.test_client().get('/user'); print('  默认 response_class,视图返回 User 对象 →', r.status_code); R['default'] = r.status_code
with app2.test_request_context():
    try: app2.make_response(User(1, 'a'))
    except TypeError as e: print('  make_response 的报错:', ' '.join(str(e).split())[:200]); R['default_err'] = ' '.join(str(e).split())
print()
print('== 二:自定义 Response 子类(重写 force_type、default_mimetype、__init__):视图返回模型对象能行吗?字符串的 Content-Type 会怎样?')
src('''
    class ApiResponse(Response):
        default_mimetype = "application/json"
        @classmethod
        def force_type(cls, response, environ=None):
            if isinstance(response, (User, Pyd)): ...  # 转成 JSON 响应
            return super().force_type(response, environ)
        def __init__(self, *a, **kw): super().__init__(*a, **kw); self.headers["X-Api-Version"] = "1"
    app.response_class = ApiResponse
''')
R['rows'] = {}
for p in ('/user', '/pyd', '/str', '/dict', '/tuple', '/missing'):
    r = c.get(p); R['rows'][p] = [r.status_code, r.content_type, r.headers.get('X-Api-Version'), r.headers.get('X-T'), r.get_data(as_text=True)[:60]]; print(f'  GET {p:<9} → {r.status_code} {r.content_type} | X-Api-Version={r.headers.get("X-Api-Version")} X-T={r.headers.get("X-T")} | {r.get_data(as_text=True).strip()[:60]!r}')
print()
print('== 三:错误页也用这个类(404、500、abort)——所以统一加的头会出现在所有响应上')
r = c.get('/boom'); print('  500 页:', r.status_code, r.content_type, r.headers.get('X-Api-Version')); R['err500'] = [r.status_code, r.content_type, r.headers.get('X-Api-Version')]
print()
print('== 四:force_type 什么时候被调用:视图返回的是「Response 以外、Flask 不认识的类型」且不是 str/bytes/dict/list/tuple/generator 时')
calls = []
class Spy(Response):
    @classmethod
    def force_type(cls, response, environ=None): calls.append(type(response).__name__); return super().force_type(response, environ)
a3 = Flask('cr3'); a3.logger.disabled = True; a3.response_class = Spy
import io
from werkzeug.wrappers import Response as WResponse
for name, ret in (('str', lambda: 'x'), ('dict', lambda: {'a': 1}), ('Response', lambda: Response('r')), ('werkzeug Response', lambda: WResponse('w')), ('WSGI callable', lambda: (lambda env, sr: (sr('200 OK', [('Content-Type', 'text/plain')]), [b'wsgi'])[1]))):
    a3.add_url_rule('/' + name.replace(' ', '_'), name.replace(' ', '_'), ret)
c3 = a3.test_client()
for name in ('str', 'dict', 'Response', 'werkzeug Response', 'WSGI callable'):
    calls.clear(); r = c3.get('/' + name.replace(' ', '_')); print(f'  返回 {name:<18} → {r.status_code} | force_type 被调用:{calls}'); R.setdefault('force', {})[name] = [r.status_code, list(calls)]
print()
print('== 四b:真正能让视图直接返回模型对象的做法:子类化 Flask,重写 make_response')
class MyFlask(Flask):
    def make_response(self, rv):
        status = headers = None
        if isinstance(rv, tuple):
            rv, *rest = rv
            if len(rest) == 2: status, headers = rest
            elif len(rest) == 1: status = rest[0] if isinstance(rest[0], int) else None; headers = rest[0] if isinstance(rest[0], dict) else None
        if isinstance(rv, User): rv = dataclasses.asdict(rv)
        elif isinstance(rv, Pyd): rv = rv.model_dump()
        if status is not None or headers is not None: rv = (rv, status, headers) if headers is not None else (rv, status)
        return super().make_response(rv)
mf = MyFlask('cr4'); mf.logger.disabled = True
mf.add_url_rule('/user', 'user', lambda: User(1, '张三')); mf.add_url_rule('/pyd', 'pyd', lambda: Pyd(a=1)); mf.add_url_rule('/tuple', 'tuple', lambda: (User(2, 'b'), 201, {'X-T': '1'})); mf.add_url_rule('/str', 'str', lambda: 'plain')
cm = mf.test_client(); R['mf'] = {}
for p in ('/user', '/pyd', '/tuple', '/str'):
    r = cm.get(p); R['mf'][p] = [r.status_code, r.content_type, r.headers.get('X-T'), r.get_data(as_text=True).strip()]; print(f'  GET {p:<7} → {r.status_code} {r.content_type} | X-T={r.headers.get("X-T")} | {r.get_data(as_text=True).strip()!r}')
print()
print('== 五:default_mimetype 与 mimetype 参数:不同写法得到的 Content-Type')
class Csv(Response): default_mimetype = 'text/csv'
for label, r in (('Csv("a,b")', Csv('a,b')), ('Csv("a,b", mimetype="text/plain")', Csv('a,b', mimetype='text/plain')), ('Csv("a,b", content_type="text/tab-separated-values")', Csv('a,b', content_type='text/tab-separated-values'))): print(f'  {label:<56} → {r.content_type}'); R.setdefault('mime', {})[label] = r.content_type
save('f41', R)
