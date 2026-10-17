import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f72'); R = {}
import base64, json, hashlib
from flask import Flask, request, redirect, url_for, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, fresh_login_required
app = Flask('lg'); app.logger.disabled = True; app.secret_key = 'lab-secret'; app.config['REMEMBER_COOKIE_DURATION'] = 3600
lm = LoginManager(app); lm.login_view = 'login'
USERS = {'1': {'name': 'ann', 'pw': 'pw1'}, '2': {'name': 'bob', 'pw': 'pw2'}}
loads = {'n': 0}
class User(UserMixin):
    def __init__(self, id): self.id = id; self.name = USERS[id]['name']
@lm.user_loader
def load_user(uid): loads['n'] += 1; return User(uid) if uid in USERS else None
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        for uid, u in USERS.items():
            if u['name'] == request.form['name'] and u['pw'] == request.form['pw']:
                login_user(User(uid), remember=bool(request.form.get('remember'))); return redirect(request.args.get('next') or '/')
        return 'bad credentials', 401
    return 'login form'
@app.get('/')
def index(): return f'hello {current_user.name}' if current_user.is_authenticated else 'hello anonymous'
@app.get('/secret')
@login_required
def secret(): return f'secret for {current_user.name}'
@app.get('/sensitive')
@fresh_login_required
def sensitive(): return 'sensitive'
@app.get('/logout')
def logout(): logout_user(); return 'bye'
@app.get('/whoami')
def whoami(): return jsonify(auth=current_user.is_authenticated, anon=current_user.is_anonymous, cls=type(current_user._get_current_object()).__name__, id=current_user.get_id())
import zlib
def dec(v):
    comp = v.startswith('.'); v = v[1:] if comp else v; p = v.split('.')[0]; raw = base64.urlsafe_b64decode(p + '=' * (-len(p) % 4))
    if comp: raw = zlib.decompress(raw)
    return json.loads(raw)
print('== 一:未登录访问受保护页面:重定向到 login_view,并带上 next 参数')
c = app.test_client(); r = c.get('/secret'); print('  GET /secret →', r.status_code, '| Location =', r.headers['Location']); R['redirect'] = [r.status_code, r.headers['Location']]
r = c.get('/'); print('  GET / →', r.get_data(as_text=True)); R['anon'] = r.get_data(as_text=True)
print('  current_user 的类型(未登录):', c.get('/whoami').get_json()); R['anon_who'] = c.get('/whoami').get_json()
print()
print('== 二:登录:login_user 往 session 里写了什么;next 回跳')
r = c.post('/login?next=/secret', data={'name': 'ann', 'pw': 'pw1'}); print('  POST /login?next=/secret →', r.status_code, '| Location =', r.headers['Location']); R['login'] = [r.status_code, r.headers['Location']]
with c: c.get('/'); print('  session 里的键:', dict(session)); R['session'] = {k: (v if k != '_id' else v[:12] + '…') for k, v in dict(session).items()}
print('  登录后 GET /secret →', c.get('/secret').get_data(as_text=True), '| whoami:', c.get('/whoami').get_json()); R['logged'] = c.get('/whoami').get_json()
print('  session cookie 的明文(base64 解码,不需要密钥):', {k: (v[:10] + '…' if k == '_id' else v) for k, v in dec([x for x in c._cookies.values() if x.key == 'session'][0].value).items()})
print()
print('== 三:每个请求都会调用 user_loader(从 session 里的 id 重新加载用户)')
loads['n'] = 0; c.get('/'); c.get('/'); c.get('/secret'); print('  3 个请求 user_loader 调用了', loads['n'], '次(每个访问 current_user 的请求一次)'); R['loads'] = loads['n']
loads['n'] = 0; c0 = app.test_client(); c0.get('/'); print('  未登录请求访问 current_user:user_loader 调用', loads['n'], '次(session 里没有 id,不调用)')
print()
print('== 四:remember me:登录时 remember=True 会多设置一个 remember_token cookie(session 丢了也能恢复登录)')
c2 = app.test_client(); r = c2.post('/login', data={'name': 'bob', 'pw': 'pw2', 'remember': '1'}); cks = r.headers.getlist('Set-Cookie'); print('  Set-Cookie:', [x.split(';')[0].split('=')[0] + '=' + x.split(';')[0].split('=')[1][:14] + '…' for x in cks], '| remember_token 的属性:', [x.split(';', 1)[1].strip() for x in cks if x.startswith('remember_token')]); R['remember'] = [x.split(';')[0].split('=')[0] for x in cks]
rt = [x for x in c2._cookies.values() if x.key == 'remember_token'][0].value; print('  remember_token 的值形如 用户id|哈希:', rt.split('|')[0], '|', rt.split('|')[1][:12] + '…'); R['rt_id'] = rt.split('|')[0]
for k in [x for x in list(c2._cookies) if 'session' in str(x)]: pass
c2._cookies = {k: v for k, v in c2._cookies.items() if v.key != 'session'}; print('  把 session cookie 删掉(只剩 remember_token)后访问 /whoami →', c2.get('/whoami').get_json()); R['restored'] = c2.get('/whoami').get_json()
print('  恢复之后 session 里 _fresh =', end=' ')
with c2: c2.get('/'); print(session.get('_fresh')); R['fresh_after_restore'] = session.get('_fresh')
r = c2.get('/sensitive'); print('  从 remember cookie 恢复的会话访问 fresh_login_required 页面 →', r.status_code, r.headers.get('Location')); R['fresh_required'] = [r.status_code, r.headers.get('Location')]
print()
print('== 五:登出:session 与 remember cookie 都被清掉')
r = c2.get('/logout'); print('  Set-Cookie:', [x.split(';')[0].split('=')[0] + '=' + x.split(';')[0].split('=')[1][:8] for x in r.headers.getlist('Set-Cookie')]); print('  登出后 whoami:', c2.get('/whoami').get_json()['auth']); R['logout'] = [x.split(';')[0].split('=')[0] for x in r.headers.getlist('Set-Cookie')]
print()
print('== 六:session_protection:basic(默认)只在身份标识(IP + User-Agent)变化时让会话变成「非 fresh」;strong 则直接清空会话')
for mode in ('basic', 'strong'):
    lm.session_protection = mode; cx = app.test_client(); cx.post('/login', data={'name': 'ann', 'pw': 'pw1'}, headers={'User-Agent': 'UA-A'}); a = cx.get('/whoami', headers={'User-Agent': 'UA-A'}).get_json()['auth']; b = cx.get('/whoami', headers={'User-Agent': 'UA-B'}).get_json()['auth']
    with cx: cx.get('/whoami', headers={'User-Agent': 'UA-B'}); fresh = session.get('_fresh')
    cy = app.test_client(); cy.post('/login', data={'name': 'ann', 'pw': 'pw1'}, headers={'User-Agent': 'UA-A'}); fr = cy.get('/sensitive', headers={'User-Agent': 'UA-B'})
    R.setdefault('prot', {})[mode] = [a, b]; print(f'  {mode:<7} 同一个 session 换 User-Agent 后 whoami 是否仍登录: {b}(原 UA 下 {a})')
lm.session_protection = 'basic'
print()
print('== 六b:未授权的处理:返回 JSON 而不是重定向(API 接口的常见需求)')
@lm.unauthorized_handler
def unauth(): return jsonify(error='login required'), 401
r = app.test_client().get('/secret'); print('  自定义 unauthorized_handler →', r.status_code, r.get_json()); R['unauth'] = [r.status_code, r.get_json()]
save('f72', R)
