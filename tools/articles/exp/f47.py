import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f47'); R = {}
import base64, hashlib, hmac, json, time, datetime as dt
from itsdangerous import URLSafeTimedSerializer, URLSafeSerializer, TimestampSigner, BadSignature, SignatureExpired, BadTimeSignature, BadPayload
from flask import Flask, request, make_response, jsonify
SECRET = 'lab-secret'
s = URLSafeTimedSerializer(SECRET, salt='auth-cookie')
print('== 一:签名后的值长什么样:payload.timestamp.signature 三段,都是 URL 安全的 base64')
tok = s.dumps({'uid': 42, 'role': 'admin'}); print('  token =', tok); R['token'] = tok
parts = tok.split('.'); print('  分成', len(parts), '段:', [len(p) for p in parts], '字符'); R['parts'] = len(parts)
def b64d(x): return base64.urlsafe_b64decode(x + '=' * (-len(x) % 4))
print('  第 1 段(payload)base64 解码 →', b64d(parts[0]).decode()); print('  第 2 段(时间戳)解码为整数 →', int.from_bytes(b64d(parts[1]), 'big'), '→', dt.datetime.fromtimestamp(int.from_bytes(b64d(parts[1]), 'big'), dt.timezone.utc).isoformat()); R['payload'] = b64d(parts[0]).decode(); R['ts'] = int.from_bytes(b64d(parts[1]), 'big')
print('  第 3 段(签名)解码后的字节数 →', len(b64d(parts[2])), '(HMAC-SHA1 的输出是 20 字节)'); R['sig_len'] = len(b64d(parts[2]))
print('  结论:payload 没有加密,任何人拿到 cookie 都能读;签名只保证「没被改过」。')
print()
print('== 二:自己按 itsdangerous 的算法手工算一遍签名(django-concat 密钥派生 + HMAC-SHA1),与库的结果比对')
key = hashlib.sha1(b'auth-cookie' + b'signer' + SECRET.encode()).digest()
signing_input = (parts[0] + '.' + parts[1]).encode(); mine = base64.urlsafe_b64encode(hmac.new(key, signing_input, hashlib.sha1).digest()).rstrip(b'=').decode()
print('  手算签名 =', mine); print('  token 里的签名 =', parts[2]); print('  相同:', mine == parts[2]); R['manual_ok'] = mine == parts[2]
print('  派生密钥 = sha1(salt + "signer" + secret_key) 的前 8 字节(十六进制):', key[:8].hex()); R['key_head'] = key[:8].hex()
print()
print('== 三:篡改与伪造:改 payload、改时间戳、换密钥、换 salt、截断、乱码')
def tryload(label, token, ser=s, **kw):
    try: v = ser.loads(token, **kw); r = f'通过 → {v}'
    except Exception as e: r = f'{type(e).__name__}: {str(e)[:70]}'
    R.setdefault('tamper', {})[label] = r; print(f'  {label:<28} → {r}')
tryload('原样', tok)
forged = base64.urlsafe_b64encode(json.dumps({'uid': 1, 'role': 'root'}, separators=(',', ':')).encode()).rstrip(b'=').decode()
tryload('改 payload(签名不变)', forged + '.' + parts[1] + '.' + parts[2])
tryload('改时间戳(签名不变)', parts[0] + '.' + base64.urlsafe_b64encode((int.from_bytes(b64d(parts[1]), 'big') + 1000).to_bytes(4, 'big')).rstrip(b'=').decode() + '.' + parts[2])
tryload('用另一个密钥验证', tok, URLSafeTimedSerializer('other-secret', salt='auth-cookie'))
tryload('用另一个 salt 验证', tok, URLSafeTimedSerializer(SECRET, salt='other-salt'))
tryload('截断', tok[:-5]); tryload('去掉签名段', '.'.join(parts[:2])); tryload('随机字符串', 'not-a-token')
print()
print('== 四:过期:loads(max_age=秒)——时间戳是签名时写的,过期判断在验证时做')
tok2 = s.dumps('x'); time.sleep(2.2)
tryload('max_age=10(未过期)', tok2, max_age=10); tryload('max_age=1(已过期)', tok2, max_age=1)
try: s.loads(tok2, max_age=1)
except SignatureExpired as e: print('  SignatureExpired 的 date_signed =', e.date_signed.isoformat(), '| payload(base64 形式)仍然可取 =', e.payload); R['expired'] = [e.date_signed.isoformat(), e.payload.decode()]
print('  不传 max_age 时永不过期:', s.loads(tok2))
print()
print('== 五:在 Flask 里用它做一个「记住我」cookie:设置 + 校验;被篡改得到 401')
app = Flask('sc'); app.logger.disabled = True
ser = URLSafeTimedSerializer(SECRET, salt='remember')
@app.get('/login')
def login():
    r = make_response('ok'); r.set_cookie('remember', ser.dumps({'uid': 7}), max_age=3600, httponly=True, samesite='Lax'); return r
@app.get('/me')
def me():
    raw = request.cookies.get('remember')
    if not raw: return {'error': 'no cookie'}, 401
    try: return {'uid': ser.loads(raw, max_age=3600)['uid']}
    except SignatureExpired: return {'error': 'expired'}, 401
    except BadSignature: return {'error': 'bad signature'}, 401
c = app.test_client(); r = c.get('/login'); ck = r.headers['Set-Cookie'].split(';')[0]; print('  Set-Cookie 的第一段(名字=值):', ck[:60] + '…'); print('  GET /me →', c.get('/me').status_code, c.get('/me').get_json()); R['flask_ok'] = c.get('/me').get_json()
t = ck.split('=', 1)[1]; c2 = app.test_client(use_cookies=False); r = c2.get('/me', headers={'Cookie': 'remember=' + forged + '.' + t.split('.', 1)[1]}); print('  篡改 payload 后 GET /me →', r.status_code, r.get_json()); R['flask_bad'] = [r.status_code, r.get_json()]
print()
print('== 六:没有「撤销」:签名 cookie 在有效期内一直有效——登出后拿旧 cookie 照样通过(服务器端没有状态)')
old = ser.dumps({'uid': 7}); c3 = app.test_client(use_cookies=False)
print('  登出(客户端删 cookie)之后,旧 token 被别人拿着继续发 →', c3.get('/me', headers={'Cookie': 'remember=' + old}).status_code, '(服务器无从得知它已「登出」)'); R['replay'] = c3.get('/me', headers={'Cookie': 'remember=' + old}).status_code
print()
print('== 七:大小开销与压缩:itsdangerous 的 URLSafe 序列化器在压缩后更短时会 zlib 压缩(token 以 . 开头)')
import secrets
print(f'  {"payload":<26} {"JSON 字节":>10} {"token 字符":>11}  压缩标记')
R['size'] = {}
for label, payload in (('10 字符的随机十六进制', secrets.token_hex(5)), ('100 字符的随机十六进制', secrets.token_hex(50)), ('1000 字符的随机十六进制', secrets.token_hex(500)), ('100 个重复的 x', 'x' * 100), ('1000 个重复的 x', 'x' * 1000)):
    t = s.dumps(payload); jl = len(json.dumps(payload)); R['size'][label] = [jl, len(t), t.startswith('.')]; print(f'  {label:<26} {jl:>10} {len(t):>11}  {"以 . 开头(已压缩)" if t.startswith(".") else "未压缩"}')
save('f47', R)
