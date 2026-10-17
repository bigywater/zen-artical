import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f105'); R = {}
from flask import Flask, Blueprint, jsonify, request, abort, url_for
USERS = {1: {'first': 'Ann', 'last': 'Lee', 'email': 'ann@x.test'}}
def get_user(i):
    if i not in USERS: abort(404)
    return USERS[i]
app = Flask('ver'); app.logger.disabled = True
v1 = Blueprint('v1', __name__, url_prefix='/v1'); v2 = Blueprint('v2', __name__, url_prefix='/v2')
@v1.get('/users/<int:i>')
def u1(i): u = get_user(i); return {'id': i, 'name': f"{u['first']} {u['last']}"}
@v2.get('/users/<int:i>')
def u2(i): u = get_user(i); return {'id': i, 'first_name': u['first'], 'last_name': u['last'], 'email': u['email']}
@v1.after_request
def deprecate(r): r.headers['Deprecation'] = 'true'; r.headers['Sunset'] = 'Wed, 31 Dec 2026 23:59:59 GMT'; r.headers['Link'] = '</v2/users>; rel="successor-version"'; return r
app.register_blueprint(v1); app.register_blueprint(v2)
@app.get('/health')
def health(): return {'ok': True}
c = app.test_client()
print('== 一:URL 前缀版本:两个蓝图共用同一份业务代码,响应结构不同')
for p in ('/v1/users/1', '/v2/users/1', '/v3/users/1'):
    r = c.get(p); print(f'  {p:<14} → {r.status_code} {r.get_data(as_text=True).strip()[:100] if r.is_json else "(HTML 404 页面)"}'); R.setdefault('url', {})[p] = [r.status_code, r.get_json() if r.is_json else None]
print('  url_for 生成的地址:', url_for('v1.u1', i=1) if False else '', end=''); 
with app.test_request_context(): print(url_for('v1.u1', i=1), url_for('v2.u2', i=1)); R['url_for'] = [url_for('v1.u1', i=1), url_for('v2.u2', i=1)]
print('  路由表:'); [print('    ', f'{str(sorted(r.methods - {"HEAD", "OPTIONS"})):<8} {r.rule:<24} → {r.endpoint}') for r in app.url_map.iter_rules() if r.endpoint != 'static']
print()
print('== 二:废弃提示:蓝图的 after_request 只给 v1 的响应加 Deprecation / Sunset 头')
for p in ('/v1/users/1', '/v2/users/1', '/health'):
    r = c.get(p); print(f'  {p:<14} Deprecation={r.headers.get("Deprecation")} Sunset={r.headers.get("Sunset")} Link={r.headers.get("Link")}'); R.setdefault('dep', {})[p] = [r.headers.get('Deprecation'), r.headers.get('Sunset')]
r = c.get('/v1/users/999'); print('  v1 的 404 响应有没有这些头:', r.headers.get('Deprecation')); R['dep404'] = r.headers.get('Deprecation')
print()
print('== 三:请求头版本:Accept: application/vnd.app.v2+json 与自定义 X-API-Version')
app2 = Flask('ver2'); app2.logger.disabled = True
@app2.get('/users/<int:i>')
def users(i):
    u = get_user(i); best = request.accept_mimetypes.best_match(['application/vnd.app.v1+json', 'application/vnd.app.v2+json'])
    ver = request.headers.get('X-API-Version')
    if ver is None:
        if best is None: abort(406)
        ver = best.split('.v')[1][0]
    if ver == '1': body = {'id': i, 'name': f"{u['first']} {u['last']}"}
    elif ver == '2': body = {'id': i, 'first_name': u['first'], 'last_name': u['last'], 'email': u['email']}
    else: abort(400, description='unsupported version')
    r = jsonify(body); r.headers['Content-Type'] = f'application/vnd.app.v{ver}+json'; return r
c2 = app2.test_client(); R['hdr'] = {}
for label, h in (('Accept: …v1+json', {'Accept': 'application/vnd.app.v1+json'}), ('Accept: …v2+json', {'Accept': 'application/vnd.app.v2+json'}), ('Accept: v2 优先 (q 值)', {'Accept': 'application/vnd.app.v1+json;q=0.5, application/vnd.app.v2+json;q=0.9'}), ('Accept: */*', {'Accept': '*/*'}), ('Accept: text/html', {'Accept': 'text/html'}), ('X-API-Version: 2', {'X-API-Version': '2'}), ('X-API-Version: 9', {'X-API-Version': '9'})):
    r = c2.get('/users/1', headers=h); print(f'  {label:<26} → {r.status_code} {r.headers.get("Content-Type", "").split(";")[0]:<34} {r.get_data(as_text=True).strip()[:70] if r.is_json or "json" in r.headers.get("Content-Type", "") else ""}'); R['hdr'][label] = [r.status_code, r.headers.get('Content-Type')]
r = c2.get('/users/1', headers={'Accept': 'application/vnd.app.v2+json'}); print('  响应里的 Vary 头:', r.headers.get('Vary'), '(Flask 不会自动加;共享缓存会把 v1 与 v2 混在一起)'); R['vary'] = r.headers.get('Vary')
print()
print('== 四:路由层面的代价:URL 版本每个版本重复一套路由;请求头版本只有一套路由但视图里要分支')
print(f'  URL 版本:2 个版本 × 1 条规则 = {sum(1 for r in app.url_map.iter_rules() if "users" in r.rule)} 条规则;请求头版本:{sum(1 for r in app2.url_map.iter_rules() if "users" in r.rule)} 条规则')
R['rules'] = [sum(1 for r in app.url_map.iter_rules() if 'users' in r.rule), sum(1 for r in app2.url_map.iter_rules() if 'users' in r.rule)]
save('f105', R)
