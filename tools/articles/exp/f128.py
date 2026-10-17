import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f128'); R = {}
import re
from flask import Flask, jsonify
from flask_cors import CORS
def mk(**kw):
    a = Flask('c'); a.logger.disabled = True
    @a.get('/data')
    def data(): return jsonify(ok=True)
    CORS(a, **kw); return a
def acao(a, origin):
    r = a.test_client().get('/data', headers={'Origin': origin} if origin is not None else {}); return {k: v for k, v in r.headers if k in ('Access-Control-Allow-Origin', 'Access-Control-Allow-Credentials', 'Vary')}
GOOD = 'https://app.example.com'; OTHERS = ['https://app.example.com', 'https://other.test', 'null']
print('== 一:几种常见配置,对「自己的前端」「陌生站点」「Origin: null」分别回什么')
cfgs = [('origins 不写(默认 *)', {}), ('origins="*" + supports_credentials=True', dict(origins='*', supports_credentials=True)), ('origins=[自己的前端]', dict(origins=[GOOD])), ('origins=[自己的前端] + supports_credentials', dict(origins=[GOOD], supports_credentials=True))]
R['cfg'] = {}
for label, kw in cfgs:
    a = mk(**kw); print(f'  [{label}]'); R['cfg'][label] = {}
    for o in OTHERS: r = acao(a, o); print(f'     Origin: {o:<24} → {r}'); R['cfg'][label][o] = r
print()
print('== 二:用正则或后缀匹配 origins 的陷阱:匹配规则写得不严,别人的域名也能通过')
tests = ['https://app.example.com', 'https://evilexample.com', 'https://app.example.com.other.test', 'http://app.example.com', 'https://sub.app.example.com']
R['regex'] = {}
for label, pat in (('r"https://.*example.com"(不严)', r'https://.*example.com'), (r'r"https://app\.example\.com$"(锚定)', r'https://app\.example\.com$'), (r'r"https://([a-z0-9-]+\.)?example\.com$"(允许子域)', r'https://([a-z0-9-]+\.)?example\.com$')):
    a = mk(origins=[re.compile(pat)]); print(f'  [{label}]'); R['regex'][label] = {}
    for o in tests: r = acao(a, o); ok = 'Access-Control-Allow-Origin' in r; print(f'     {o:<42} → {"放行" if ok else "拒绝"}'); R['regex'][label][o] = ok
print()
print('== 三:CORS 不是认证:服务端并没有因为 Origin 不在名单里就拒绝请求(第 79 篇看过),只是不给浏览器放行读取')
a = mk(origins=[GOOD]); r = a.test_client().get('/data', headers={'Origin': 'https://other.test'}); print('  Origin 不在名单:', r.status_code, r.get_json(), '| 有没有 Allow-Origin:', 'Access-Control-Allow-Origin' in r.headers); R['not_auth'] = [r.status_code, r.get_json()]
r = a.test_client().get('/data'); print('  根本不带 Origin(curl、服务器到服务器):', r.status_code, r.get_json()); R['no_origin'] = [r.status_code]
print()
print('== 四:Vary: Origin 与缓存:按 Origin 回不同的头,必须加 Vary: Origin')
a = mk(origins=[GOOD, 'https://admin.example.com']); r1 = a.test_client().get('/data', headers={'Origin': GOOD}); r2 = a.test_client().get('/data', headers={'Origin': 'https://admin.example.com'}); print('  Origin=app →', {k: v for k, v in r1.headers if k in ('Access-Control-Allow-Origin', 'Vary')}); print('  Origin=admin →', {k: v for k, v in r2.headers if k in ('Access-Control-Allow-Origin', 'Vary')}); R['vary'] = r1.headers.get('Vary')
print()
print('== 五:只给需要的路径、需要的方法开 CORS')
a = Flask('c2'); a.logger.disabled = True
@a.get('/api/x')
def x(): return 'x'
@a.get('/admin/y')
def y(): return 'y'
CORS(a, resources={r'/api/*': {'origins': [GOOD], 'methods': ['GET']}})
for p in ('/api/x', '/admin/y'): print(f'  {p:<10}', acao(a, GOOD)) if False else print(f'  {p:<10}', {k: v for k, v in a.test_client().get(p, headers={'Origin': GOOD}).headers if k.startswith('Access-Control')}); R.setdefault('res', {})[p] = {k: v for k, v in a.test_client().get(p, headers={'Origin': GOOD}).headers if k.startswith('Access-Control')}
r = a.test_client().options('/api/x', headers={'Origin': GOOD, 'Access-Control-Request-Method': 'DELETE'}); print('  预检请求 DELETE /api/x(只允许 GET)→', r.status_code, {k: v for k, v in r.headers if k.startswith('Access-Control')}); R['pre_delete'] = [r.status_code, {k: v for k, v in r.headers if k.startswith('Access-Control')}]
save('f128', R)
