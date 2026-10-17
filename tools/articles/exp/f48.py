import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f48'); R = {}
import base64, json, zlib, datetime as dt, uuid, warnings, secrets
from flask import Flask, session, request
from markupsafe import Markup
app = Flask('sess'); app.logger.disabled = True; app.secret_key = 'lab-secret'
def b64d(x): return base64.urlsafe_b64decode(x + '=' * (-len(x) % 4))
def decode_cookie(value):
    """不用密钥,只靠 base64 与 zlib 看 cookie 里装了什么;返回 (是否压缩, 段数, payload 文本, 签发时间)"""
    comp = value.startswith('.'); v = value[1:] if comp else value; p = v.split('.'); raw = b64d(p[0])
    if comp: raw = zlib.decompress(raw)
    return comp, len(p), raw.decode(), dt.datetime.fromtimestamp(int.from_bytes(b64d(p[1]), 'big'), dt.timezone.utc).isoformat()
@app.get('/basic')
def basic(): session['user'] = 'ann'; session['n'] = 1; return 'ok'
@app.get('/types')
def types():
    session['dt'] = dt.datetime(2026, 10, 2, 12, 0, tzinfo=dt.timezone.utc); session['bytes'] = b'\x00\xffab'; session['tuple'] = (1, 2); session['uuid'] = uuid.UUID(int=255); session['markup'] = Markup('<b>x</b>'); session['list'] = [1, {'a': (3, 4)}]; return 'ok'
