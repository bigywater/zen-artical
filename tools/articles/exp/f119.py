import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f119'); R = {}
import base64, zlib, json, hashlib, secrets
from flask import Flask, session, jsonify, request
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import URLSafeTimedSerializer, BadSignature
def mk(key, **cfg):
    a = Flask('k'); a.logger.disabled = True; a.config['SECRET_KEY'] = key; a.config.update(cfg)
    @a.post('/login')
    def login(): session['user'] = request.json['user']; session['role'] = 'user'; return 'ok'
    @a.get('/me')
    def me(): return jsonify(user=session.get('user'), role=session.get('role'))
    @a.get('/touch')
    def touch(): session['n'] = session.get('n', 0) + 1; return 'ok'
    return a
def cookie(r): 
    for k, v in r.headers:
        if k == 'Set-Cookie' and v.startswith('session='): return v.split(';')[0][len('session='):]
def b64d(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
def decode_payload(c):
    comp = c.startswith('.'); p = c[1:] if comp else c; p = p.split('.')[0]; raw = b64d(p); return zlib.decompress(raw).decode() if comp else raw.decode()
print('== 一:没有 SECRET_KEY 时用 session')
a = Flask('nokey'); a.logger.disabled = True; a.config['PROPAGATE_EXCEPTIONS'] = False
@a.get('/s')
def s_(): session['x'] = 1; return 'ok'
import logging
try: r = a.test_client().get('/s'); print('  HTTP', r.status_code)
except Exception as e: print('  异常:', type(e).__name__, str(e)[:90])
a.config['PROPAGATE_EXCEPTIONS'] = True
try: a.test_client().get('/s')
except Exception as e: print('  (传播出来的异常)', type(e).__name__ + ':', str(e)[:100]); R['nokey'] = f'{type(e).__name__}: {str(e)[:100]}'
print()
print('== 二:session cookie 的内容:签名,不加密——不需要密钥就能读')
KEY = 'prod-key-' + secrets.token_hex(8); app = mk(KEY); c = app.test_client(); r = c.post('/login', json={'user': 'ann'}); ck = cookie(r)
print('  cookie:', ck[:70] + '…'); print('  不用密钥解出的内容:', decode_payload(ck)); R['payload'] = decode_payload(ck); print('  cookie 的三段:', [len(x) for x in ck.split('.')], '(载荷.时间戳.签名)')
print()
print('== 三:知道 SECRET_KEY 就能伪造任意用户(用同样的序列化器签一个 role=admin 的 cookie)')
si = SecureCookieSessionInterface(); ser = si.get_signing_serializer(app); forged = ser.dumps({'user': 'mallory', 'role': 'admin'})
c2 = app.test_client(); c2.set_cookie('session', forged, domain='localhost'); r = c2.get('/me'); print('  用正确的 key 伪造的 cookie →', r.get_json()); R['forged_ok'] = r.get_json()
other = mk('some-other-key-xxxxxxxxxxxxxxxx'); ser2 = SecureCookieSessionInterface().get_signing_serializer(other); bad = ser2.dumps({'user': 'mallory', 'role': 'admin'})
c3 = app.test_client(); c3.set_cookie('session', bad, domain='localhost'); r = c3.get('/me'); print('  用错误的 key 伪造的 cookie →', r.get_json(), '(签名不对,当作没有 session)'); R['forged_bad'] = r.get_json()
tam = ck[:-3] + ('AAA' if ck[-3:] != 'AAA' else 'BBB'); c4 = app.test_client(); c4.set_cookie('session', tam, domain='localhost'); print('  篡改签名的 cookie →', c4.get('/me').get_json())
print()
print('== 四:换 SECRET_KEY:所有已登录用户的 session 立刻失效')
c = app.test_client(); c.post('/login', json={'user': 'ann'}); print('  换 key 之前:', c.get('/me').get_json())
app.config['SECRET_KEY'] = 'brand-new-key-xxxxxxxxxxxxxxxxxxxx'; print('  换 key 之后(同一个 cookie):', c.get('/me').get_json()); R['rotate_noFallback'] = c.get('/me').get_json()
print()
print('== 五:SECRET_KEY_FALLBACKS(Flask 3.1):平滑轮换——新 key 签发,旧 key 仍可验证')
old, new = 'old-key-xxxxxxxxxxxxxxxxxxxxxxxx', 'new-key-xxxxxxxxxxxxxxxxxxxxxxxx'
a_old = mk(old); co = a_old.test_client(); co.post('/login', json={'user': 'ann'}); old_cookie = cookie(co.post('/login', json={'user': 'ann'}))
a_new = mk(new, SECRET_KEY_FALLBACKS=[old]); cn = a_new.test_client(); cn.set_cookie('session', old_cookie, domain='localhost')
print('  新 key + FALLBACKS=[旧 key],带旧 cookie →', cn.get('/me').get_json()); r = cn.get('/touch'); new_cookie = cookie(r); print('  之后服务端下发的 cookie 已经用新 key 签名:', new_cookie is not None and ser_ok(new_cookie, new) if False else '', end='')
def verifies(c_, key): 
    try: URLSafeTimedSerializer(key, salt='cookie-session', serializer=SecureCookieSessionInterface.serializer, signer_kwargs={'key_derivation': 'hmac', 'digest_method': hashlib.sha1}).loads(c_); return True
    except Exception: return False
print('旧 cookie 能被旧 key 验证:', verifies(old_cookie, old), '| 新下发的 cookie 能被新 key 验证:', verifies(new_cookie, new), '| 能被旧 key 验证:', verifies(new_cookie, old)); R['fallback'] = [cn.get('/me').get_json(), verifies(new_cookie, new), verifies(new_cookie, old)]
a_nofb = mk(new); cx = a_nofb.test_client(); cx.set_cookie('session', old_cookie, domain='localhost'); print('  只有新 key、没有 FALLBACKS,带旧 cookie →', cx.get('/me').get_json()); R['no_fallback'] = cx.get('/me').get_json()
print()
print('== 六:弱 SECRET_KEY 可以被字典猜出来(只猜自己这个 cookie)')
weak = mk('dev'); cw = weak.test_client(); ckw = cookie(cw.post('/login', json={'user': 'ann'}))
WORDS = ['secret', 'password', 'changeme', 'dev', 'development', 'flask', 'key', 'mysecret', 'SECRET_KEY', 'your-secret-key'] + [f'word{i}' for i in range(200000)]
def guess(c_, words):
    for w in words:
        if verifies(c_, w): return w
t0 = time.perf_counter(); g_ = guess(ckw, WORDS); t = ms(t0); print(f'  字典猜测:猜中 {g_!r},用时 {t:.1f} ms'); R['crack_weak'] = [g_, t]
strong = mk(secrets.token_hex(32)); cs = strong.test_client(); cks = cookie(cs.post('/login', json={'user': 'ann'}))
t0 = time.perf_counter(); g2 = guess(cks, WORDS); t2 = ms(t0); n = len(WORDS); print(f'  强 key(64 个十六进制字符):试了 {n} 个候选,结果 {g2},用时 {t2:.0f} ms(约 {t2 / n * 1000:.1f} µs/个)'); R['crack_strong'] = [g2, t2, n]
print(f'  随机 32 字节 key 有 2^256 种可能;按每秒试 {n / (t2 / 1000):.0f} 个算,穷举不可行(这里没有真的穷举)')
print('  生成方式:secrets.token_hex(32) →', secrets.token_hex(32)[:16] + '…', '(64 个字符)')
save('f119', R)
