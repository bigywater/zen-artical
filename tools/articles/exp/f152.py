import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f152'); R = {}
from flask import Flask, request, session, g, url_for, has_request_context, has_app_context, jsonify, current_app
app = Flask('rc'); app.logger.disabled = True; app.config['SECRET_KEY'] = 'k' * 32
EV = []
@app.before_request
def br(): EV.append('before_request'); g.pre = 'set by before_request'
@app.after_request
def ar(r): EV.append('after_request'); return r
@app.teardown_request
def tr(e): EV.append('teardown_request')
@app.teardown_appcontext
def ta(e): EV.append('teardown_appcontext')
@app.get('/items/<int:i>')
def item(i): return jsonify(i=i)
def helper_reads_request(): return f"{request.method} {request.path} q={request.args.get('q')} ua={request.headers.get('User-Agent')}"
print('== 一:用 test_request_context 测一个读取 request 的辅助函数(不走路由、不走钩子)')
with app.test_request_context('/items/5?q=hello', method='POST', headers={'User-Agent': 'unit-test'}): print('  ', helper_reads_request()); R['helper'] = helper_reads_request()
print()
print('== 二:钩子不会自动执行:进入 with 只是推入上下文;退出时才会执行 teardown')
EV.clear()
with app.test_request_context('/items/5'):
    print('  with 里面,EV =', EV, '| g.pre =', g.get('pre')); R['inside'] = list(EV)
print('  退出 with 之后,EV =', EV); R['after_exit'] = list(EV)
EV.clear()
with app.test_request_context('/items/5'): rv = app.preprocess_request(); print('  手动调用 app.preprocess_request() 后 EV =', EV, '| g.pre =', g.get('pre'), '| 返回值', rv)
R['preprocess'] = list(EV)
print()
print('== 三:full_dispatch_request():在上下文里手动走一遍路由与视图,得到 Response')
EV.clear()
with app.test_request_context('/items/7'): resp = app.full_dispatch_request(); print('  响应:', resp.status_code, resp.get_json(), '| 钩子顺序(退出前):', EV); R['dispatch'] = [resp.status_code, resp.get_json(), list(EV)]
print('  退出之后:', EV)
print()
print('== 四:url_for 在上下文外 vs 里面;测试里生成外部地址')
try: url_for('item', i=3)
except RuntimeError as e: print('  没有任何上下文时 url_for →', str(e).splitlines()[0][:100]); R['url_no_ctx'] = str(e).splitlines()[0][:100]
with app.test_request_context('/'): print('  test_request_context 里 url_for("item", i=3) →', url_for('item', i=3), '| _external=True →', url_for('item', i=3, _external=True)); R['url_in'] = [url_for('item', i=3), url_for('item', i=3, _external=True)]
with app.test_request_context('/', base_url='https://shop.example.test:8443'): print("  base_url='https://shop.example.test:8443' 时 _external →", url_for('item', i=3, _external=True)); R['url_base'] = url_for('item', i=3, _external=True)
with app.app_context():
    try: url_for('item', i=3, _external=True)
    except RuntimeError as e: print('  只有 app_context、没配 SERVER_NAME 时 _external →', str(e).splitlines()[0][:90]); R['app_ctx_url'] = str(e).splitlines()[0][:90]
app.config['SERVER_NAME'] = 'shop.example.test'
with app.app_context(): print('  配了 SERVER_NAME 后 app_context 里 _external →', url_for('item', i=3, _external=True)); R['app_ctx_servername'] = url_for('item', i=3, _external=True)
app.config['SERVER_NAME'] = None
print()
print('== 五:app_context 与 test_request_context 的区别')
with app.app_context(): print('  app_context: has_app_context =', has_app_context(), '| has_request_context =', has_request_context()); R['appctx'] = [has_app_context(), has_request_context()]
with app.test_request_context('/'): print('  test_request_context: has_app_context =', has_app_context(), '| has_request_context =', has_request_context()); R['reqctx'] = [has_app_context(), has_request_context()]
print()
print('== 六:session 与 json 请求体')
with app.test_request_context('/', method='POST', json={'k': 'v'}): print('  request.get_json() →', request.get_json()); R['json'] = request.get_json()
with app.test_request_context('/'):
    session['x'] = 1; print('  session 可以读写,session["x"] =', session['x']); R['session'] = session['x']
save('f152', R)