@app.get('/perm')
def perm(): session.permanent = True; session['u'] = 1; return 'ok'
@app.get('/touch')
def touch(): return str(session.get('user'))
@app.get('/modify')
def modify(): session['k'] = 'v'; return 'ok'
@app.get('/clear')
def clear(): session.clear(); return 'ok'
@app.get('/big/<int:n>')
def big(n): session['d'] = secrets.token_hex(n // 2); return 'ok'
@app.get('/rep/<int:n>')
def rep(n): session['d'] = 'x' * n; return 'ok'
@app.get('/read')
def read(): return dict(session)
print('== 一:一个最简单的 session:Set-Cookie 里的值解开后是什么(不需要密钥就能解开——没有加密)')
c = app.test_client(); r = c.get('/basic'); sc = r.headers['Set-Cookie']; print('  Set-Cookie:', sc); R['sc'] = sc
val = sc.split(';')[0].split('=', 1)[1]; comp, nparts, payload, ts = decode_cookie(val); print(f'  cookie 值分 {nparts} 段;压缩={comp};payload = {payload};签发时间 = {ts}'); R['dec'] = [nparts, comp, payload, ts]
print()
print('== 二:非 JSON 类型:Flask 用带标记的 JSON(TaggedJSONSerializer),标记是一个空格加单字母的键')
r = c.get('/types'); val = r.headers['Set-Cookie'].split(';')[0].split('=', 1)[1]; comp, nparts, payload, ts = decode_cookie(val); print('  payload =', payload); R['tagged'] = payload
c2 = app.test_client(); c2.get('/types')
with c2: c2.get('/touch'); print('  session 里的真实类型:', {k: type(v).__name__ for k, v in session.items()}); R['types_back'] = {k: type(v).__name__ for k, v in session.items()}
print()
print('== 三:permanent 与否:不 permanent 的 session 是「浏览器会话 cookie」(没有 Expires/Max-Age);permanent 才有 Expires 与 Max-Age')
r1 = app.test_client().get('/basic'); r2 = app.test_client().get('/perm'); print('  非 permanent:', r1.headers['Set-Cookie'].split(';', 1)[1].strip()); print('  permanent   :', r2.headers['Set-Cookie'].split(';', 1)[1].strip()); R['perm'] = [r1.headers['Set-Cookie'].split(';', 1)[1].strip(), r2.headers['Set-Cookie'].split(';', 1)[1].strip()]
print('  PERMANENT_SESSION_LIFETIME =', app.config['PERMANENT_SESSION_LIFETIME'])
print()
print('== 四:什么时候重发 Set-Cookie:没改动不发;改了才发;permanent 的 session 每次请求都刷新(SESSION_REFRESH_EACH_REQUEST=True 默认)')
def sets(cl, path): return 'Set-Cookie' in cl.get(path).headers
cn = app.test_client(); cn.get('/basic'); R['resend'] = {}
R['resend']['非 permanent:只读一下'] = sets(cn, '/touch'); R['resend']['非 permanent:修改'] = sets(cn, '/modify')
cp = app.test_client(); cp.get('/perm'); R['resend']['permanent:只读一下'] = sets(cp, '/touch')
app.config['SESSION_REFRESH_EACH_REQUEST'] = False; R['resend']['permanent + REFRESH=False:只读一下'] = sets(cp, '/touch'); app.config['SESSION_REFRESH_EACH_REQUEST'] = True
for k, v in R['resend'].items(): print(f'  {k:<36} → {"发 Set-Cookie" if v else "不发"}')
print()
print('== 五:登出 session.clear():发出一个立即过期的 Set-Cookie')
c3 = app.test_client(); c3.get('/basic'); r = c3.get('/clear'); print('  Set-Cookie:', r.headers.get('Set-Cookie')); R['clear'] = r.headers.get('Set-Cookie')
print()
print('== 六:大小与压缩:随机内容不可压缩,cookie 会越来越大;超过 4093 字节发警告;重复内容会被 zlib 压缩(值以 . 开头)')
R['size'] = {}
for kind, path, ns in (('随机十六进制', '/big', (100, 1000, 3000, 5000, 8000)), ('重复的 x', '/rep', (100, 1000, 5000))):
    for n in ns:
        with warnings.catch_warnings(record=True) as W:
            warnings.simplefilter('always'); r = app.test_client().get(f'{path}/{n}')
        ck = r.headers['Set-Cookie'].split(';')[0].split('=', 1)[1]; R['size'][f'{kind} {n}'] = [len(ck), ck.startswith('.'), len(W)]
        print(f'  {kind:<8} {n:>5} 字符 → cookie 值 {len(ck):>5} 字节 | {"已压缩" if ck.startswith(".") else "未压缩"} | 警告 {len(W)} 条')
print()
print('== 七:篡改 cookie:改一个字符 → 签名不匹配 → session 是空的(不抛异常,静默当作没登录)')
c4 = app.test_client(); c4.get('/basic'); ck = [x for x in c4._cookies.values()][0]; good = ck.value
c5 = app.test_client(use_cookies=False)
R['tamper'] = {}
for label, v in (('原样', good), ('改 payload 第 5 个字符', good[:4] + ('A' if good[4] != 'A' else 'B') + good[5:]), ('换成别的密钥签的', None)):
    if v is None:
        from itsdangerous import URLSafeTimedSerializer; v = URLSafeTimedSerializer('wrong', salt='cookie-session', serializer=app.session_interface.get_signing_serializer(app).serializer, signer_kwargs={'key_derivation': 'hmac', 'digest_method': __import__('hashlib').sha1}).dumps({'user': 'root'})
    r = c5.get('/read', headers={'Cookie': 'session=' + v}); R['tamper'][label] = [r.status_code, r.get_json()]; print(f'  {label:<26} → {r.status_code} {r.get_json()}')
print()
print('== 八:Flask 用的签名参数(取自 SecureCookieSessionInterface):salt、key_derivation、digest_method')
si = app.session_interface; print('  salt =', si.salt, '| key_derivation =', si.key_derivation, '| digest_method =', si.digest_method.__name__ if hasattr(si.digest_method, '__name__') else si.digest_method, '| serializer =', type(si.serializer).__name__); R['si'] = [si.salt, si.key_derivation, getattr(si.digest_method, '__name__', str(si.digest_method)), type(si.serializer).__name__]
save('f48', R)
