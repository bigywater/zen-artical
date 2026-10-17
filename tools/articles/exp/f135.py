import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f135'); R = {}
import http.client as hc, ssl, pathlib, textwrap
APP = '''
import os, time
from flask import Flask, request, jsonify, url_for, redirect, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix
app = Flask(__name__)
n = int(os.environ.get("X_FOR", "0"))
if n: app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n)
@app.get("/info")
def info(): return jsonify(remote_addr=request.remote_addr, access_route=list(request.access_route), raw_first_xff=(request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or None, raw_xff=request.headers.get("X-Forwarded-For"))
@app.get("/dir/")
def d(): return "dir"
@app.get("/go")
def go(): return redirect(url_for("info"))
@app.post("/size")
def size(): return str(len(request.get_data()))
@app.get("/stream")
def stream():
    def gen():
        for i in range(5): yield f"chunk{i}\\n"; time.sleep(0.3)
    return Response(stream_with_context(gen()), mimetype="text/plain")
'''
W = FT / 'f134nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(W / 'k.pem'), '-out', str(W / 'c.pem'), '-days', '2', '-subj', '/CN=localhost'], capture_output=True)
def conf(up, http_port, https_port, proxy_headers=True, buffering='on', redirect_http=True, max_body='1m', xff='$remote_addr'):
    ph = f'''proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-For {xff};
        proxy_set_header X-Forwarded-Proto $scheme;''' if proxy_headers else ''
    return textwrap.dedent(f'''
    worker_processes 1; daemon off; pid {W}/nginx.pid; error_log {W}/logs/error.log;
    events {{ worker_connections 64; }}
    http {{
      access_log {W}/logs/access.log; client_body_temp_path {W}/tmp/b; proxy_temp_path {W}/tmp/p; fastcgi_temp_path {W}/tmp/f; uwsgi_temp_path {W}/tmp/u; scgi_temp_path {W}/tmp/s;
      client_max_body_size {max_body};
      server {{ listen 127.0.0.1:{http_port}; {"return 301 https://$host:" + str(https_port) + "$request_uri;" if redirect_http else "location / { proxy_pass http://127.0.0.1:" + str(up) + "; }"} }}
      server {{
        listen 127.0.0.1:{https_port} ssl; ssl_certificate {W}/c.pem; ssl_certificate_key {W}/k.pem; server_name localhost;
        location / {{ proxy_pass http://127.0.0.1:{up}; {ph} proxy_buffering {buffering}; }}
      }}
    }}''')
class Nginx:
    def __init__(self, text): (W / 'nginx.conf').write_text(text); self.p = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
    def stop(self):
        try: os.killpg(self.p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError): pass
        try: self.p.wait(5)
        except Exception: pass
    def __enter__(self): return self
    def __exit__(self, *a): self.stop()
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
def https(port, method, path, body=None, headers=None, timeout=10):
    c = hc.HTTPSConnection('127.0.0.1', port, context=CTX, timeout=timeout); t0 = time.perf_counter(); c.request(method, path, body=body, headers={'Host': f'localhost:{port}', **(headers or {})}); r = c.getresponse(); b = r.read(); return r.status, dict(r.getheaders()), b, ms(t0)
def plain(port, path):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path); r = c.getresponse(); b = r.read(); return r.status, dict(r.getheaders()), b
d = mkapp('f135', {'app.py': APP})
NOTRUST = ['--forwarded-allow-ips', '10.9.9.9']
SPOOF = '203.0.113.9'
print('== 实际的客户端是本机 127.0.0.1;客户端自己在请求里写了一个假的 X-Forwarded-For: 203.0.113.9。看 Flask 最终认定的客户端地址')
R['rows'] = {}
cases = [
    ('A', 'nginx 用 $remote_addr 覆盖 XFF,ProxyFix(x_for=1)', '$remote_addr', 1),
    ('B', 'nginx 用 $proxy_add_x_forwarded_for 追加,ProxyFix(x_for=1)', '$proxy_add_x_forwarded_for', 1),
    ('C', 'nginx 追加,但 ProxyFix(x_for=2)(多信任了一层)', '$proxy_add_x_forwarded_for', 2),
    ('D', 'nginx 追加,没有 ProxyFix,取 XFF 第一个元素(常见的写法)', '$proxy_add_x_forwarded_for', 0),
    ('E', 'nginx 覆盖,没有 ProxyFix(只看 remote_addr)', '$remote_addr', 0),
]
for key, label, xff, n in cases:
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}'] + NOTRUST + ['app:app'], X_FOR=str(n)) as s:
        hp, sp = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp, xff=xff)):
            st, h, b, _ = https(sp, 'GET', '/info', headers={'X-Forwarded-For': SPOOF}); j = json.loads(b)
    print(f'  [{key}] {label}'); print(f'      服务端收到的 XFF 头 = {j["raw_xff"]!r}'); print(f'      request.remote_addr = {j["remote_addr"]} | access_route = {j["access_route"]} | 取第一个元素 = {j["raw_first_xff"]}'); R['rows'][key] = dict(label=label, **j)
print()
print('== 不经过 nginx、直连 gunicorn 时,客户端自己写的 XFF 会被 ProxyFix 当真(没有可信代理却配了 ProxyFix)')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}'] + NOTRUST + ['app:app'], X_FOR='1') as s:
    st, h, b, _ = s.get('/info', headers={'X-Forwarded-For': SPOOF})[0], None, None, None
    r = s.get('/info', headers={'X-Forwarded-For': SPOOF}); j = json.loads(r[2]); print('  直连(没有 nginx),ProxyFix(x_for=1),请求头 XFF = 203.0.113.9 →', 'remote_addr =', j['remote_addr']); R['direct'] = j['remote_addr']
save('f135', R)
