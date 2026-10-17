import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f24'); R = {}
from flask import Flask, request, make_response
a = Flask('oh'); a.logger.disabled = True; calls = []
@a.route('/res', methods=['GET', 'POST'])
def res(): calls.append(request.method); return 'body of res'
@a.route('/custom', methods=['GET', 'OPTIONS'])
def custom():
    if request.method == 'OPTIONS':
        r = make_response('', 204); r.headers['Allow'] = 'GET, OPTIONS'; r.headers['X-Custom'] = '1'; return r
    return 'custom get'
@a.route('/noauto', methods=['GET'], provide_automatic_options=False)
def noauto(): return 'noauto'
@a.before_request
def br(): calls.append('before:' + request.method)
c = a.test_client()
print('== 一:自动的 OPTIONS 响应:状态、Allow 头、正文;视图函数不会被调用')
calls.clear(); r = c.options('/res'); print('  OPTIONS /res →', r.status, '|', dict(r.headers), '| 正文长度', len(r.data)); print('  这次请求触发的回调:', calls); R['options'] = [r.status_code, dict(r.headers), len(r.data), list(calls)]
print()
print('== 二:自动的 HEAD:视图函数确实会被执行(有副作用就会执行两次),只是 Werkzeug 去掉了正文')
calls.clear(); rg = c.get('/res'); rh = c.head('/res'); print('  GET →', rg.status_code, 'Content-Length', rg.headers.get('Content-Length'), '正文', len(rg.data)); print('  HEAD →', rh.status_code, 'Content-Length', rh.headers.get('Content-Length'), '正文', len(rh.data)); print('  视图函数里记录到的方法:', [x for x in calls if not x.startswith('before')]); R['head'] = [rg.headers.get('Content-Length'), rh.headers.get('Content-Length'), len(rh.data), [x for x in calls if not x.startswith('before')]]
print()
print('== 三:自己处理 OPTIONS(methods 里写上 OPTIONS):Flask 不再生成自动响应,视图被调用')
r = c.options('/custom'); print('  OPTIONS /custom →', r.status_code, '| Allow =', r.headers.get('Allow'), '| X-Custom =', r.headers.get('X-Custom')); R['custom'] = [r.status_code, r.headers.get('Allow'), r.headers.get('X-Custom')]
print()
print('== 四:provide_automatic_options=False:不生成自动 OPTIONS,于是得到 405')
r = c.options('/noauto'); print('  OPTIONS /noauto →', r.status_code, '| Allow =', r.headers.get('Allow')); R['noauto'] = [r.status_code, r.headers.get('Allow')]
rule = [x for x in a.url_map.iter_rules() if x.endpoint == 'noauto'][0]; print('  noauto 规则的 methods =', sorted(rule.methods)); R['noauto_methods'] = sorted(rule.methods)
print()
print('== 五:before_request 对 OPTIONS 也会执行(所以放在 before_request 里的鉴权要小心预检请求)')
calls.clear(); c.options('/res'); print('  OPTIONS /res 触发的回调:', calls); R['before_options'] = list(calls)
print()
print('== 六:跨域预检请求(带 Origin 与 Access-Control-Request-Method 的 OPTIONS):没有装 flask-cors 时只返回 Allow,没有任何 Access-Control-* 头')
r = c.options('/res', headers={'Origin': 'https://other.example', 'Access-Control-Request-Method': 'POST'}); print('  →', r.status_code, '|', {k: v for k, v in r.headers if k.lower().startswith(('access-control', 'allow'))}); R['preflight'] = {k: v for k, v in r.headers if k.lower().startswith(('access-control', 'allow'))}
save('f24', R)
