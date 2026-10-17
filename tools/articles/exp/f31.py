import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f31'); R = {}
import io, json
import flask
from flask import Flask, request
app = Flask('rq'); app.logger.disabled = True; app.secret_key = 'k'
@app.route('/inspect/<int:n>', methods=['GET', 'POST'])
def inspect_(n):
    cls = type(request._get_current_object())
    return {'type': f'{cls.__module__}.{cls.__name__}', 'method': request.method, 'path': request.path, 'full_path': request.full_path, 'script_root': request.script_root, 'url': request.url, 'base_url': request.base_url, 'url_root': request.url_root, 'host': request.host, 'host_url': request.host_url, 'scheme': request.scheme, 'is_secure': request.is_secure, 'remote_addr': request.remote_addr, 'endpoint': request.endpoint, 'view_args': request.view_args, 'url_rule': str(request.url_rule), 'content_type': request.content_type, 'mimetype': request.mimetype, 'content_length': request.content_length, 'user_agent': request.user_agent.string, 'referrer': request.referrer, 'is_json': request.is_json, 'accept_json': request.accept_mimetypes.best == 'application/json'}
c = app.test_client()
print('== 一:一个请求上可以读到的属性(打印一次真实请求的各个属性)')
r = c.post('/inspect/7?x=1&y=2', data=b'{"a":1}', content_type='application/json', headers={'User-Agent': 'lab/1.0', 'Referer': 'http://ref.test/', 'Accept': 'application/json'}, base_url='https://shop.example.test:8443/base/', environ_overrides={'REMOTE_ADDR': '203.0.113.9'})
d = r.get_json(); R['attrs'] = d
for k, v in d.items(): print(f'  request.{k:<14} = {v!r}')
print()
print('== 二:Request 类的家族:Flask 的 Request 继承 Werkzeug 的 Request;Flask 加了哪些属性')
from werkzeug.wrappers import Request as WRequest
own = sorted(n for n in vars(flask.Request) if not n.startswith('_')); print('  flask.Request 自己定义的公开成员:', own); R['own'] = own
print('  继承链:', [f'{k.__module__}.{k.__name__}' for k in flask.Request.__mro__ if k is not object]); R['mro'] = [f'{k.__module__}.{k.__name__}' for k in flask.Request.__mro__ if k is not object]
print()
print('== 三:惰性解析:请求对象构造时并不解析 args / form / json / cookies;第一次访问才解析并缓存')
from werkzeug.test import EnvironBuilder
env = EnvironBuilder('/p?x=1', method='POST', data={'f': 'v'}).get_environ()
with app.request_context(env):
    r_ = request._get_current_object(); before = sorted(k for k in r_.__dict__ if k in ('args', 'form', 'files', 'cookies', 'values', 'headers', 'data'))
    r_.args; r_.form; after = sorted(k for k in r_.__dict__ if k in ('args', 'form', 'files', 'cookies', 'values', 'headers', 'data'))
    print('  构造后缓存里已有:', before, '| 访问 args 与 form 之后:', after); R['lazy'] = [before, after]
print()
print('== 四:请求体只能读一次:get_data() 之后再读 stream 是空的;cache=True(默认)时 get_data 可重复调用')
with app.test_request_context('/p', method='POST', data=b'hello body'):
    a1 = request.get_data(); a2 = request.get_data(); s = request.stream.read(); print('  get_data() 两次:', a1, a2, '| 随后读 stream:', s); R['body'] = [a1.decode(), a2.decode(), s.decode()]
with app.test_request_context('/p', method='POST', data=b'hello body'):
    s1 = request.stream.read(); a3 = request.get_data(); print('  先读 stream 再 get_data():', s1, a3); R['body2'] = [s1.decode(), a3.decode()]
print()
print('== 五:remote_addr 与反向代理:没有 ProxyFix 时拿到的是直连方的地址(见第 135 篇);X-Forwarded-For 只是普通头')
r = c.get('/inspect/1', headers={'X-Forwarded-For': '198.51.100.7'}, environ_overrides={'REMOTE_ADDR': '10.0.0.2'}); print('  REMOTE_ADDR=10.0.0.2、X-Forwarded-For=198.51.100.7 → request.remote_addr =', r.get_json()['remote_addr']); R['xff'] = r.get_json()['remote_addr']
print()
print('== 六:读取请求的开销:构造 Request + 访问 args / headers / path(timeit,50000 次)')
import timeit
env = EnvironBuilder('/p?x=1&y=2', headers={'A': 'b'}).get_environ()
def mk(): rq = flask.Request(env); return rq.path, rq.args.get('x'), rq.headers.get('A')
t = min(timeit.timeit(mk, number=50000) / 50000 * 1e6 for _ in range(3)); print(f'  每次构造并读取:{t:.1f} µs'); R['cost'] = t
save('f31', R)
