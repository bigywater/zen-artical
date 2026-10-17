import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f169'); R = {}
import threading
import http.client as hc, ssl, pathlib, textwrap, threading
APP = '''
import os, time
from flask import Flask, send_file, Response, request
app = Flask(__name__)
BIG = os.environ["BIG"]
@app.get("/sendfile")
def sendfile(): return send_file(BIG, mimetype="application/octet-stream", conditional=True)
@app.get("/readall")
def readall():
    with open(BIG, "rb") as f: data = f.read()
    return Response(data, mimetype="application/octet-stream")
@app.get("/chunks")
def chunks():
    def gen():
        with open(BIG, "rb") as f:
            while True:
                c = f.read(64 * 1024)
                if not c: break
                yield c
    return Response(gen(), mimetype="application/octet-stream", headers={"Content-Length": str(os.path.getsize(BIG))})
@app.get("/accel")
def accel():
    r = Response(status=200); r.headers["X-Accel-Redirect"] = "/protected/big.bin"; r.headers["Content-Type"] = "application/octet-stream"; return r
@app.get("/ping")
def ping(): return "pong"
'''
W = FT / 'f134nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(W / 'k.pem'), '-out', str(W / 'c.pem'), '-days', '2', '-subj', '/CN=localhost'], capture_output=True)
def conf(up, http_port, https_port, proxy_headers=True, buffering='on', redirect_http=True, max_body='1m', protected=None):
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
        {('location /protected/ { internal; alias ' + protected + '/; }') if protected else ''}\n        location / {{ proxy_pass http://127.0.0.1:{up}; {ph} proxy_buffering {buffering}; }}
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
SIZE_MB = 300
big = FT / 'f169_big'; big.mkdir(exist_ok=True); bigf = big / 'big.bin'
if not bigf.exists() or bigf.stat().st_size != SIZE_MB * 1024 * 1024:
    with open(bigf, 'wb') as f:
        for _ in range(SIZE_MB): f.write(os.urandom(1024 * 1024))
d = mkapp('f169', {'app.py': APP})
def rss_of(port):
    pids = subprocess.run(['pgrep', '-f', f'127.0.0.1:{port}'], capture_output=True, text=True).stdout.split(); return sum(int(subprocess.run(['ps', '-o', 'rss=', '-p', p], capture_output=True, text=True).stdout.strip() or 0) for p in pids) / 1024
def curl(url, extra=()):
    out = subprocess.run(['curl', '-s', '-k', '-o', '/dev/null', '-w', '%{time_total} %{speed_download} %{size_download} %{http_code}'] + list(extra) + [url], capture_output=True, text=True, timeout=300).stdout.split(); return float(out[0]), float(out[1]) / 1e6, int(float(out[2])), out[3]
def measure(label, port, path, base='http', extra=()):
    mx = [rss_of(port)]; stop = threading.Event()
    def mon():
        while not stop.is_set(): mx[0] = max(mx[0], rss_of(port)); time.sleep(0.05)
    t = threading.Thread(target=mon); t.start(); r = curl(f'{base}://127.0.0.1:{port}{path}', extra); stop.set(); t.join(); return r, mx[0]
print(f'== 一:下载 {SIZE_MB} MB 的文件:Flask 的 send_file、整个读进内存、手写分块生成器(gunicorn gthread 单 worker,curl 单连接,本机)')
R['direct'] = {}
for label, path in (('send_file(sendfile)', '/sendfile'), ('整个文件读进内存再返回', '/readall'), ('64 KB 一块的生成器', '/chunks')):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '4', '--timeout', '120', 'app:app'], BIG=str(bigf)) as s:
        time.sleep(1.0); base_rss = rss_of(s.port); (t, sp, n, code), mx = measure(label, s.port, path); print(f'  {label:<26} {code} 用时 {t:5.2f} 秒 | 速度 {sp:6.0f} MB/s | 收到 {n / 1e6:.0f} MB | worker 空闲内存 {base_rss:.0f} MB,下载期间峰值 {mx:.0f} MB'); R['direct'][label] = [t, sp, mx - base_rss]
print()
print('== 二:Range 请求(断点续传):send_file 支持 Range;只取最后 1 MB')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '4', 'app:app'], BIG=str(bigf)) as s:
    time.sleep(1.0); st = SIZE_MB * 1024 * 1024
    r = subprocess.run(['curl', '-s', '-D', '-', '-o', '/dev/null', '-H', f'Range: bytes={st - 1048576}-', f'http://127.0.0.1:{s.port}/sendfile'], capture_output=True, text=True).stdout; hdr = {l.split(':', 1)[0].lower(): l.split(':', 1)[1].strip() for l in r.splitlines() if ':' in l}
    print('  状态行:', r.splitlines()[0].strip(), '| Content-Range:', hdr.get('content-range'), '| Content-Length:', hdr.get('content-length'), '| Accept-Ranges:', hdr.get('accept-ranges'), '| ETag:', bool(hdr.get('etag'))); R['range'] = [r.splitlines()[0].strip(), hdr.get('content-range'), hdr.get('content-length')]
    r2 = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-H', f'If-None-Match: {hdr.get("etag")}', f'http://127.0.0.1:{s.port}/sendfile'], capture_output=True, text=True).stdout; print('  带 If-None-Match 的再次请求 →', r2, '(304,不再传文件)'); R['304'] = r2
print()
print('== 三:经过 nginx:Flask 自己发文件 vs 返回 X-Accel-Redirect 让 nginx 发(Flask 只回一个头)')
R['nginx'] = {}
for label, path, prot in (('经 nginx 代理 Flask 的 send_file', '/sendfile', None), ('X-Accel-Redirect 让 nginx 直接发文件', '/accel', str(big))):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '4', '--timeout', '120', '--access-logfile', '-', '--access-logformat', 'REQ %(U)s %(L)s', 'app:app'], BIG=str(bigf)) as s:
        hp, sp_ = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp_, protected=prot)):
            time.sleep(0.8); t, spd, n, code = curl(f'https://127.0.0.1:{sp_}{path}'); time.sleep(0.5); line = [l for l in s.logtext().splitlines() if l.startswith('REQ ' + path)][-1]; held = float(line.split()[-1])
            print(f'  {label:<34} {code} 用时 {t:5.2f} 秒 | {spd:6.0f} MB/s | 收到 {n / 1e6:.0f} MB | gunicorn 日志里这个请求占用 worker {held * 1000:.0f} ms'); R['nginx'][label] = [t, spd, n, held * 1000]
save('f169', R)
