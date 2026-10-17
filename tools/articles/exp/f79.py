import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f79'); R = {}
from flask import Flask, jsonify, request, abort
from flask_cors import CORS, cross_origin
def H(r, *names): return {k: v for k, v in r.headers if k.lower() in {n.lower() for n in names}}
CH = ('Access-Control-Allow-Origin', 'Access-Control-Allow-Credentials', 'Access-Control-Allow-Methods', 'Access-Control-Allow-Headers', 'Access-Control-Max-Age', 'Access-Control-Expose-Headers', 'Vary')
def api(**cors_kw):
    a = Flask('c'); a.logger.disabled = True
    @a.route('/data', methods=['GET', 'POST', 'PUT'])
    def data(): return jsonify(ok=True)
    @a.get('/boom')
    def boom(): raise RuntimeError('boom')
    @a.get('/missing-abort')
    def ab(): abort(403)
    if cors_kw is not None: CORS(a, **cors_kw)
    return a
A_ORIGIN = 'http://app.example'
print('== 一:CORS(app) 默认配置:简单请求(带 Origin 头)与不带 Origin 头')
c = api().test_client()
r = c.get('/data', headers={'Origin': A_ORIGIN}); print('  带 Origin:', r.status_code, H(r, *CH)); R['simple'] = H(r, *CH)
r = c.get('/data'); print('  不带 Origin:', r.status_code, H(r, *CH)); R['noorigin'] = H(r, *CH)
print()
print('== 二:预检请求(OPTIONS + Access-Control-Request-*)的响应')
r = c.options('/data', headers={'Origin': A_ORIGIN, 'Access-Control-Request-Method': 'PUT', 'Access-Control-Request-Headers': 'content-type, x-token'})
print('  ', r.status_code, H(r, *CH), '正文长度', len(r.data)); R['pre'] = [r.status_code, H(r, *CH)]
c2 = api(max_age=600, methods=['GET', 'POST']).test_client()
r = c2.options('/data', headers={'Origin': A_ORIGIN, 'Access-Control-Request-Method': 'PUT'}); print('  methods=[GET,POST],请求 PUT 的预检:', r.status_code, H(r, 'Access-Control-Allow-Methods', 'Access-Control-Max-Age')); R['pre2'] = [r.status_code, H(r, 'Access-Control-Allow-Methods', 'Access-Control-Max-Age')]
print()
print('== 三:origins 白名单:允许的 Origin 被回显并带 Vary: Origin;不在名单里的 Origin 没有 CORS 头,但请求照样被处理')
c = api(origins=[A_ORIGIN]).test_client()
for o in (A_ORIGIN, 'http://evil.example'):
    r = c.get('/data', headers={'Origin': o}); print(f'  Origin={o:<22} → {r.status_code} {H(r, *CH)} 正文={r.get_json()}'); R.setdefault('wl', {})[o] = [r.status_code, H(r, *CH)]
r = c.options('/data', headers={'Origin': 'http://evil.example', 'Access-Control-Request-Method': 'GET'}); print('  evil 的预检:', r.status_code, H(r, *CH)); R['wl_pre'] = [r.status_code, H(r, *CH)]
print()
print('== 四:supports_credentials=True 时的 Allow-Origin(浏览器规定带凭证时不能是 *)')
for label, kw in (('origins="*" + credentials', dict(supports_credentials=True)), ('origins=[A] + credentials', dict(origins=[A_ORIGIN], supports_credentials=True))):
    r = api(**kw).test_client().get('/data', headers={'Origin': A_ORIGIN}); print(f'  {label:<28} → {H(r, "Access-Control-Allow-Origin", "Access-Control-Allow-Credentials", "Vary")}'); R.setdefault('cred', {})[label] = H(r, 'Access-Control-Allow-Origin', 'Access-Control-Allow-Credentials', 'Vary')
print()
print('== 五:只给部分路径开 CORS(resources)、expose_headers,以及 @cross_origin 装饰器')
a = Flask('r'); a.logger.disabled = True
CORS(a, resources={r'/api/*': {'origins': [A_ORIGIN], 'expose_headers': ['X-Total']}})
@a.get('/api/x')
def x(): return jsonify(1)
@a.get('/private')
def pv(): return jsonify(1)
@a.get('/one')
@cross_origin(origins=['http://one.example'])
def one(): return jsonify(1)
c = a.test_client()
for p, o in (('/api/x', A_ORIGIN), ('/private', A_ORIGIN), ('/one', 'http://one.example'), ('/one', A_ORIGIN)):
    r = c.get(p, headers={'Origin': o}); print(f'  {p:<9} Origin={o:<22} → {H(r, "Access-Control-Allow-Origin", "Access-Control-Expose-Headers")}'); R.setdefault('res', {})[f'{p} {o}'] = H(r, 'Access-Control-Allow-Origin', 'Access-Control-Expose-Headers')
