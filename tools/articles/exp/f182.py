import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import threading, re as _re
tee('f182'); R = {}
COMMON = '''
import logging, os, re, uuid, threading, urllib.request
from flask import Flask, g, request, has_request_context, jsonify
ID_OK = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
class RidFilter(logging.Filter):
    def filter(self, rec): rec.rid = g.get("rid", "-") if has_request_context() else "-"; return True
h = logging.StreamHandler(); h.setFormatter(logging.Formatter("[%(svc)s] rid=%(rid)s %(message)s")); h.addFilter(RidFilter())
def make(svc, validate=True, propagate=True):
    app = Flask(svc); lg = logging.getLogger(svc); lg.setLevel(logging.INFO); lg.handlers = [h]; lg.propagate = False
    lg = logging.LoggerAdapter(lg, {"svc": svc})
    @app.before_request
    def rid():
        inc = request.headers.get("X-Request-ID")
        g.rid = inc if inc and (not validate or ID_OK.match(inc)) else uuid.uuid4().hex[:12]
    @app.after_request
    def hdr(resp): resp.headers["X-Request-ID"] = g.rid; return resp
    return app, lg
'''
A = COMMON + '''
import sys
app, lg = make("A", validate=os.environ.get("VALIDATE", "1") == "1")
B = os.environ["B_PORT"]
@app.get("/order")
def order():
    lg.info("A: 收到 /order")
    hd = {"X-Request-ID": g.rid} if os.environ.get("PROPAGATE", "1") == "1" else {}
    body = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{B}/stock", headers=hd), timeout=5).read().decode()
    lg.info("A: B 返回 %s", body); return jsonify(stock=body)
@app.get("/thread")
def thread():
    def work(): lg.info("A: 后台线程里的日志")
    t = threading.Thread(target=work); t.start(); t.join(); lg.info("A: 视图里的日志"); return "ok"
@app.get("/boom")
def boom(): 1 / 0
@app.errorhandler(500)
def e500(e): lg.error("A: 500"); return jsonify(error="internal", request_id=g.rid), 500
'''
B = COMMON + '''
app, lg = make("B")
@app.get("/stock")
def stock(): lg.info("B: 查库存"); return "42"
'''
d = mkapp('f182', {'a.py': A, 'b.py': B})
def rids(txt): return [(m.group(1), m.group(2)) for m in _re.finditer(r'\[(A|B)\] rid=(\S+)', txt)]
def run(propagate='1', validate='1', nginx=None):
    sb = Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'b:app']); sa = Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'a:app'], B_PORT=sb.port, PROPAGATE=propagate, VALIDATE=validate); return sa, sb
print('== 一:没有传入 X-Request-ID 与传入时:响应头里的 ID、日志里的 ID')
sa, sb = run(); R['basic'] = {}
r1 = sa.get('/order'); id1 = dict(r1[1]).get('X-Request-ID')
r2 = sa.get('/order', headers={'X-Request-ID': 'client-abc-123'}); id2 = dict(r2[1]).get('X-Request-ID')
time.sleep(0.3); la = sa.logtext(); lb = sb.logtext()
print(f'  不带头:响应头 X-Request-ID = {id1}(服务端生成,12 位)'); print(f'  带头 client-abc-123:响应头 X-Request-ID = {id2}')
print('  A 的日志:'); [print('    ' + l[:100]) for l in la.splitlines() if l.startswith('[A]')]
print('  B 的日志(A 调用 B 时把 ID 放进了请求头):'); [print('    ' + l[:100]) for l in lb.splitlines() if l.startswith('[B]')]
ra = [x[1] for x in rids(la)]; rb = [x[1] for x in rids(lb)]; R['basic'] = dict(id1=id1, id2=id2, a=ra, b=rb)
print(f'  同一次请求在 A、B 两边的 ID 相同:第 2 次 A={set(ra[2:])},B={rb[1]}')
sa.stop(); sb.stop()
print()
print('== 二:A 调用 B 时忘了带上 ID:两边的日志对不上')
sa, sb = run(propagate='0'); r = sa.get('/order'); idA = dict(r[1]).get('X-Request-ID'); time.sleep(0.3)
rbs = [x[1] for x in rids(sb.logtext())]; print(f'  A 的响应头 ID = {idA};B 日志里的 ID = {rbs}(B 自己生成了新的,链路断了)'); R['noprop'] = [idA, rbs]
sa.stop(); sb.stop()
print()
print('== 三:客户端传来不合规的 ID(很长 / 含空格与引号):不校验 vs 校验(只允许 [A-Za-z0-9._-]、最长 64)')
R['bad'] = {}
for label, val in (('不校验', '0'), ('校验', '1')):
    sa, sb = run(validate=val)
    r = sa.get('/order', headers={'X-Request-ID': 'x' * 300 + ' "quoted" a b'}); echoed = dict(r[1]).get('X-Request-ID'); sa.stop(); sb.stop()
    print(f'  {label}:响应头里的 ID 长度 {len(echoed)}' + ('(原样回显)' if len(echoed) > 100 else f',值 {echoed}(重新生成)')); R['bad'][label] = len(echoed)
print()
print('== 四:/boom 的 500 响应带上 request_id;后台线程里的日志拿不到请求的 ID')
sa, sb = run(); r = sa.get('/boom'); body = r[2].decode().strip(); sa.get('/thread'); time.sleep(0.3)
print(f'  /boom → {r[0]} {body}(响应头 X-Request-ID = {dict(r[1]).get("X-Request-ID")})')
tl_ = [l for l in sa.logtext().splitlines() if '线程' in l or '视图里' in l]; [print('    ' + l) for l in tl_]
R['boom'] = [r[0], body, tl_]; sa.stop(); sb.stop()
print()
print('== 五:nginx 生成 $request_id 并转发:nginx 访问日志、Flask 日志用同一个 ID')
W = FT / 'f182nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
sa, sb = run(); lp = free_port()
(W / 'nginx.conf').write_text(textwrap.dedent(f'''
    worker_processes 1; daemon off; pid {W}/nginx.pid; error_log {W}/logs/error.log;
    events {{ worker_connections 64; }}
    http {{
      log_format rid '$request_id "$request" $status';
      access_log {W}/logs/access.log rid; client_body_temp_path {W}/tmp/b; proxy_temp_path {W}/tmp/p; fastcgi_temp_path {W}/tmp/f; uwsgi_temp_path {W}/tmp/u; scgi_temp_path {W}/tmp/s;
      server {{ listen 127.0.0.1:{lp}; location / {{ proxy_pass http://127.0.0.1:{sa.port}; proxy_set_header X-Request-ID $request_id; add_header X-Request-ID $request_id always; }} }}
    }}'''))
ng = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
r = http(lp, 'GET', '/order'); time.sleep(0.3)
nid = [l.split()[0] for l in (W / 'logs' / 'access.log').read_text().splitlines()]
fa = [x[1] for x in rids(sa.logtext())]; fb = [x[1] for x in rids(sb.logtext())]
print(f'  nginx 访问日志里的 ID:{nid};Flask A 日志:{fa};B 日志:{fb}'); print(f'  nginx 响应头 X-Request-ID:{[v for k, v in r[1] if k == "X-Request-ID"]}(与 Flask 加的头同名,客户端看到的数量见上)')
R['nginx'] = dict(nid=nid, fa=fa, fb=fb, hdrs=[v for k, v in r[1] if k == 'X-Request-ID'])
os.killpg(ng.pid, signal.SIGTERM); ng.wait(5); sa.stop(); sb.stop()
save('f182', R)
