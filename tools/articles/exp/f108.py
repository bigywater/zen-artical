import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f108'); R = {}
import secrets, hashlib, hmac, base64, json, functools
from flask import Flask, request, jsonify, g, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
app = Flask('t'); app.logger.disabled = True; app.config['SECRET_KEY'] = 'lab-secret'
USERS = {1: {'name': 'ann', 'role': 'user'}, 2: {'name': 'root', 'role': 'admin'}}
TOKENS = {}   # sha256(token) -> user id(只存哈希)
def issue(uid): t = secrets.token_urlsafe(32); TOKENS[hashlib.sha256(t.encode()).hexdigest()] = uid; return t
ser = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='api')
def bearer():
    h = request.headers.get('Authorization', '')
    if not h: return None, 'missing'
    p = h.split(None, 1)
    if len(p) != 2 or p[0].lower() != 'bearer': return None, 'malformed'
    return p[1], None
def need(kind='opaque', role=None):
    def deco(f):
        @functools.wraps(f)
        def w(*a, **k):
            tok, err = bearer()
            if err: 
                r = jsonify(error='unauthorized', reason=err); r.status_code = 401; r.headers['WWW-Authenticate'] = 'Bearer realm="api"'; return r
            if kind == 'opaque': uid = TOKENS.get(hashlib.sha256(tok.encode()).hexdigest())
            else:
                try: uid = ser.loads(tok, max_age=int(app.config.get('TOK_AGE', 3600)))['uid']
                except SignatureExpired: r = jsonify(error='token expired'); r.status_code = 401; r.headers['WWW-Authenticate'] = 'Bearer error="invalid_token"'; return r
                except BadSignature: uid = None
            if uid is None or uid not in USERS:
                r = jsonify(error='invalid token'); r.status_code = 401; r.headers['WWW-Authenticate'] = 'Bearer error="invalid_token"'; return r
            if role and USERS[uid]['role'] != role: return jsonify(error='forbidden'), 403
            g.uid = uid; return f(*a, **k)
        return w
    return deco
@app.get('/me')
@need()
def me(): return jsonify(uid=g.uid)
@app.get('/admin')
@need(role='admin')
def admin(): return jsonify(ok=True)
@app.get('/me-signed')
@need('signed')
def me2(): return jsonify(uid=g.uid)
c = app.test_client()
t1 = issue(1); t2 = issue(2)
def show(label, r): print(f'  {label:<36} → {r.status_code} {r.get_data(as_text=True).strip()[:60]} | WWW-Authenticate: {r.headers.get("WWW-Authenticate")}'); return r
print('== 一:Bearer 令牌的几种请求:没有头、格式错、错误令牌、正确令牌')
R['basic'] = {}
for label, h in (('没有 Authorization 头', {}), ('Authorization: Token abc(不是 Bearer)', {'Authorization': 'Token abc'}), ('Authorization: Bearer(没有令牌)', {'Authorization': 'Bearer'}), ('Authorization: Bearer 错误令牌', {'Authorization': 'Bearer nope'}), ('Authorization: bearer 正确令牌(小写)', {'Authorization': f'bearer {t1}'}), ('Authorization: Bearer 正确令牌', {'Authorization': f'Bearer {t1}'})):
    r = show(label, c.get('/me', headers=h)); R['basic'][label] = [r.status_code, r.headers.get('WWW-Authenticate')]