print()
print('== 六:出错的响应有没有 CORS 头?(浏览器里看不到错误详情,只会报「CORS 错误」)')
c = api(origins=[A_ORIGIN]).test_client()
for p in ('/boom', '/nonexistent', '/missing-abort'):
    r = c.get(p, headers={'Origin': A_ORIGIN}); print(f'  {p:<16} → {r.status_code} {H(r, "Access-Control-Allow-Origin")}'); R.setdefault('err', {})[p] = [r.status_code, H(r, 'Access-Control-Allow-Origin')]
a5 = api(origins=[A_ORIGIN]); a5.config['PROPAGATE_EXCEPTIONS'] = False; a5.config['TESTING'] = False
r = a5.test_client().get('/boom', headers={'Origin': A_ORIGIN}); print('  TESTING=False 下 /boom:', r.status_code, H(r, 'Access-Control-Allow-Origin')); R['err_boom_prod'] = [r.status_code, H(r, 'Access-Control-Allow-Origin')]
print()
print('== 七:真正的浏览器(无头 Chrome):页面在 http://127.0.0.1:P1,接口在 http://127.0.0.1:P2(端口不同就是不同源)')
SRV = '''
import os, time
from flask import Flask, jsonify, request
from flask_cors import CORS
app = Flask(__name__)
mode = os.environ["MODE"]; page_origin = os.environ["PAGE_ORIGIN"]
LOG = os.environ["LOGF"]
@app.before_request
def lg():
    with open(LOG, "a") as f: f.write(f"{request.method} {request.path} origin={request.headers.get('Origin')} cookie={request.cookies.get('sid')} ctype={request.content_type}\\n")
@app.route("/data", methods=["GET", "POST"])
def data(): return jsonify(ok=True, method=request.method)
@app.get("/me")
def me(): return jsonify(sid=request.cookies.get("sid"))
if mode == "wild": CORS(app)
elif mode == "origin": CORS(app, origins=[page_origin])
elif mode == "cred": CORS(app, origins=[page_origin], supports_credentials=True)
'''
PAGE = '''<!doctype html><meta charset=utf-8><pre id=out>running</pre><script>
document.cookie = "sid=abc123; path=/";
const API = "http://127.0.0.1:__API__";
const tests = {
  "GET /data": () => fetch(API + "/data"),
  "POST /data (JSON)": () => fetch(API + "/data", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"}),
  "GET /data + X-Token 头": () => fetch(API + "/data", {headers: {"X-Token": "t"}}),
  "GET /me (credentials: include)": () => fetch(API + "/me", {credentials: "include"}),
};
(async () => {
  const res = {};
  for (const [k, f] of Object.entries(tests)) {
    try { const r = await f(); res[k] = "OK " + r.status + " " + (await r.text()).trim(); } catch (e) { res[k] = "FAIL " + e.name + ": " + e.message; }
  }
  document.getElementById("out").textContent = "RESULT:" + JSON.stringify(res);
})();
</script>'''
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
pdir = mkapp('f79page', {'app.py': 'from flask import Flask, send_file\napp = Flask(__name__)\n@app.get("/")\ndef i(): return send_file("page.html")\n', 'page.html': 'x'})
R['browser'] = {}
for mode, label in (('none', '接口没开 CORS'), ('wild', 'CORS(app) 默认配置'), ('origin', 'CORS(app, origins=[页面源])'), ('cred', 'origins=[页面源] + supports_credentials')):
    d = mkapp('f79api', {'app.py': SRV}); lf = d / 'seen.log'; lf.write_text('')
    api_port = free_port(); page_port = free_port()
    with Server(d, ['gunicorn', '-b', '127.0.0.1:' + str(api_port), '-w', '1', 'app:app'], port=api_port, MODE=mode, PAGE_ORIGIN=f'http://127.0.0.1:{page_port}', LOGF=lf):
        (pdir / 'page.html').write_text(PAGE.replace('__API__', str(api_port)))
        with Server(pdir, ['gunicorn', '-b', '127.0.0.1:' + str(page_port), '-w', '1', 'app:app'], port=page_port):
            prof = FT / 'f79chrome'; shutil.rmtree(prof, ignore_errors=True)
            pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', '--virtual-time-budget=15000', '--dump-dom', f'http://127.0.0.1:{page_port}/'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
            buf = ''; t0 = time.time()
            while time.time() - t0 < 60:
                l = pc.stdout.readline()
                if not l: break
                buf += l
                if '</html>' in l: break
            try: os.killpg(pc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            pc.wait(); r = type('R', (), {'stdout': buf, 'stderr': ''})
            m = re.search(r'RESULT:(\{.*?\})</pre>', r.stdout, re.S)
            res = json.loads(__import__('html').unescape(m.group(1))) if m else {'?': 'no result: ' + r.stdout[-200:] + r.stderr[-200:]}
            seen = [l.strip() for l in lf.read_text().splitlines()]
    print(f'  [{label}]')
    for k, v in res.items(): print(f'    {k:<32} {v}')
    print('    服务端实际收到的请求:', [re.sub(r' ctype=None', '', l)[:110] for l in seen])
    R['browser'][mode] = dict(res=res, seen=seen)
save('f79', R)
