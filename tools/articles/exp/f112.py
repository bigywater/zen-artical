import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f112'); R = {}
import html as htmlmod
SRV = '''
import os
from flask import Flask, request, jsonify, make_response
app = Flask(__name__); mode = os.environ["MODE"]; page_origin = os.environ["PAGE_ORIGIN"]; LOG = os.environ["LOGF"]
@app.before_request
def lg():
    with open(LOG, "a") as f: f.write(f"{request.method} {request.path} ctype={request.content_type} acrh={request.headers.get('Access-Control-Request-Headers')} acrm={request.headers.get('Access-Control-Request-Method')}\\n")
    if request.method == "OPTIONS":
        if mode == "auth401": return make_response("unauthorized", 401)
        r = make_response("", 204); r.headers["Access-Control-Allow-Origin"] = page_origin
        r.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
        if mode != "noheaders": r.headers["Access-Control-Allow-Headers"] = "content-type, x-token"
        if mode == "maxage60": r.headers["Access-Control-Max-Age"] = "60"
        elif mode == "maxage0": r.headers["Access-Control-Max-Age"] = "0"
        return r
@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = page_origin; return r
@app.route("/data", methods=["GET", "POST", "PUT", "DELETE"])
def data(): return jsonify(ok=True, method=request.method)
'''
PAGE = '''<!doctype html><meta charset=utf-8><pre id=out>running</pre><script>
const API = "http://127.0.0.1:__API__";
const tests = [
  ["GET(简单请求)", () => fetch(API + "/data")],
  ["POST text/plain(简单请求)", () => fetch(API + "/data", {method: "POST", headers: {"Content-Type": "text/plain"}, body: "x"})],
  ["POST application/json", () => fetch(API + "/data", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"})],
  ["POST application/json(再来一次)", () => fetch(API + "/data", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"})],
  ["GET + 自定义头 X-Token", () => fetch(API + "/data", {headers: {"X-Token": "t"}})],
  ["GET + Authorization 头", () => fetch(API + "/data", {headers: {"Authorization": "Bearer t"}})],
  ["PUT", () => fetch(API + "/data", {method: "PUT"})],
  ["DELETE", () => fetch(API + "/data", {method: "DELETE"})],
];
(async () => {
  const res = {};
  for (const [k, f] of tests) { try { const r = await f(); res[k] = "OK " + r.status; } catch (e) { res[k] = "FAIL " + e.message; } }
  document.getElementById("out").textContent = "RESULT:" + JSON.stringify(res);
})();
</script>'''
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
pdir = mkapp('f112page', {'app.py': 'from flask import Flask, send_file\napp = Flask(__name__)\n@app.get("/")\ndef i(): return send_file("page.html")\n', 'page.html': 'x'})
R['modes'] = {}
for mode, label in (('maxage60', '预检响应带 Access-Control-Max-Age: 60'), ('maxage0', 'Max-Age: 0(不缓存预检)'), ('noheaders', '预检响应没有 Access-Control-Allow-Headers'), ('auth401', 'OPTIONS 请求也要求认证(返回 401)')):
    d = mkapp('f112api', {'app.py': SRV}); lf = d / 'seen.log'; lf.write_text('')
    api_port = free_port(); page_port = free_port()
    with Server(d, ['gunicorn', '-b', '127.0.0.1:' + str(api_port), '-w', '1', 'app:app'], port=api_port, MODE=mode, PAGE_ORIGIN=f'http://127.0.0.1:{page_port}', LOGF=lf):
        (pdir / 'page.html').write_text(PAGE.replace('__API__', str(api_port)))
        with Server(pdir, ['gunicorn', '-b', '127.0.0.1:' + str(page_port), '-w', '1', 'app:app'], port=page_port):
            prof = FT / 'f112chrome'; shutil.rmtree(prof, ignore_errors=True)
            pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', '--virtual-time-budget=20000', '--dump-dom', f'http://127.0.0.1:{page_port}/'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
            buf = ''; t0 = time.time()
            while time.time() - t0 < 80:
                l = pc.stdout.readline()
                if not l: break
                buf += l
                if '</html>' in l: break
            try: os.killpg(pc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            pc.wait(); m = re.search(r'RESULT:(\{.*?\})</pre>', buf, re.S); res = json.loads(htmlmod.unescape(m.group(1))) if m else {'?': 'no result'}; seen = [l.strip() for l in lf.read_text().splitlines()]
    print(f'== [{label}]')
    for k, v in res.items(): print(f'    {k:<32} {v}')
    simple = [re.sub(r' ctype=\S+ acrh=\S+ acrm=\S+', '', s) for s in seen]; print('    服务端收到的请求顺序:', [re.sub(r' ctype=(\S+) acrh=(\S+) acrm=(\S+)', lambda mm: '' if mm.group(1) == 'None' and mm.group(2) == 'None' else f' [{mm.group(1)}]' if mm.group(2) == 'None' else f' [预检:方法={mm.group(3)} 头={mm.group(2)}]', s) for s in seen])
    print('    其中 OPTIONS 个数:', sum(s.startswith('OPTIONS') for s in seen)); R['modes'][mode] = dict(res=res, seen=seen, n_options=sum(s.startswith('OPTIONS') for s in seen))
save('f112', R)
