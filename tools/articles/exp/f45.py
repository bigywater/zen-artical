import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f45'); R = {}
import datetime as dt, json
from flask import Flask, Response, request, session, make_response
from werkzeug.http import http_date, parse_date
app = Flask('lm'); app.logger.disabled = True; app.secret_key = 'k'
T0 = dt.datetime(2026, 10, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
@app.get('/lm')
def lm():
    r = Response('content'); r.last_modified = T0; return r.make_conditional(request)
@app.get('/cc')
def cc():
    r = Response('x'); r.cache_control.max_age = 600; r.cache_control.public = True; r.cache_control.must_revalidate = True; return r
@app.get('/nostore')
def nostore():
    r = Response('secret'); r.cache_control.no_store = True; r.cache_control.private = True; return r
@app.get('/exp')
def exp():
    r = Response('x'); r.expires = T0 + dt.timedelta(hours=1); return r
@app.get('/sess')
def sess(): session['u'] = 1; return 'ok'
@app.get('/sess-read')
def sess_read(): return str(session.get('u'))
@app.get('/nosess')
def nosess(): return 'ok'
@app.get('/vary')
def vary():
    r = Response('x'); r.vary.add('Accept-Encoding'); r.vary.add('Accept-Language'); return r
@app.get('/both')
def both():
    r = Response('content'); r.last_modified = T0; r.set_etag('v1'); return r.make_conditional(request)
c = app.test_client()
print('== 一:Last-Modified 与 If-Modified-Since:格式、比较精度(秒)')
r = c.get('/lm'); print('  首次:', r.status_code, '| Last-Modified =', r.headers['Last-Modified']); R['first'] = [r.status_code, r.headers['Last-Modified']]
R['ims'] = {}
for label, hdr in (('等于 Last-Modified', http_date(T0)), ('晚 1 秒', http_date(T0 + dt.timedelta(seconds=1))), ('早 1 秒', http_date(T0 - dt.timedelta(seconds=1))), ('格式非法', 'yesterday')):
    rr = c.get('/lm', headers={'If-Modified-Since': hdr}); R['ims'][label] = rr.status_code; print(f'  If-Modified-Since {label:<14} ({hdr}) → {rr.status_code}')
R['both'] = {}
for label, hd in (('INM 匹配 + IMS 过期', {'If-None-Match': '"v1"', 'If-Modified-Since': http_date(T0 - dt.timedelta(days=1))}), ('INM 不匹配 + IMS 匹配', {'If-None-Match': '"zzz"', 'If-Modified-Since': http_date(T0)}), ('只有 IMS 匹配', {'If-Modified-Since': http_date(T0)}), ('INM 与 IMS 都匹配', {'If-None-Match': '"v1"', 'If-Modified-Since': http_date(T0)})):
    rr = c.get('/both', headers=hd); R['both'][label] = rr.status_code; print(f'  /both 同时有 ETag 与 Last-Modified,请求 {label:<20} → {rr.status_code}')
print()
print('== 二:Cache-Control 指令:max_age、public、private、no_store、must_revalidate 在响应头里的形式')
for p in ('/cc', '/nostore'): r = c.get(p); print(f'  GET {p:<9} Cache-Control: {r.headers["Cache-Control"]}'); R.setdefault('cc', {})[p] = r.headers['Cache-Control']
r = c.get('/exp'); print('  Expires:', r.headers['Expires']); R['expires'] = r.headers['Expires']
print()
print('== 三:Vary:Flask 在访问 session 时会自动加 Vary: Cookie;自己加的 Vary 与它合并')
R['vary'] = {}
for p in ('/nosess', '/sess-read', '/sess', '/vary'): r = c.get(p); R['vary'][p] = r.headers.get('Vary'); print(f'  GET {p:<11} → Vary: {r.headers.get("Vary")} | Set-Cookie: {"有" if "Set-Cookie" in r.headers else "无"}')
print()
print('== 四:缓存方式对比:同一个资源用三种策略,客户端第二次请求要付出的代价')
print(f'  {"策略":<34} {"第二次请求":<30}')
r = c.get('/lm'); r2 = c.get('/lm', headers={'If-Modified-Since': r.headers['Last-Modified']}); print(f'  {"Last-Modified + If-Modified-Since":<34} 发请求 → {r2.status_code},正文 {len(r2.data)} 字节'); R['strat_lm'] = [r2.status_code, len(r2.data)]
print(f'  {"max-age=600(强缓存)":<34} 浏览器直接用本地副本;期间服务器收不到请求(这一条是 HTTP 规范的约定,test client 无法演示)')
print()
print('== 五:缓存与登录态:带 Set-Cookie 的响应被共享缓存(CDN)缓存会泄露;要加 private / no-store / Vary: Cookie')
r = c.get('/sess'); print('  /sess 的响应头:', {k: v for k, v in r.headers if k.lower() in ('set-cookie', 'vary', 'cache-control')}.keys(), '| Cache-Control =', r.headers.get('Cache-Control'), '(Flask 不会替你加)'); R['sess_cc'] = r.headers.get('Cache-Control')
print()
save('f45', R)
