import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f156'); R = {}
import datetime as dt, time as _t
from flask import Flask, session, request, jsonify, redirect, flash, get_flashed_messages, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user
app = Flask('ts'); app.logger.disabled = True; app.config.update(SECRET_KEY='k' * 32, TESTING=True)
lm = LoginManager(app)
class U(UserMixin):
    def __init__(self, id): self.id = id
@lm.user_loader
def load(i): return U(i) if i in ('1', '2') else None
@app.post('/login')
def login(): session['user'] = request.form['u']; session.permanent = request.form.get('perm') == '1'; return 'ok'
@app.get('/me')
def me(): return jsonify(user=session.get('user'), keys=sorted(session.keys()))
@app.post('/cart/add')
def add(): session['cart'] = session.get('cart', []) + [request.form['item']]; return jsonify(cart=session['cart'])
@app.post('/notify')
def notify(): flash('saved!', 'success'); return redirect(url_for('page'))
@app.get('/page')
def page(): return jsonify(flashes=get_flashed_messages(with_categories=True))
@app.get('/secret')
@login_required
def secret(): return jsonify(who=current_user.id)
c = app.test_client()
print('== 一:读取与预置 session:session_transaction()')
with c.session_transaction() as s: s['user'] = 'preset'; s['cart'] = ['x']
print('  预置之后 /me →', c.get('/me').get_json()); R['preset'] = c.get('/me').get_json()
with c.session_transaction() as s: print('  再用 session_transaction 读取服务端写进去的:', dict(s)); R['read_back'] = dict(s)
print()
print('== 二:请求之后检查 session 的内容:with client 保留上下文')
c2 = app.test_client()
with c2: c2.post('/cart/add', data={'item': 'apple'}); c2.post('/cart/add', data={'item': 'pear'}); print('  with client: 里请求之后读 flask.session["cart"] →', session['cart']); R['cart'] = list(session['cart'])
print()
print('== 三:flash 消息存在 session 里;跟随重定向后读到,读一次就没了')
c3 = app.test_client(); r = c3.post('/notify', follow_redirects=True); print('  重定向后的页面读到:', r.get_json()); R['flash1'] = r.get_json()
r = c3.get('/page'); print('  再请求一次:', r.get_json(), '(flash 被消费了)'); R['flash2'] = r.get_json()
c3b = app.test_client()
with c3b.session_transaction() as s: s['_flashes'] = [('warning', 'preset flash')]
print('  预置 _flashes 之后:', c3b.get('/page').get_json()); R['flash_preset'] = c3b.get('/page').get_json()
print()
print('== 四:Flask-Login:不走登录表单,直接在 session 里写 _user_id 就是「已登录」')
c4 = app.test_client(); r = c4.get('/secret'); print('  未登录访问 /secret →', r.status_code); R['anon'] = r.status_code
with c4.session_transaction() as s: s['_user_id'] = '1'; s['_fresh'] = True
r = c4.get('/secret'); print('  预置 _user_id=1 之后 →', r.status_code, r.get_json()); R['login_preset'] = [r.status_code, r.get_json()]
with c4.session_transaction() as s: s['_user_id'] = '999'
print('  预置一个不存在的用户 id →', c4.get('/secret').status_code, '(user_loader 返回 None,当作未登录)'); R['login_bad'] = c4.get('/secret').status_code
print()
print('== 五:session 的 cookie 在客户端罐里是什么样:登录之后检查 Set-Cookie 属性(SESSION_COOKIE_* 配置会体现在这里)')
c5 = app.test_client(); r = c5.post('/login', data={'u': 'ann', 'perm': '1'}); sc = [v for k, v in r.headers if k == 'Set-Cookie'][0]; print('  Set-Cookie 属性:', [p.split('=')[0].strip() for p in sc.split(';')]); R['setcookie'] = [p.split('=')[0].strip() for p in sc.split(';')]
print()
print('== 六:测试 session 过期:PERMANENT_SESSION_LIFETIME 靠 cookie 里的签名时间戳;用修改时钟的方式验证')
app.config['PERMANENT_SESSION_LIFETIME'] = dt.timedelta(seconds=60)
c6 = app.test_client(); c6.post('/login', data={'u': 'ann', 'perm': '1'}); print('  刚登录:', c6.get('/me').get_json()['user'])
real_time = _t.time; _t.time = lambda: real_time() + 120
try: print('  把 time.time() 往后拨 120 秒之后:', c6.get('/me').get_json()['user'])
finally: _t.time = real_time
R['expired'] = 'checked'
save('f156', R)
