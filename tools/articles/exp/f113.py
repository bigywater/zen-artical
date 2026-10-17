import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f113'); R = {}
import hashlib, json, datetime as dt
from flask import Flask, request, jsonify, make_response
from werkzeug.http import http_date
app = Flask('et'); app.logger.disabled = True
DATA = [{'id': i, 'name': f'user{i}', 'score': i * 1.5} for i in range(1000)]
VER = {'v': 1}
def slow_query(): time.sleep(0.05); return DATA
@app.get('/hash')
def by_hash():
    body = json.dumps(slow_query(), sort_keys=True); r = make_response(body); r.headers['Content-Type'] = 'application/json'; r.add_etag(); return r.make_conditional(request)
@app.get('/version')
def by_version():
    etag = f'"v{VER["v"]}"'
    if etag in [x.strip() for x in request.headers.get('If-None-Match', '').split(',')]: r = make_response('', 304); r.headers['ETag'] = etag; return r
    r = make_response(json.dumps(slow_query())); r.headers['Content-Type'] = 'application/json'; r.headers['ETag'] = etag; return r
@app.get('/lm')
def by_lm():
    r = make_response(json.dumps(DATA)); r.headers['Content-Type'] = 'application/json'; r.last_modified = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc); return r.make_conditional(request)
@app.get('/weak')
def weak():
    r = make_response(json.dumps(DATA)); r.set_etag('abc', weak=True); return r.make_conditional(request)
c = app.test_client()
print('== 一:add_etag() + make_conditional():第一次 200 带 ETag,带 If-None-Match 再请求得到 304 和空正文')
r1 = c.get('/hash'); et = r1.headers['ETag']; print('  第一次 →', r1.status_code, '| ETag =', et, '| 正文', len(r1.data), '字节'); R['first'] = [r1.status_code, et, len(r1.data)]
r2 = c.get('/hash', headers={'If-None-Match': et}); print('  带 If-None-Match →', r2.status_code, '| 正文', len(r2.data), '字节 | ETag 头仍在:', r2.headers.get('ETag') == et); R['second'] = [r2.status_code, len(r2.data)]
r3 = c.get('/hash', headers={'If-None-Match': '"other"'}); print('  If-None-Match 是别的值 →', r3.status_code, '| 正文', len(r3.data), '字节'); R['mismatch'] = r3.status_code
r4 = c.get('/hash', headers={'If-None-Match': f'"x", {et}, "y"'}); print('  If-None-Match 是列表 "x", ETag, "y" →', r4.status_code); R['list'] = r4.status_code
r5 = c.post('/hash', headers={'If-None-Match': et}); print('  POST 带 If-None-Match →', r5.status_code, '(路由只允许 GET)')
print('  ETag 是正文的哈希吗:', et.strip('"') == hashlib.sha1(r1.data).hexdigest(), '(Werkzeug 的 add_etag 用正文的 SHA-1 十六进制)'); R['sha1'] = et.strip('"') == hashlib.sha1(r1.data).hexdigest()
print()
print('== 二:哈希 ETag 要先把正文算出来才能比较(慢查询 50 ms 照付);版本号 ETag 可以先比较、命中就不查')
res = {}
for label, path, h in (('哈希 ETag:200(没带头)', '/hash', {}), ('哈希 ETag:304', '/hash', {'If-None-Match': et}), ('版本号 ETag:200', '/version', {}), ('版本号 ETag:304', '/version', {'If-None-Match': '"v1"'})):
    c.get(path, headers=h); L = []
    for _ in range(5): t0 = time.perf_counter(); r = c.get(path, headers=h); L.append(ms(t0))
    res[label] = [median(L), r.status_code, len(r.data)]; print(f'  {label:<24} {median(L):>7.2f} ms  状态 {r.status_code}  正文 {len(r.data)} 字节')
R['cost'] = res
VER['v'] = 2; r = c.get('/version', headers={'If-None-Match': '"v1"'}); print('  数据变了(版本号 → v2)后,带旧 ETag 的请求 →', r.status_code, '新 ETag', r.headers['ETag']); R['ver_change'] = [r.status_code, r.headers['ETag']]
print()
print('== 三:Last-Modified / If-Modified-Since')
r1 = c.get('/lm'); print('  第一次 →', r1.status_code, '| Last-Modified =', r1.headers.get('Last-Modified')); lm = r1.headers['Last-Modified']
r2 = c.get('/lm', headers={'If-Modified-Since': lm}); print('  带 If-Modified-Since(同一时间)→', r2.status_code); r3 = c.get('/lm', headers={'If-Modified-Since': http_date(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc))}); print('  If-Modified-Since 是更早的时间 →', r3.status_code); R['lm'] = [r1.status_code, r2.status_code, r3.status_code]
print()
print('== 四:弱 ETag W/"abc"')
r1 = c.get('/weak'); print('  ETag =', r1.headers['ETag']); r2 = c.get('/weak', headers={'If-None-Match': 'W/"abc"'}); r3 = c.get('/weak', headers={'If-None-Match': '"abc"'}); print('  If-None-Match: W/"abc" →', r2.status_code, '| If-None-Match: "abc"(强)→', r3.status_code, '(If-None-Match 用弱比较,两者都匹配)'); R['weak'] = [r1.headers['ETag'], r2.status_code, r3.status_code]
print()
print('== 五:带宽:1000 条记录的列表,304 与 200 的响应体积')
r200 = c.get('/hash'); r304 = c.get('/hash', headers={'If-None-Match': et}); print(f'  200 响应体 {len(r200.data)} 字节;304 响应体 {len(r304.data)} 字节;头部总字节(估算)200: {sum(len(k) + len(v) + 4 for k, v in r200.headers)},304: {sum(len(k) + len(v) + 4 for k, v in r304.headers)}'); R['bytes'] = [len(r200.data), len(r304.data)]
save('f113', R)
