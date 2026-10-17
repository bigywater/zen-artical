import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f44'); R = {}
import hashlib, json
from flask import Flask, Response, request, jsonify, make_response
from werkzeug.http import generate_etag, quote_etag, parse_etags
app = Flask('et'); app.logger.disabled = True
DATA = {'v': 1}
@app.get('/auto')
def auto():
    r = make_response(json.dumps({'items': list(range(100))})); r.mimetype = 'application/json'; r.add_etag(); r.make_conditional(request); return r
@app.get('/manual')
def manual():
    body = json.dumps(DATA); etag = hashlib.md5(body.encode()).hexdigest()
    if request.if_none_match.contains(etag) or request.if_none_match.contains_weak(etag): return Response(status=304, headers={'ETag': f'"{etag}"'})
    r = Response(body, mimetype='application/json'); r.set_etag(etag); return r
@app.get('/weak')
def weak():
    r = Response('x' * 100); r.set_etag('abc', weak=True); r.make_conditional(request); return r
@app.route('/doc', methods=['GET', 'PUT'])
def doc():
    r = Response(json.dumps(DATA), mimetype='application/json'); r.set_etag(hashlib.md5(json.dumps(DATA).encode()).hexdigest())
    if request.method == 'PUT':
        if request.if_match and not request.if_match.contains(r.get_etag()[0]): return Response('precondition failed', 412)
        DATA['v'] += 1; return Response('updated', 200)
    return r.make_conditional(request)
c = app.test_client()
print('== 一:add_etag + make_conditional:ETag 是响应体的 SHA-1 哈希;带 If-None-Match 得到 304')
r = c.get('/auto'); etag = r.headers['ETag']; print('  首次:', r.status_code, '| ETag =', etag, '| 正文', len(r.data), '字节 | Content-Length', r.headers.get('Content-Length')); R['first'] = [r.status_code, etag, len(r.data)]
exp = '"' + hashlib.sha1(r.data).hexdigest() + '"'; print('  与 sha1(正文) 比较:', exp == etag); R['sha1'] = exp == etag
r2 = c.get('/auto', headers={'If-None-Match': etag}); print('  If-None-Match =', etag[:12] + '…', '→', r2.status_code, '| 正文', len(r2.data), '字节 | ETag =', r2.headers.get('ETag', '')[:12] + '…', '| Content-Length =', r2.headers.get('Content-Length')); R['304'] = [r2.status_code, len(r2.data), r2.headers.get('Content-Length')]
r3 = c.get('/auto', headers={'If-None-Match': '"other"'}); print('  If-None-Match: "other" →', r3.status_code, '| 正文', len(r3.data), '字节'); R['mismatch'] = [r3.status_code, len(r3.data)]
r4 = c.get('/auto', headers={'If-None-Match': '*'}); print('  If-None-Match: * →', r4.status_code); R['star'] = r4.status_code
r5 = c.get('/auto', headers={'If-None-Match': f'"a", {etag}, "b"'}); print('  If-None-Match 带多个值(含正确的)→', r5.status_code); R['multi'] = r5.status_code
r6 = c.post('/auto', headers={'If-None-Match': etag}); print('  POST 带 If-None-Match →', r6.status_code, '(路由不允许 POST)')
print()
print('== 二:弱 ETag W/"…" 与强 ETag:If-None-Match 比较使用弱比较;If-Match 需要强比较')
r = c.get('/weak'); print('  响应的 ETag:', r.headers['ETag']); R['weak'] = r.headers['ETag']
for label, hdr in (('强 "abc"', '"abc"'), ('弱 W/"abc"', 'W/"abc"'), ('不同 "xyz"', '"xyz"')): rr = c.get('/weak', headers={'If-None-Match': hdr}); print(f'  If-None-Match: {label:<12} → {rr.status_code}'); R.setdefault('weakcmp', {})[label] = rr.status_code
print('  werkzeug 的辅助:generate_etag(b"x") =', generate_etag(b'x'), '| quote_etag("a", weak=True) =', quote_etag('a', weak=True), '| parse_etags(\'W/"a", "b"\').to_header() =', parse_etags('W/"a", "b"').to_header()); R['helpers'] = [generate_etag(b'x'), quote_etag('a', weak=True), parse_etags('W/"a", "b"').to_header()]
print()
print('== 三:手写 ETag(用数据版本号或哈希,不必先生成整个响应体):用 request.if_none_match 判断')
r = c.get('/manual'); e1 = r.headers['ETag']; print('  GET /manual →', r.status_code, e1); r2 = c.get('/manual', headers={'If-None-Match': e1}); print('  带 ETag 再请求 →', r2.status_code, '(没有重新生成响应体)'); R['manual'] = [r.status_code, r2.status_code]
print()
print('== 四:ETag 防止「丢失更新」:PUT 带 If-Match;别人先改了就得到 412 Precondition Failed')
g = c.get('/doc'); et = g.headers['ETag']
r1 = c.put('/doc', headers={'If-Match': et}); print('  第一个客户端 PUT If-Match = 它读到的 ETag →', r1.status_code, r1.get_data(as_text=True)); R['put1'] = [r1.status_code, r1.get_data(as_text=True)]
r2 = c.put('/doc', headers={'If-Match': et}); print('  第二个客户端用同一个(已过期的)ETag PUT →', r2.status_code, r2.get_data(as_text=True)); R['put2'] = [r2.status_code, r2.get_data(as_text=True)]
print('  数据版本现在是:', DATA)
print()
print('== 五:节省多少:304 响应只有头,没有正文——对比 200 与 304 的字节数(1 万个元素的 JSON)')
big = Flask('big'); big.get('/b')(lambda: (lambda r: (r.add_etag(), r.make_conditional(request), r)[2])(make_response(json.dumps(list(range(10000))))))
cb = big.test_client(); r = cb.get('/b'); r2 = cb.get('/b', headers={'If-None-Match': r.headers['ETag']})
hdr_bytes = lambda rr: len(''.join(f'{k}: {v}\r\n' for k, v in rr.headers))
print(f'  200:正文 {len(r.data)} 字节 + 头约 {hdr_bytes(r)} 字节;304:正文 {len(r2.data)} 字节 + 头约 {hdr_bytes(r2)} 字节;但服务器仍然生成并哈希了整个响应体(耗时见下)'); R['saved'] = [len(r.data), hdr_bytes(r), len(r2.data), hdr_bytes(r2)]
import timeit
t200 = min(timeit.timeit(lambda: cb.get('/b'), number=300) / 300 * 1e6 for _ in range(3)); t304 = min(timeit.timeit(lambda: cb.get('/b', headers={'If-None-Match': r.headers['ETag']}), number=300) / 300 * 1e6 for _ in range(3))
print(f'  test client 耗时:200 {t200:.0f} µs;304 {t304:.0f} µs(服务器端的计算没有省:还是要生成响应体算 SHA-1)'); R['cost'] = [t200, t304]
save('f44', R)