print('  401 与 403:普通用户访问 /admin →', c.get('/admin', headers={'Authorization': f'Bearer {t1}'}).status_code, '| 管理员 →', c.get('/admin', headers={'Authorization': f'Bearer {t2}'}).status_code); R['rbac'] = [c.get('/admin', headers={'Authorization': f'Bearer {t1}'}).status_code, c.get('/admin', headers={'Authorization': f'Bearer {t2}'}).status_code]
print()
print('== 二:令牌怎么存:只存哈希;令牌本身的长度与熵')
print(f'  令牌 {t1} (长度 {len(t1)},secrets.token_urlsafe(32) = 32 字节随机数 → 43 个字符)'); R['tok_len'] = len(t1)
print('  服务端存的是 sha256 十六进制:', list(TOKENS)[0][:24] + '…', f'(长度 {len(list(TOKENS)[0])})——数据库泄漏时拿不到可用令牌'); print('  对比 hmac.compare_digest("a", "a") =', hmac.compare_digest('a', 'a'), '(比较哈希时用它,不用 ==)')
print()
print('== 三:签名令牌(itsdangerous):无状态,自带过期;内容是明文可读的')
st = ser.dumps({'uid': 1}); print('  令牌:', st); R['signed'] = st
payload = st.split('.')[0]; print('  不需要密钥就能解出 payload:', base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)).decode()); R['payload'] = base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)).decode()
r = c.get('/me-signed', headers={'Authorization': f'Bearer {st}'}); print('  验证通过 →', r.status_code, r.get_json())
tampered = st[:-2] + ('AA' if st[-2:] != 'AA' else 'BB'); r = c.get('/me-signed', headers={'Authorization': f'Bearer {tampered}'}); print('  篡改签名 →', r.status_code, r.get_json()); R['tampered'] = r.status_code
forged = base64.urlsafe_b64encode(b'{"uid": 2}').decode().rstrip('=') + '.' + st.split('.', 1)[1]; r = c.get('/me-signed', headers={'Authorization': f'Bearer {forged}'}); print('  改 payload 里的 uid 为 2(沿用原签名)→', r.status_code); R['forged'] = r.status_code
app.config['TOK_AGE'] = 1; time.sleep(2.1); r = c.get('/me-signed', headers={'Authorization': f'Bearer {st}'}); print('  max_age=1 秒,等 2 秒后 →', r.status_code, r.get_json()); R['expired'] = [r.status_code, r.get_json()]; app.config['TOK_AGE'] = 3600
print()
print('== 四:吊销:不透明令牌删掉记录立即失效;签名令牌在过期前仍然有效(除非另查一次用户状态)')
st2 = ser.dumps({'uid': 1}); TOKENS.clear(); t3 = issue(1)
del TOKENS[hashlib.sha256(t3.encode()).hexdigest()]
print('  不透明令牌删除后 →', c.get('/me', headers={'Authorization': f'Bearer {t3}'}).status_code); R['revoke_opaque'] = c.get('/me', headers={'Authorization': f'Bearer {t3}'}).status_code
print('  签名令牌:吊销动作之后(这里没有存储可删)→', c.get('/me-signed', headers={'Authorization': f'Bearer {st2}'}).status_code, '(仍然 200,要吊销必须另存黑名单或检查用户状态)'); R['revoke_signed'] = c.get('/me-signed', headers={'Authorization': f'Bearer {st2}'}).status_code
USERS_BAK = dict(USERS); USERS.pop(1); print('  用户被删除后签名令牌 →', c.get('/me-signed', headers={'Authorization': f'Bearer {st2}'}).status_code, '(因为视图里还检查了用户是否存在)'); USERS.update(USERS_BAK)
print()
print('== 五:令牌放在查询参数里会进访问日志(用 gunicorn 的访问日志验证)')
d = mkapp('f108', {'app.py': 'from flask import Flask, request\napp = Flask(__name__)\n@app.get("/me")\ndef me(): return "ok"\n'})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--access-logfile', '-', 'app:app']) as s:
    s.get('/me?token=SECRET-IN-QUERY'); s.get('/me', headers={'Authorization': 'Bearer SECRET-IN-HEADER'}); time.sleep(0.3); log = s.logtext()
print('  日志里能搜到查询参数里的令牌:', 'SECRET-IN-QUERY' in log, '| 能搜到头里的令牌:', 'SECRET-IN-HEADER' in log); R['logleak'] = ['SECRET-IN-QUERY' in log, 'SECRET-IN-HEADER' in log]
print('  访问日志行示例:', [l for l in log.splitlines() if 'token=' in l][0][:110])
save('f108', R)
