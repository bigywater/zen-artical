import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f109'); R = {}
import jwt, base64, json, hmac, hashlib, datetime as dt
from flask import Flask, request, jsonify, g
SECRET = 'lab-secret-key-that-is-long-enough-32b!'
def b64d(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode()
def b64e(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
now = int(time.time())
print('== 一:JWT 的结构:三段 base64url,前两段是明文 JSON')
tok = jwt.encode({'sub': '1', 'role': 'user', 'iat': now, 'exp': now + 900}, SECRET, algorithm='HS256'); h, p, s = tok.split('.')
print('  令牌:', tok[:60] + '…', f'(长度 {len(tok)})'); print('  header   :', b64d(h)); print('  payload  :', b64d(p)); print('  signature:', f'{len(s)} 个字符的 base64url(HMAC-SHA256 的 32 字节)'); R['struct'] = [len(tok), b64d(h), b64d(p)]
print('  不验证签名也能读出 payload:', jwt.decode(tok, options={'verify_signature': False})['role'])
print()
print('== 二:验证:必须指定 algorithms;过期、未生效、签名错误')
def tryd(label, fn):
    try: r = fn(); out = f'通过 {r}' if not isinstance(r, dict) else f'通过 sub={r.get("sub")}'
    except Exception as e: out = f'{type(e).__name__}: {str(e)[:70]}'
    print(f'  {label:<34} → {out}'); R.setdefault('verify', {})[label] = out
tryd('algorithms=["HS256"]', lambda: jwt.decode(tok, SECRET, algorithms=['HS256']))
tryd('不传 algorithms', lambda: jwt.decode(tok, SECRET))
tryd('错误的密钥', lambda: jwt.decode(tok, 'wrong' * 8, algorithms=['HS256']))
exp_tok = jwt.encode({'sub': '1', 'exp': now - 10}, SECRET, algorithm='HS256'); tryd('exp 已过去 10 秒', lambda: jwt.decode(exp_tok, SECRET, algorithms=['HS256']))
tryd('exp 过去 10 秒 + leeway=30', lambda: jwt.decode(exp_tok, SECRET, algorithms=['HS256'], leeway=30))
nbf_tok = jwt.encode({'sub': '1', 'nbf': now + 60}, SECRET, algorithm='HS256'); tryd('nbf 在 60 秒之后', lambda: jwt.decode(nbf_tok, SECRET, algorithms=['HS256']))
noexp = jwt.encode({'sub': '1'}, SECRET, algorithm='HS256'); tryd('没有 exp(默认不要求)', lambda: jwt.decode(noexp, SECRET, algorithms=['HS256']))
tryd('options={"require": ["exp"]} 时没有 exp', lambda: jwt.decode(noexp, SECRET, algorithms=['HS256'], options={'require': ['exp']}))
tryd('要求 aud 但令牌没有 aud', lambda: jwt.decode(tok, SECRET, algorithms=['HS256'], audience='api'))
print()
print('== 三:经典攻击:alg 改成 none;篡改 payload 里的 role')
none_tok = b64e(json.dumps({'alg': 'none', 'typ': 'JWT'}).encode()) + '.' + b64e(json.dumps({'sub': '1', 'role': 'admin'}).encode()) + '.'
tryd('alg=none 的伪造令牌', lambda: jwt.decode(none_tok, SECRET, algorithms=['HS256']))
forged = h + '.' + b64e(json.dumps({'sub': '1', 'role': 'admin', 'exp': now + 900}).encode()) + '.' + s
tryd('改 role 为 admin、沿用旧签名', lambda: jwt.decode(forged, SECRET, algorithms=['HS256']))
try: jwt.decode(none_tok, options={'verify_signature': False}); print('  (但如果有人关掉了 verify_signature,伪造的令牌就会被接受——永远不要这样用)')
except Exception as e: print(e)
print()
print('== 四:HS256 与 RS256:对称密钥谁有谁能签发;非对称只有私钥能签发')
try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048); priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()); pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    rt = jwt.encode({'sub': '1', 'exp': now + 900}, priv, algorithm='RS256'); print(f'  RS256 令牌长度 {len(rt)}(HS256 是 {len(tok)})'); R['rs_len'] = [len(rt), len(tok)]
    tryd('公钥验证 RS256 令牌', lambda: jwt.decode(rt, pub, algorithms=['RS256']))
    tryd('算法混淆:把公钥当 HS256 密钥来签', lambda: jwt.encode({'sub': '1'}, pub, algorithm='HS256'))
    tryd('验证方同时允许 RS256 与 HS256(用公钥)', lambda: jwt.decode(jwt.encode({'sub': '1'}, 'x', algorithm='HS256'), pub, algorithms=['RS256', 'HS256']))
except ImportError as e: print('  没有 cryptography:', e); R['rs'] = 'no cryptography'
print()
print('== 五:放进 Flask:登录发令牌、受保护接口验令牌;令牌里的角色在有效期内不会跟着数据库变化')
app = Flask('jw'); app.logger.disabled = True
USERS = {'ann': {'pw': 'pw1', 'role': 'user', 'id': 1}}
@app.post('/login')
def login():
    d = request.get_json(); u = USERS.get(d.get('username'))
    if not u or not hmac.compare_digest(u['pw'], d.get('password', '')): return jsonify(error='bad credentials'), 401
    return jsonify(access_token=jwt.encode({'sub': str(u['id']), 'role': u['role'], 'iat': int(time.time()), 'exp': int(time.time()) + 900}, SECRET, algorithm='HS256'))
@app.get('/me')
def me():
    h = request.headers.get('Authorization', '')
    try: claims = jwt.decode(h.split()[1], SECRET, algorithms=['HS256'], options={'require': ['exp', 'sub']})
    except Exception as e: return jsonify(error=type(e).__name__), 401
    return jsonify(sub=claims['sub'], role=claims['role'])
c = app.test_client()
r = c.post('/login', json={'username': 'ann', 'password': 'bad'}); print('  错误密码 →', r.status_code); R['bad_login'] = r.status_code
r = c.post('/login', json={'username': 'ann', 'password': 'pw1'}); t = r.get_json()['access_token']; print('  登录 →', r.status_code, '令牌长度', len(t)); r = c.get('/me', headers={'Authorization': f'Bearer {t}'}); print('  用令牌访问 /me →', r.status_code, r.get_json())
USERS['ann']['role'] = 'banned'; r = c.get('/me', headers={'Authorization': f'Bearer {t}'}); print("  数据库里把角色改成 banned 之后,旧令牌仍然报告 role =", r.get_json()['role'], '(JWT 是自包含的)'); R['stale_role'] = r.get_json()['role']
save('f109', R)
