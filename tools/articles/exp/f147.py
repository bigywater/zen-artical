import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f147'); R = {}
import http.client as hc, ssl, pathlib, textwrap
APP = '''
import os, time
from flask import Flask, request, jsonify
app = Flask(__name__)
LOG = os.environ["LOGF"]
def mark(s):
    with open(LOG, "a") as f: f.write(s + "\\n")
@app.get("/slow")
def slow():
    n = float(request.args.get("s", "5")); time.sleep(n); mark("slow finished"); return "slow done"
@app.get("/deadline")
def deadline():
    limit = float(request.args.get("limit", "1")); start = time.perf_counter(); steps = 0
    while steps < 50:
        if time.perf_counter() - start > limit: mark("deadline: gave up"); return jsonify(error="took too long", steps=steps), 504
        time.sleep(0.1); steps += 1
    return jsonify(ok=True)
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
d = mkapp('f147', {'app.py': APP}); LOGF = d / 'marks.log'
def nginx_conf(up, hp, sp, read_timeout):
    return conf(up, hp, sp).replace('proxy_buffering on;', f'proxy_buffering on; proxy_read_timeout {read_timeout}s;')
def get(port, path, timeout=30):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=timeout); t0 = time.perf_counter()
    try: c.request('GET', path); r = c.getresponse(); b = r.read(); return r.status, ms(t0), b.decode()[:60].strip().replace('\n', ' ')
    except Exception as e: return type(e).__name__, ms(t0), ''
    finally: c.close()
def gc(extra, **env_): LOGF.write_text(''); return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}'] + extra + ['app:app'], LOGF=LOGF, **env_)
print('== 一:gunicorn --timeout 2,视图要 5 秒:不同 worker 类型的结果')
R['gun'] = {}
for label, extra in (('sync worker', ['-w', '1', '--timeout', '2']), ('gthread worker', ['-w', '1', '-k', 'gthread', '--threads', '4', '--timeout', '2'])):
    with gc(extra) as s:
        time.sleep(1.0); r = get(s.port, '/slow?s=5'); time.sleep(0.5); log = s.logtext(); to = 'WORKER TIMEOUT' in log
        print(f'  {label:<16} 客户端:{r[0]},用时 {r[1]:.0f} ms,{r[2]!r} | 服务端日志有 WORKER TIMEOUT:{to}'); R['gun'][label] = [r[0], r[1], to]
print()
print('== 二:nginx proxy_read_timeout 2 秒,gunicorn --timeout 30:客户端得到什么,服务端的工作还继续吗')
with gc(['-w', '1', '-k', 'gthread', '--threads', '4', '--timeout', '30']) as s:
    hp, sp = free_port(), free_port()
    with Nginx(nginx_conf(s.port, hp, sp, 2)):
        r = get(sp, '/slow?s=5') if False else None
        c = hc.HTTPSConnection('127.0.0.1', sp, context=CTX, timeout=30); t0 = time.perf_counter(); c.request('GET', '/slow?s=5', headers={'Host': f'localhost:{sp}'}); resp = c.getresponse(); body = resp.read().decode()[:80].strip().replace('\n', ' '); dt = ms(t0)
        print(f'  客户端:{resp.status},用时 {dt:.0f} ms,{body!r}'); R['nginx'] = [resp.status, dt]; time.sleep(4.0)
        print('  4 秒之后查看服务端:慢请求是否仍然跑完了:', 'slow finished' in LOGF.read_text(), '(客户端早就拿到 504,工作还是做完了)'); R['still_runs'] = 'slow finished' in LOGF.read_text()
print()
print('== 三:应用层的截止时间:协作式地检查时间,超时就提前返回')
with gc(['-w', '1', '-k', 'gthread', '--threads', '4']) as s:
    time.sleep(1.0); r = get(s.port, '/deadline?limit=1'); print(f'  /deadline?limit=1 → {r[0]},用时 {r[1]:.0f} ms,{r[2]!r}'); R['deadline'] = [r[0], r[1]]; r2 = get(s.port, '/deadline?limit=20'); print(f'  /deadline?limit=20(够用)→ {r2[0]},用时 {r2[1]:.0f} ms'); R['deadline_ok'] = [r2[0], r2[1]]
save('f147', R)
