import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f134'); R = {}
import http.client as hc, ssl, pathlib, textwrap
APP = '''
import os, time
from flask import Flask, request, jsonify, url_for, redirect, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix
app = Flask(__name__)
if os.environ.get("FIX") == "1": app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
@app.get("/info")
def info(): return jsonify(scheme=request.scheme, is_secure=request.is_secure, host=request.host, remote_addr=request.remote_addr, external=url_for("info", _external=True))
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
def conf(up, http_port, https_port, proxy_headers=True, buffering='on', redirect_http=True, max_body='1m'):
    ph = '''proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-For $remote_addr;
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
d = mkapp('f134', {'app.py': APP})
NOTRUST = ['--forwarded-allow-ips', '10.9.9.9']
def info_and_dir(label, gargs, fix, key, key2):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}'] + gargs + ['app:app'], FIX=fix) as s:
        hp, sp = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp)):
            st, h, b, _ = https(sp, 'GET', '/info'); j = json.loads(b); print('  /info →', j); R[key] = j
            st, h, b, _ = https(sp, 'GET', '/dir'); print('  GET /dir(规则是 /dir/)→', st, 'Location:', h.get('Location')); R[key2] = [st, h.get('Location')]
print('== 一:nginx 终止 TLS;gunicorn 不信任任何代理地址,Flask 也没有 ProxyFix。请求是 https://localhost:端口/info')
info_and_dir('', NOTRUST, '0', 'nofix', 'redir_nofix')
print()
print('== 二:gunicorn 用默认设置(默认信任来自 127.0.0.1 的 X-Forwarded-Proto),Flask 没有 ProxyFix')
info_and_dir('', [], '0', 'gunicorn_default', 'redir_gdefault')
print('  (gunicorn 自己把 X-Forwarded-Proto 翻译成了 wsgi.url_scheme)')
print()
print('== 三:gunicorn 不信任代理,由 Flask 的 ProxyFix(x_for=1, x_proto=1, x_host=1) 负责')
info_and_dir('', NOTRUST, '1', 'fix', 'redir_fix')
print()
print('== 四:HTTP 到 HTTPS 的跳转由 nginx 做')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], FIX='1') as s:
    hp, sp = free_port(), free_port()
    with Nginx(conf(s.port, hp, sp)):
        st, h, b = plain(hp, '/info?x=1'); print('  http://…/info?x=1 →', st, 'Location:', h.get('Location')); R['http_redirect'] = [st, h.get('Location')]
print()
print('== 五:nginx 在 Flask 之前的限制:请求体大小(client_max_body_size 默认 1m)')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], FIX='1') as s:
    hp, sp = free_port(), free_port()
    with Nginx(conf(s.port, hp, sp)):
        R['size'] = {}
        for kb in (500, 900, 1100, 3000):
            st, h, b, _ = https(sp, 'POST', '/size', body=b'x' * (kb * 1024)); print(f'  上传 {kb} KB → {st}' + (f' ({b.decode()[:40]!r})' if st == 200 else ' (nginx 直接拒绝,请求没有到达 Flask)')); R['size'][kb] = st
    with Nginx(conf(s.port, hp, sp, max_body='5m')):
        st, h, b, _ = https(sp, 'POST', '/size', body=b'x' * (3000 * 1024)); print('  client_max_body_size 5m 后上传 3000 KB →', st); R['size5m'] = st
print()
print('== 六:反向代理的缓冲会让流式响应失效:一个每 0.3 秒吐一块的响应,proxy_buffering on 与 off')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '4', 'app:app'], FIX='1') as s:
    R['buf'] = {}
    for mode in ('on', 'off'):
        hp, sp = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp, buffering=mode)):
            c = hc.HTTPSConnection('127.0.0.1', sp, context=CTX, timeout=20); t0 = time.perf_counter(); c.request('GET', '/stream', headers={'Host': f'localhost:{sp}'}); r = c.getresponse(); times = []
            while True:
                ch = r.read(8)
                if not ch: break
                times.append(round(ms(t0)))
            print(f'  proxy_buffering {mode:<3} 读到每一块数据的时间(ms):', times); R['buf'][mode] = [times[0], times[-1], len(times)]
save('f134', R)
