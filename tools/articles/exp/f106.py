import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f106'); R = {}
import uuid
from flask import Flask, request, jsonify, abort, url_for
app = Flask('r'); app.logger.disabled = True
DB = {1: {'id': 1, 'name': 'ann'}}; NEXT = [2]
@app.get('/users/')
def list_users(): return jsonify(list(DB.values()))
@app.post('/users/')
def create_user():
    u = {'id': NEXT[0], **request.get_json()}; DB[NEXT[0]] = u; NEXT[0] += 1; r = jsonify(u); r.status_code = 201; r.headers['Location'] = url_for('get_user', uid=u['id']); return r
@app.get('/users/<int:uid>')
def get_user(uid): return jsonify(DB[uid]) if uid in DB else abort(404)
@app.put('/users/<int:uid>')
def put_user(uid): DB[uid] = {'id': uid, **request.get_json()}; return jsonify(DB[uid])
@app.patch('/users/<int:uid>')
def patch_user(uid): DB[uid].update(request.get_json()); return jsonify(DB[uid])
@app.delete('/users/<int:uid>')
def del_user(uid): DB.pop(uid, None); return '', 204
@app.get('/users/me')
def me(): return jsonify(me=True)
@app.get('/users/<name>')
def by_name(name): return jsonify(by_name=name)
@app.get('/ping')
def ping(): return 'pong'
@app.get('/users/<int:uid>/posts/<int:pid>')
def post(uid, pid): return jsonify(uid=uid, pid=pid)
@app.get('/files/<path:p>')
def files(p): return jsonify(p=p)
@app.get('/items/<uuid:i>')
def item(i): return jsonify(i=str(i), t=type(i).__name__)
POSTS = {5: {'owner': 1}}
@app.get('/v/users/<int:uid>/posts/<int:pid>')
def nested(uid, pid):
    if POSTS.get(pid, {}).get('owner') != uid: abort(404)
    return jsonify(ok=True)
c = app.test_client()
def b(r): return r.get_data(as_text=True).strip().replace('\n', ' ')[:70]
print('== 一:方法与状态码:POST 创建返回 201 + Location;PUT 整体替换;PATCH 部分更新;DELETE 返回 204')
r = c.post('/users/', json={'name': 'bob'}); print('  POST /users/ →', r.status_code, r.headers.get('Location'), b(r)); R['post'] = [r.status_code, r.headers.get('Location')]
r = c.put('/users/2', json={'name': 'bobby'}); print('  PUT /users/2 {name} →', r.status_code, b(r))
r = c.patch('/users/2', json={'email': 'b@x.test'}); print('  PATCH /users/2 {email} →', r.status_code, b(r)); R['patch'] = r.get_json()
r = c.put('/users/2', json={'name': 'bobby'}); print('  再 PUT 一次(整体替换,email 没了)→', r.status_code, b(r)); R['put_replace'] = r.get_json()
r = c.delete('/users/2'); print('  DELETE /users/2 →', r.status_code, repr(r.get_data(as_text=True))); R['delete'] = r.status_code
r = c.delete('/users/2'); print('  再 DELETE 一次 →', r.status_code, '(这个实现是幂等的:删不存在的也返回 204)'); R['delete2'] = r.status_code
r = c.get('/users/2'); print('  GET /users/2 →', r.status_code)
print()
print('== 二:405 与 OPTIONS:不允许的方法;GET 路由自动支持 HEAD 与 OPTIONS')
r = c.delete('/users/'); print('  DELETE /users/ →', r.status_code, '| Allow:', r.headers.get('Allow')); R['allow'] = r.headers.get('Allow')
r = c.options('/users/1'); print('  OPTIONS /users/1 →', r.status_code, '| Allow:', r.headers.get('Allow')); R['options'] = r.headers.get('Allow')
r = c.head('/users/1'); print('  HEAD /users/1 →', r.status_code, '| 正文长度', len(r.data), '| Content-Length', r.headers.get('Content-Length'))
print()
print('== 三:尾部斜杠:路由定义带斜杠(/users/)与不带斜杠(/ping)时的行为')
for m, p in (('get', '/users'), ('post', '/users'), ('get', '/users/'), ('get', '/ping'), ('get', '/ping/')):
    r = getattr(c, m)(p, json={'name': 'z'}) if m == 'post' else getattr(c, m)(p); print(f'  {m.upper():<5} {p:<9} → {r.status_code}' + (f' Location: {r.headers.get("Location")}' if r.status_code in (301, 307, 308) else '')); R.setdefault('slash', {})[f'{m} {p}'] = [r.status_code, r.headers.get('Location')]
print()
print('== 四:路由优先级:静态路径 /users/me 与 /users/<name>、/users/<int:uid>')
for p in ('/users/me', '/users/ann', '/users/1'):
    r = c.get(p); print(f'  GET {p:<10} → {b(r)}'); R.setdefault('prio', {})[p] = r.get_json()
print()
print('== 五:转换器:int、uuid、path')
for p in ('/items/12345678-1234-5678-1234-567812345678', '/items/not-a-uuid', '/files/a/b/c.txt', '/users/1/posts/2', '/users/x/posts/2'):
    r = c.get(p); print(f'  GET {p:<48} → {r.status_code} {b(r) if r.is_json else ""}'); R.setdefault('conv', {})[p] = r.status_code
print()
print('== 六:嵌套资源:/users/<uid>/posts/<pid> 里 pid 是否属于 uid 要自己校验(路由只管格式)')
for p in ('/v/users/1/posts/5', '/v/users/2/posts/5'): print(f'  GET {p} →', c.get(p).status_code); R.setdefault('nested', {})[p] = c.get(p).status_code
print()
print('== 七:POST 不幂等:同一个请求发两次创建两条;PUT 发两次结果相同')
n0 = len(DB); c.post('/users/', json={'name': 'dup'}); c.post('/users/', json={'name': 'dup'}); n1 = len(DB); print(f'  POST 两次:用户数 {n0} → {n1}(多了 {n1 - n0} 条)'); R['post2'] = n1 - n0
c.put('/users/50', json={'name': 'same'}); n2 = len(DB); c.put('/users/50', json={'name': 'same'}); print(f'  PUT /users/50 两次:第一次后 {n2},第二次后 {len(DB)}(没有再增加)'); R['put2'] = [n2, len(DB)]
save('f106', R)
