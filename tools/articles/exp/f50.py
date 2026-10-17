import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f50'); R = {}
from flask import Flask, request, jsonify, make_response, render_template_string, abort
app = Flask('cn'); app.logger.disabled = True
OFFERS = ['application/json', 'text/html', 'text/csv']
@app.get('/res')
def res():
    best = request.accept_mimetypes.best_match(OFFERS)
    if best is None: return Response406()
    if best == 'application/json': r = jsonify(a=1)
    elif best == 'text/csv': r = make_response('a\n1\n'); r.mimetype = 'text/csv'
    else: r = make_response('<p>a=1</p>')
    r.vary.add('Accept'); return r
def Response406():
    r = make_response({'error': 'not acceptable', 'offered': OFFERS}, 406); r.vary.add('Accept'); return r
@app.get('/lang')
def lang():
    best = request.accept_languages.best_match(['zh-CN', 'zh-TW', 'en', 'en-GB', 'ja'], default='en'); return {'best': best, 'header': request.headers.get('Accept-Language')}
@app.get('/enc')
def enc(): return {'gzip': request.accept_encodings['gzip'], 'br': request.accept_encodings['br'], 'identity': request.accept_encodings['identity'], 'best': request.accept_encodings.best, 'raw': request.headers.get('Accept-Encoding')}
@app.get('/parsed')
def parsed(): return {'values': [(m, q) for m, q in request.accept_mimetypes], 'best': request.accept_mimetypes.best, 'accept_json': request.accept_mimetypes.accept_json, 'accept_html': request.accept_mimetypes.accept_html, 'quality_json': request.accept_mimetypes.quality('application/json'), 'json_in': 'application/json' in request.accept_mimetypes}
@app.get('/ext.<fmt>')
def ext(fmt):
    if fmt == 'json': return {'a': 1}
    if fmt == 'html': return '<p>a=1</p>'
    abort(404)
c = app.test_client()
print('== 一:Accept 头的解析:q 值、通配符、同 q 值时的顺序')
print(f'  {"Accept":<54} → 服务端提供 {OFFERS} 时选择')
R['accept'] = {}
cases = [('*/*', 'curl 默认'), ('application/json', ''), ('text/html', ''), ('text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Chrome 的导航请求'), ('application/json, text/html', '同 q 值'), ('text/html, application/json', '同 q 值,顺序相反'), ('application/json;q=0.5, text/html;q=0.9', ''), ('text/*', ''), ('image/png', '服务端没有的'), ('application/json;q=0', 'q=0 表示不接受'), ('text/html;q=0, */*;q=0.1', ''), ('', '没有 Accept 头'), ('garbage', '')]
for hdr, note in cases:
    h = {'Accept': hdr} if hdr != '' else {}
    r = c.get('/res', headers=h); R['accept'][hdr or '(无)'] = [r.status_code, r.content_type]; print(f'  {(hdr or "(无)"):<54} → {r.status_code} {r.content_type}   {note}')
print()
print('== 二:request.accept_mimetypes 的各个接口(同一个请求上)')
r = c.get('/parsed', headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}); R['parsed'] = r.get_json(); print('  ', r.get_json())
print()
print('== 三:406 Not Acceptable 与 Vary: Accept(缓存要按 Accept 区分)')
r = c.get('/res', headers={'Accept': 'image/png'}); print('  Accept: image/png →', r.status_code, r.get_json(), '| Vary =', r.headers.get('Vary')); R['406'] = [r.status_code, r.get_json(), r.headers.get('Vary')]
r = c.get('/res', headers={'Accept': 'application/json'}); print('  Accept: application/json → Vary =', r.headers.get('Vary')); R['vary'] = r.headers.get('Vary')
print()
print('== 四:Accept-Language:语言匹配(Accept-Language: zh 能匹配到 zh-CN 吗)')
R['lang'] = {}
for hdr in ('zh-CN,zh;q=0.9,en;q=0.8', 'zh', 'zh-TW', 'en-US,en;q=0.9', 'fr', 'ja;q=0.5, en;q=0.9', '*', ''):
    r = c.get('/lang', headers={'Accept-Language': hdr} if hdr else {}); R['lang'][hdr or '(无)'] = r.get_json()['best']; print(f'  Accept-Language: {(hdr or "(无)"):<26} → best_match(zh-CN, zh-TW, en, en-GB, ja; default=en) = {r.get_json()["best"]}')
print()
print('== 五:Accept-Encoding:Flask 不会自动压缩响应,只告诉你客户端接受什么')
for hdr in ('gzip, deflate, br', 'gzip;q=0, identity', 'br;q=1.0, gzip;q=0.8, *;q=0.1', ''):
    r = c.get('/enc', headers={'Accept-Encoding': hdr} if hdr else {}); R.setdefault('enc', {})[hdr or '(无)'] = r.get_json(); print(f'  {(hdr or "(无)"):<34} → gzip q={r.get_json()["gzip"]} br q={r.get_json()["br"]} identity q={r.get_json()["identity"]}')
print()
print('== 六:用 URL 后缀选择格式(/ext.json)比 Accept 更适合浏览器直接访问与缓存;两种可以共存')
R['ext'] = {p: [c.get(p).status_code, c.get(p).content_type] for p in ('/ext.json', '/ext.html', '/ext.xml')}
for p, v in R['ext'].items(): print(f'  GET {p:<10} → {v[0]} {v[1]}')
print()
print('== 七:Accept 头的真实来源:curl 与 python-requests 默认发什么')
d = __import__('fl').app('f50', {'app.py': 'from flask import Flask, request\napp = Flask(__name__)\n@app.get("/h")\ndef h(): return {"accept": request.headers.get("Accept"), "ua": request.headers.get("User-Agent"), "ae": request.headers.get("Accept-Encoding")}\n'})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    r = subprocess.run(['curl', '-s', f'http://127.0.0.1:{s.port}/h'], capture_output=True, text=True); print('  curl 默认:', r.stdout.strip()); R['curl'] = r.stdout.strip()
    import requests; r = requests.get(f'http://127.0.0.1:{s.port}/h'); print('  requests 默认:', r.text.strip()); R['requests'] = r.text.strip()
save('f50', R)
