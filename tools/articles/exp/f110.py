import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f110'); R = {}
import jwt, secrets, hashlib, hmac
from flask import Flask, request, jsonify, make_response
SECRET = 'lab-secret-key-that-is-long-enough-32b!'
app = Flask('rt'); app.logger.disabled = True
ACCESS_TTL = 2; REFRESH_TTL = 5
RT = {}   # sha256(refresh) -> {uid, family, used, expires, revoked}
FAM = {}  # family -> revoked?
def h(t): return hashlib.sha256(t.encode()).hexdigest()
def issue_access(uid): return jwt.encode({'sub': str(uid), 'exp': int(time.time()) + ACCESS_TTL}, SECRET, algorithm='HS256')
def issue_refresh(uid, family): t = secrets.token_urlsafe(32); RT[h(t)] = {'uid': uid, 'family': family, 'used': False, 'expires': time.time() + REFRESH_TTL}; return t
@app.post('/login')
def login():
    fam = secrets.token_hex(4); FAM[fam] = False; return jsonify(access=issue_access(1), refresh=issue_refresh(1, fam))
@app.post('/refresh')
def refresh():
    t = request.get_json().get('refresh', ''); rec = RT.get(h(t))
    if not rec: return jsonify(error='unknown refresh token'), 401
    if FAM[rec['family']]: return jsonify(error='family revoked'), 401
    if time.time() > rec['expires']: return jsonify(error='refresh token expired'), 401
    if rec['used']:
        FAM[rec['family']] = True; return jsonify(error='refresh token reuse detected; family revoked'), 401
    rec['used'] = True; return jsonify(access=issue_access(rec['uid']), refresh=issue_refresh(rec['uid'], rec['family']))
@app.post('/logout')
def logout():
    rec = RT.get(h(request.get_json().get('refresh', '')))
    if rec: FAM[rec['family']] = True
    return '', 204
@app.get('/me')
def me():
    try: return jsonify(sub=jwt.decode(request.headers['Authorization'].split()[1], SECRET, algorithms=['HS256'])['sub'])
    except Exception as e: return jsonify(error=type(e).__name__), 401
@app.post('/login-cookie')
def login_cookie():
    fam = secrets.token_hex(4); FAM[fam] = False; r = make_response(jsonify(access=issue_access(1)))
    r.set_cookie('refresh', issue_refresh(1, fam), httponly=True, secure=True, samesite='Strict', path='/refresh', max_age=REFRESH_TTL); return r
c = app.test_client()
def auth(t): return {'Authorization': f'Bearer {t}'}
print(f'== 一:短命的访问令牌({ACCESS_TTL} 秒,演示用)+ 较长的刷新令牌({REFRESH_TTL} 秒):过期后用刷新令牌换新的')
d = c.post('/login').get_json(); print('  登录得到 access + refresh;/me →', c.get('/me', headers=auth(d['access'])).status_code)
time.sleep(ACCESS_TTL + 0.3); r = c.get('/me', headers=auth(d['access'])); print(f'  {ACCESS_TTL} 秒后 /me →', r.status_code, r.get_json()); R['access_expired'] = [r.status_code, r.get_json()]
r = c.post('/refresh', json={'refresh': d['refresh']}); d2 = r.get_json(); print('  /refresh →', r.status_code, '拿到新的 access 与新的 refresh(两者都变了):', d2['access'] != d['access'], d2['refresh'] != d['refresh']); print('  新 access 访问 /me →', c.get('/me', headers=auth(d2['access'])).status_code); R['refresh'] = r.status_code
print()
print('== 二:刷新令牌轮换与重用检测:旧的刷新令牌再用一次(像是被偷了)')
r = c.post('/refresh', json={'refresh': d['refresh']}); print('  再用已经用过的旧 refresh →', r.status_code, r.get_json()); R['reuse'] = [r.status_code, r.get_json()]
r = c.post('/refresh', json={'refresh': d2['refresh']}); print('  此后连合法的新 refresh 也失效 →', r.status_code, r.get_json()); R['family_dead'] = [r.status_code, r.get_json()]
print('  (整个「家族」被撤销:攻击者和真用户都得重新登录)')
print()
print('== 三:正常用户的副作用:刷新响应丢了(网络问题),客户端用同一个旧令牌重试')
d = c.post('/login').get_json(); r1 = c.post('/refresh', json={'refresh': d['refresh']}); print('  第一次 /refresh →', r1.status_code, '(但假设响应在路上丢了,客户端没收到新令牌)'); r2 = c.post('/refresh', json={'refresh': d['refresh']}); print('  客户端用旧令牌重试 →', r2.status_code, r2.get_json()); r3 = c.post('/refresh', json={'refresh': r1.get_json()['refresh']}); print('  服务端发出的那个新令牌也作废了 →', r3.status_code); R['lost'] = [r1.status_code, r2.status_code, r3.status_code]
print('  (严格的轮换会把这种合法重试当成重用;常见的缓解是给旧令牌一个几秒的宽限期——本篇没有实现)')
print()
print('== 四:登出与过期')
d = c.post('/login').get_json(); c.post('/logout', json={'refresh': d['refresh']}); r = c.post('/refresh', json={'refresh': d['refresh']}); print('  登出后用刷新令牌 →', r.status_code, r.get_json()); R['logout'] = r.get_json()
print('  但登出前签发的访问令牌还能用(过期前):/me →', c.get('/me', headers=auth(d['access'])).status_code); R['access_after_logout'] = c.get('/me', headers=auth(d['access'])).status_code
d = c.post('/login').get_json(); time.sleep(REFRESH_TTL + 0.3); r = c.post('/refresh', json={'refresh': d['refresh']}); print(f'  刷新令牌放了 {REFRESH_TTL} 秒之后 →', r.status_code, r.get_json()); R['rt_expired'] = r.get_json()
r = c.post('/refresh', json={'refresh': 'garbage'}); print('  乱写的刷新令牌 →', r.status_code, r.get_json())
print()
print('== 五:刷新令牌放进 HttpOnly cookie:限定路径,JS 读不到')
r = c.post('/login-cookie'); sc = r.headers.get('Set-Cookie'); print('  Set-Cookie:', sc.split('=', 1)[0] + '=<令牌>' + sc[sc.index(';'):]); R['cookie'] = sc.split('=', 1)[0] + '=<令牌>' + sc[sc.index(';'):]
print('  响应正文里只有 access,没有 refresh:', list(r.get_json().keys())); R['cookie_body'] = list(r.get_json().keys())
save('f110', R)
