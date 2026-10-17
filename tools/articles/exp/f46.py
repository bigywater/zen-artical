import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f46'); R = {}
import datetime as dt, warnings
from flask import Flask, Response, request, make_response
app = Flask('ck'); app.logger.disabled = True
@app.get('/set')
def set_():
    r = make_response('ok'); r.set_cookie('plain', 'v1'); r.set_cookie('opts', 'v2', max_age=3600, path='/app', secure=True, httponly=True, samesite='Lax'); r.set_cookie('cn', '中文 空格;分号,逗号"引号'); r.set_cookie('exp', 'v', expires=dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)); return r
@app.get('/del')
def del_():
    r = make_response('ok'); r.delete_cookie('plain'); r.delete_cookie('opts', path='/app'); return r
@app.get('/read')
def read_(): return {'cookies': request.cookies.to_dict(), 'raw': request.headers.get('Cookie')}
@app.get('/big')
def big():
    r = make_response('ok'); r.set_cookie('big', 'x' * 5000); return r
@app.get('/part')
def part():
    r = make_response('ok'); r.set_cookie('p', 'v', partitioned=True, secure=True); return r
c = app.test_client()
print('== 一:set_cookie 的各个参数在 Set-Cookie 头里的样子')
r = c.get('/set'); R['set'] = r.headers.getlist('Set-Cookie')
for h in R['set']: print('  Set-Cookie:', h)
print()
print('== 二:delete_cookie 发出的是「值为空、立即过期」的 Set-Cookie;path/domain 必须与设置时一致才能删掉')
r = c.get('/del'); R['del'] = r.headers.getlist('Set-Cookie')
for h in R['del']: print('  Set-Cookie:', h)
print()
print('== 三:请求里的 Cookie 头怎么被解析:request.cookies')
cases = [('正常', 'a=1; b=2'), ('带引号的值', 'a="x y"'), ('重复的名字', 'a=1; a=2'), ('没有等号', 'a=1; b; c=3'), ('值里有等号', 'a=b=c'), ('空值', 'a=; b=2'), ('名字大小写', 'A=1; a=2'), ('百分号', 'a=%E4%B8%AD'), ('原始 UTF-8', 'a=中'.encode('utf-8').decode('latin-1')), ('分号后没空格', 'a=1;b=2'), ('带空格的名字', 'my cookie=1')]
R['read'] = {}
for label, hdr in cases:
    r = app.test_client(use_cookies=False).get('/read', headers={'Cookie': hdr}); R['read'][label] = r.get_json()['cookies']; print(f'  {label:<12} Cookie: {hdr!r:<28} → {r.get_json()["cookies"]}')
print()
print('== 四:测试客户端自带 cookie jar:往返、路径与 secure 的过滤')
c2 = app.test_client(); c2.get('/set'); r = c2.get('/read'); print('  GET /set 之后 GET /read 看到的 cookies:', r.get_json()['cookies'], '(opts 的 path=/app 与 secure,所以 /read 没带它)'); R['jar'] = r.get_json()['cookies']
print('  jar 里的键:', sorted(ck.key + '(path=' + ck.path + ')' for ck in c2._cookies.values()) if hasattr(c2, '_cookies') else '?'); R['jar_keys'] = sorted(ck.key + '(path=' + ck.path + ')' for ck in c2._cookies.values()) if hasattr(c2, '_cookies') else []
print()
print('== 五:值里的特殊字符怎么编码:Werkzeug 对不安全字符加引号并用八进制转义;中文如何')
c3 = app.test_client(); c3.get('/set'); jar = {ck.key: ck.value for ck in c3._cookies.values()}; print('  中文那条 cn 在客户端看到的原始值:', repr(jar.get('cn'))); R['cn_raw'] = jar.get('cn')
r = c3.get('/read'); print('  再发回来后 request.cookies["cn"] =', repr(r.get_json()['cookies'].get('cn'))); R['cn_back'] = r.get_json()['cookies'].get('cn')
print()
print('== 六:大小限制:Werkzeug 对超过 MAX_COOKIE_SIZE(默认 4093)的 cookie 发警告')
print('  MAX_COOKIE_SIZE =', app.config['MAX_COOKIE_SIZE']); R['max_size'] = app.config['MAX_COOKIE_SIZE']
with warnings.catch_warnings(record=True) as W:
    warnings.simplefilter('always'); r = c.get('/big')
print('  设置 5000 字节的 cookie:状态', r.status_code, '| 警告:', [str(w.message)[:150] for w in W]); R['warn'] = [str(w.message)[:200] for w in W]
print('  Set-Cookie 头长度:', len(r.headers['Set-Cookie']))
print()
print('== 七:samesite 参数的取值;partitioned(CHIPS)')
for v in ('Lax', 'Strict', 'None', 'bogus', None):
    try:
        rr = Response('x'); rr.set_cookie('s', '1', samesite=v, secure=(v == 'None')); print(f'  samesite={v!r:<8} → {rr.headers["Set-Cookie"]}'); R.setdefault('samesite', {})[str(v)] = rr.headers['Set-Cookie']
    except Exception as e: print(f'  samesite={v!r:<8} → {type(e).__name__}: {e}'); R.setdefault('samesite', {})[str(v)] = f'{type(e).__name__}: {e}'
print('  partitioned=True:', c.get('/part').headers['Set-Cookie']); R['part'] = c.get('/part').headers['Set-Cookie']
save('f46', R)
