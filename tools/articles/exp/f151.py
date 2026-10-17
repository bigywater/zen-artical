import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f151'); R = {}
from flask import Flask, request, session, jsonify, redirect, url_for, make_response, g
app = Flask('tc'); app.logger.disabled = True; app.config['SECRET_KEY'] = 'k' * 32
@app.post('/login')
def login(): session['user'] = request.form['user']; return redirect(url_for('home'))
@app.get('/home')
def home(): return jsonify(user=session.get('user'), ip=request.remote_addr, scheme=request.scheme, host=request.host)
@app.post('/json')
def js(): return jsonify(got=request.get_json(), ctype=request.content_type)
@app.get('/q')
def q(): return jsonify(args=request.args.to_dict(flat=False))
@app.get('/cookie')
def cookie(): r = make_response('set'); r.set_cookie('visited', '1'); return r
@app.get('/readcookie')
def readcookie(): return request.cookies.get('visited', 'none')
@app.get('/stream')
def stream():
    def gen():
        for i in range(3): yield f'{i}\n'
    return app.response_class(gen(), mimetype='text/plain')
@app.get('/g')
def gview(): g.x = 'in-request'; return 'ok'
c = app.test_client()
print('== 一:请求的几种写法:form、json、query_string、headers')
r = c.post('/json', json={'a': 1}); print('  json= →', r.get_json(), '(Content-Type 由客户端自动设成', r.get_json()['ctype'] + ')'); R['json'] = r.get_json()
r = c.get('/q', query_string={'a': [1, 2], 'b': 'x'}); print('  query_string={a:[1,2], b:x} →', r.get_json()['args']); R['qs'] = r.get_json()['args']
try: c.get('/q?c=3', query_string={'d': 4}); out = '没有报错'
except ValueError as e: out = f'ValueError: {e}'
print('  URL 里已有查询串,同时传 query_string →', out); R['qs_both'] = out
print()
print('== 二:cookie 罐:客户端自动保存并回传 cookie;use_cookies=False 关闭')
c2 = app.test_client(); c2.get('/cookie'); print('  同一个客户端的下一个请求读到的 cookie:', c2.get('/readcookie').get_data(as_text=True)); R['cookie_jar'] = c2.get('/readcookie').get_data(as_text=True)
c3 = app.test_client(use_cookies=False); c3.get('/cookie'); print('  use_cookies=False 的客户端:', c3.get('/readcookie').get_data(as_text=True)); R['no_cookies'] = c3.get('/readcookie').get_data(as_text=True)
print('  两个客户端互不影响:', app.test_client().get('/readcookie').get_data(as_text=True))
print()
print('== 三:重定向:默认不跟随;follow_redirects=True 跟随并保留 session')
r = c.post('/login', data={'user': 'ann'}); print('  默认 →', r.status_code, 'Location:', r.headers['Location']); R['redir'] = [r.status_code, r.headers['Location']]
c4 = app.test_client(); r = c4.post('/login', data={'user': 'ann'}, follow_redirects=True); print('  follow_redirects=True →', r.status_code, r.get_json(), '| r.history 长度:', len(r.history)); R['follow'] = [r.status_code, r.get_json()['user'], len(r.history)]
print()
print('== 四:直接改 session:session_transaction() 在不走登录接口的情况下预置状态')
c5 = app.test_client()
with c5.session_transaction() as sess: sess['user'] = 'preset'
print('  预置 session 后访问 /home →', c5.get('/home').get_json()['user']); R['sess_tx'] = c5.get('/home').get_json()['user']
print()
print('== 五:环境覆盖:远端地址、https、主机名')
r = c.get('/home', environ_overrides={'REMOTE_ADDR': '203.0.113.7'}); print('  environ_overrides REMOTE_ADDR →', r.get_json()['ip']); R['ip'] = r.get_json()['ip']
r = c.get('/home', base_url='https://example.test'); print("  base_url='https://example.test' →", r.get_json()['scheme'], r.get_json()['host']); R['https'] = [r.get_json()['scheme'], r.get_json()['host']]
r = c.get('/home'); print('  默认的主机名与地址:', r.get_json()['host'], r.get_json()['ip'])
print()
print('== 六:请求结束后上下文就销毁;with client: 保留到 with 结束(可以在请求之后读 request、session、g)')
c6 = app.test_client(); c6.get('/g')
try: print('  普通调用之后读 g.x →', g.x)
except RuntimeError as e: print('  普通调用之后读 g.x → RuntimeError:', str(e).splitlines()[0][:50]); R['after'] = 'RuntimeError'
with c6: c6.get('/g?z=9'); print('  with client: 里请求之后读 request.args.get("z") →', request.args.get('z'), '| g.x →', g.x); R['kept'] = [request.args.get('z'), g.x]
print()
print('== 七:流式响应在测试里是被完整缓冲的;buffered=False 能一块块读')
r = c.get('/stream'); print('  普通 get:', repr(r.get_data(as_text=True))); R['stream'] = r.get_data(as_text=True)
r = c.get('/stream', buffered=False); print('  buffered=False:', [x for x in r.response], '(迭代器,可以逐块消费)'); R['unbuf'] = [x.decode() if isinstance(x, bytes) else x for x in r.response]
save('f151', R)
