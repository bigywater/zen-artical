import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f120'); R = {}
import warnings, datetime as dt
from flask import Flask, session, jsonify, request
def mk(**cfg):
    a = Flask('c'); a.logger.disabled = True; a.config['SECRET_KEY'] = 'k' * 32; a.config.update(cfg)
    @a.post('/login')
    def login(): session['u'] = 'ann'; session.permanent = request.args.get('perm') == '1'; return 'ok'
    @a.get('/read')
    def read(): return jsonify(u=session.get('u'))
    @a.get('/none')
    def none(): return 'no session access'
    @a.post('/big')
    def big(): import secrets; session['blob'] = secrets.token_hex(int(request.args['n']) // 2); return 'ok'
    return a
def sc(r): 
    L = [v for k, v in r.headers if k == 'Set-Cookie']; return L[0] if L else None
def attrs(s): 
    if not s: return None
    parts = [p.strip() for p in s.split(';')]; return [parts[0].split('=')[0] + '=<值>'] + parts[1:]
print('== 一:默认配置的 Set-Cookie')
r = mk().test_client().post('/login'); print('  ', attrs(sc(r))); R['default'] = attrs(sc(r))
print()
print('== 二:各个配置项对应的 Set-Cookie 属性')
R['cfg'] = {}
for label, cfg in (('SESSION_COOKIE_SECURE=True', {'SESSION_COOKIE_SECURE': True}), ('SESSION_COOKIE_HTTPONLY=False', {'SESSION_COOKIE_HTTPONLY': False}), ("SESSION_COOKIE_SAMESITE='Lax'", {'SESSION_COOKIE_SAMESITE': 'Lax'}), ("SESSION_COOKIE_SAMESITE='Strict'", {'SESSION_COOKIE_SAMESITE': 'Strict'}), ("SESSION_COOKIE_SAMESITE='None'(没配 Secure)", {'SESSION_COOKIE_SAMESITE': 'None'}), ("SESSION_COOKIE_NAME='__Host-sid' + Secure", {'SESSION_COOKIE_NAME': '__Host-sid', 'SESSION_COOKIE_SECURE': True}), ("SESSION_COOKIE_PATH='/app'", {'SESSION_COOKIE_PATH': '/app'}), ("SESSION_COOKIE_DOMAIN='.example.com'", {'SESSION_COOKIE_DOMAIN': '.example.com'}), ('SESSION_COOKIE_PARTITIONED=True', {'SESSION_COOKIE_PARTITIONED': True})):
    try: r = mk(**cfg).test_client().post('/login'); out = attrs(sc(r))
    except Exception as e: out = f'{type(e).__name__}: {e}'
    print(f'  {label:<44} → {out}'); R['cfg'][label] = out
print()
print('== 三:permanent 与浏览器会话 cookie:Expires / Max-Age')
for label, q, cfg in (('不设 permanent', '', {}), ('session.permanent=True(默认 31 天)', '?perm=1', {}), ('PERMANENT_SESSION_LIFETIME=1 小时', '?perm=1', {'PERMANENT_SESSION_LIFETIME': dt.timedelta(hours=1)})):
    r = mk(**cfg).test_client().post('/login' + q); print(f'  {label:<36} → {attrs(sc(r))[1:]}'); R.setdefault('perm', {})[label] = attrs(sc(r))[1:]
print()
print('== 四:什么时候服务端会重新下发 cookie(SESSION_REFRESH_EACH_REQUEST)')
for label, cfg, q in (('非 permanent,只读请求', {}, ''), ('permanent,只读请求(默认 REFRESH=True)', {}, '?perm=1'), ('permanent,只读请求,REFRESH=False', {'SESSION_REFRESH_EACH_REQUEST': False}, '?perm=1')):
    a = mk(**cfg); c = a.test_client(); c.post('/login' + q); r = c.get('/read'); print(f'  {label:<42} → 响应里有 Set-Cookie: {sc(r) is not None}'); R.setdefault('refresh', {})[label] = sc(r) is not None
r = c.get('/none'); print('  不碰 session 的请求有没有 Vary: Cookie:', r.headers.get('Vary')); r = c.get('/read'); print('  读了 session 的请求:Vary =', r.headers.get('Vary')); R['vary'] = r.headers.get('Vary')
print()
print('== 五:cookie 太大:浏览器通常限制约 4093 字节')
a = mk(); c = a.test_client()
for n in (1000, 5000, 7000, 9000):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always'); r = c.post(f'/big?n={n}')
    print(f'  session 里放 {n} 字节 → Set-Cookie 长度 {len(sc(r) or "")} | 警告:{str(w[0].message)[:110] if w else "无"}'); R.setdefault('big', {})[n] = [len(sc(r) or ''), str(w[0].message)[:160] if w else None]
print()
print('== 六:Secure cookie 在 http 下:用真实的 curl 与 gunicorn 验证(Werkzeug 的 test client 不执行 Secure 规则)')
a = mk(SESSION_COOKIE_SECURE=True); c_ = a.test_client(); c_.post('/login', base_url='http://localhost'); print('  test client 在 http 下登录后读 session →', c_.get('/read', base_url='http://localhost').get_json(), '(test client 不检查 Secure,不能用它验证这个属性)'); R['tc_ignores_secure'] = c_.get('/read', base_url='http://localhost').get_json()
from fl import app as mkapp
APP = """
from flask import Flask, session, jsonify
import os
app = Flask(__name__); app.config['SECRET_KEY'] = 'k' * 32; app.config['SESSION_COOKIE_SECURE'] = os.environ['SEC'] == '1'
@app.post('/login')
def login(): session['u'] = 'ann'; return 'ok'
@app.get('/read')
def read(): return jsonify(u=session.get('u'))
"""
d = mkapp('f120', {'app.py': APP}); R['curl'] = {}
for sec in ('0', '1'):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], SEC=sec) as s:
        jar = str(d / f'jar{sec}.txt')
        r1 = subprocess.run(['curl', '-s', '-i', '-c', jar, '-X', 'POST', f'http://127.0.0.1:{s.port}/login'], capture_output=True, text=True).stdout; sc_ = [l.strip() for l in r1.splitlines() if l.lower().startswith('set-cookie')]
        r2 = subprocess.run(['curl', '-s', '-b', jar, f'http://127.0.0.1:{s.port}/read'], capture_output=True, text=True).stdout.strip()
        print(f'  SESSION_COOKIE_SECURE={"True" if sec == "1" else "False"}:Set-Cookie 带 Secure = {"Secure" in (sc_[0] if sc_ else "")};之后 curl 经 http 带着 cookie 罐请求 /read → {r2}'); R['curl'][sec] = [('Secure' in (sc_[0] if sc_ else '')), r2]
save('f120', R)
