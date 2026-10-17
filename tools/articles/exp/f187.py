import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import json as _j
tee('f187'); R = {}
APP = '''
import os
from flask import Flask, session, request, jsonify
from itsdangerous import URLSafeTimedSerializer
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SK"]
if os.environ.get("FB"): app.config["SECRET_KEY_FALLBACKS"] = os.environ["FB"].split(",")
app.config["SESSION_REFRESH_EACH_REQUEST"] = os.environ.get("REFRESH", "1") == "1"
@app.get("/login")
def login(): session["user"] = "ann"; session.permanent = os.environ.get("PERM") == "1"; return "logged in"
@app.get("/me")
def me(): return jsonify(user=session.get("user"))
@app.get("/token")
def token(): return URLSafeTimedSerializer(app.config["SECRET_KEY"]).dumps({"uid": 7})
@app.get("/token-check")
def tcheck():
    try: return jsonify(ok=URLSafeTimedSerializer(app.config["SECRET_KEY"]).loads(request.args["t"], max_age=3600))
    except Exception as e: return jsonify(error=type(e).__name__), 400
@app.get("/token-check-multi")
def tcheck2():
    keys = [app.config["SECRET_KEY"], *app.config.get("SECRET_KEY_FALLBACKS", [])]
    try: return jsonify(ok=URLSafeTimedSerializer(keys).loads(request.args["t"], max_age=3600))
    except Exception as e: return jsonify(error=type(e).__name__), 400
'''
d = mkapp('f187', {'app.py': APP})
def cookie_of(r): 
    for k, v in r[1]:
        if k.lower() == 'set-cookie' and v.startswith('session='): return v.split(';')[0]
def setcookie(r): return any(k.lower() == 'set-cookie' for k, v in r[1])
def me(s, ck): r = s.get('/me', headers={'Cookie': ck} if ck else {}); return _j.loads(r[2])['user'], setcookie(r), cookie_of(r)
def srv(sk, fb='', **ex): return Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'app:app'], SK=sk, FB=fb, **ex)
print('== 一:直接换 SECRET_KEY(旧 → 新,没有 fallback):旧的 session cookie 还能用吗')
with srv('old-key') as a: ck_old = cookie_of(a.get('/login')); u0 = me(a, ck_old)[0]
with srv('new-key') as b: u1, sc, _ = me(b, ck_old)
print(f'  旧 key 的服务:用旧 cookie 请求 /me → user={u0!r}\n  换成新 key 重启后:用同一个旧 cookie → user={u1!r}(session 被当作空的,用户退出登录),响应是否重新下发 cookie:{sc}')
R['direct'] = [u0, u1, sc]
print()
print('== 二:SECRET_KEY_FALLBACKS=[旧 key]:旧 cookie 还能读;新 cookie 什么时候换成新 key 签名')
R['fb'] = {}
with srv('old-key') as a: ck_old = cookie_of(a.get('/login'))
for label, ex in (('session 只读,不修改(默认会话 cookie)', {'REFRESH': '1', 'PERM': '0'}), ('permanent session(每次请求刷新过期时间)', {'REFRESH': '1', 'PERM': '1'})):
    with srv('old-key', **ex) as a: ck_old = cookie_of(a.get('/login'))
    with srv('new-key', 'old-key', **ex) as b:
        u, sc, ck2 = me(b, ck_old)
    with srv('new-key', **ex) as c_: u2 = me(c_, ck2)[0] if ck2 else None
    print(f'  [{label}] 新 key + fallback 读旧 cookie → user={u!r};响应重新下发 cookie:{sc};新下发的 cookie 能被只有新 key 的服务读出:{u2!r}' if sc else f'  [{label}] 新 key + fallback 读旧 cookie → user={u!r};响应重新下发 cookie:{sc}(cookie 还是旧 key 签的)')
    R['fb'][label] = [u, sc, u2 if sc else None]
print()
print('== 三:滚动发布期间两台实例并存:三个阶段下,A 实例签的 cookie 能否被 B 实例接受,反之亦然')
phases = (('做法 1:一步到位(A 旧 key,B 新 key + fallback 旧)', ('old', '', 'new', 'old')),
          ('做法 2 第一步:全体 SECRET_KEY=旧,FALLBACKS=[新](先让所有实例能认新 key)', ('old', 'new', 'old', 'new')),
          ('做法 2 第二步:全体 SECRET_KEY=新,FALLBACKS=[旧]', ('new', 'old', 'new', 'old')))
R['phase'] = {}
for label, (ska, fba, skb, fbb) in phases:
    with srv(ska + '-key', fba + '-key' if fba else '') as a, srv(skb + '-key', fbb + '-key' if fbb else '') as b:
        ca = cookie_of(a.get('/login')); cb = cookie_of(b.get('/login')); ab = me(b, ca)[0]; ba = me(a, cb)[0]
    print(f'  {label}\n     A 签的 cookie 给 B → {ab!r};B 签的 cookie 给 A → {ba!r}'); R['phase'][label] = [ab, ba]
print()
print('== 四:itsdangerous 自己签的令牌(如重置密码链接)不会自动用 fallback:换 key 后旧令牌')
with srv('old-key') as a: tok = a.get('/token')[2].decode()
with srv('new-key', 'old-key') as b:
    r1 = b.get('/token-check?t=' + tok); r2 = b.get('/token-check-multi?t=' + tok)
print(f'  新 key + SECRET_KEY_FALLBACKS 配了旧 key,但令牌校验代码只用 app.config["SECRET_KEY"]:HTTP {r1[0]} {r1[2].decode().strip()}')
print(f'  校验代码改成 URLSafeTimedSerializer([新 key, 旧 key]):HTTP {r2[0]} {r2[2].decode().strip()}')
R['tok'] = [r1[0], r1[2].decode().strip(), r2[0], r2[2].decode().strip()]
save('f187', R)
