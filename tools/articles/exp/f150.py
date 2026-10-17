import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f150'); R = {}
import http.client as hc, ssl, pathlib, textwrap
APP = '''
import os, time
from flask import Flask, request
from flask_socketio import SocketIO, emit
app = Flask(__name__)
sio = SocketIO(app, async_mode="threading", ping_interval=float(os.environ.get("PI", "25")), ping_timeout=float(os.environ.get("PT", "20")), cors_allowed_origins="*")
LOG = os.environ["LOGF"]
def log(s):
    with open(LOG, "a") as f: f.write(f"{time.time():.2f} {s}\\n")
@sio.on("connect")
def c(auth): log(f"connect transport={request.args.get('transport')}")
@sio.on("disconnect")
def d(reason=None): log(f"disconnect reason={reason}")
@sio.on("echo")
def echo(x): return x
'''
W = FT / 'f134nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(W / 'k.pem'), '-out', str(W / 'c.pem'), '-days', '2', '-subj', '/CN=localhost'], capture_output=True)
def conf(up, http_port, https_port, proxy_headers=True, buffering='on', redirect_http=True, max_body='1m', upgrade=False, read_timeout=60):
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
        location / {{ proxy_pass http://127.0.0.1:{up}; {ph} proxy_buffering {buffering}; {'proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection upgrade;' if upgrade else ''} proxy_read_timeout {read_timeout}s; }}
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
import socketio, threading as th_, statistics
d = mkapp('f150', {'app.py': APP}); LOGF = d / 'ws.log'
def srv(**env_): LOGF.write_text(''); return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'], LOGF=LOGF, **env_)
def client(sp, transports):
    c = socketio.Client(ssl_verify=False); c.connect(f'https://127.0.0.1:{sp}', transports=transports, wait_timeout=5); return c
print('== 一:nginx 有没有转发 WebSocket 升级头(Upgrade / Connection)')
R['upg'] = {}
for label, up in (('没有配置 Upgrade 头', False), ('配置了 proxy_http_version 1.1 + Upgrade + Connection', True)):
    with srv() as s:
        hp, sp = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp, upgrade=up)):
            time.sleep(0.5); res = {}
            for tr_label, tr in (('只允许 websocket', ['websocket']), ('默认(polling 再升级)', ['polling', 'websocket'])):
                try: c = client(sp, tr); time.sleep(0.8); res[tr_label] = f'连接成功,传输方式 {c.transport()}'; c.disconnect()
                except Exception as e: res[tr_label] = f'失败:{type(e).__name__}: {str(e)[:60]}'
            print(f'  [{label}]'); [print(f'     {k:<22} {v}') for k, v in res.items()]; R['upg'][label] = res
print()
print('== 二:nginx 的 proxy_read_timeout 会掐断空闲的 WebSocket(这里设成 3 秒演示):Socket.IO 的 ping 间隔要比它短')
R['idle'] = {}
for label, env_ in (('ping_interval=25(默认)', {'PI': '25', 'PT': '20'}), ('ping_interval=1', {'PI': '1', 'PT': '5'})):
    with srv(**env_) as s:
        hp, sp = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp, upgrade=True, read_timeout=3)):
            time.sleep(0.5); c = client(sp, ['websocket']); t0 = time.time(); alive = True
            while time.time() - t0 < 7:
                time.sleep(0.5)
                if not c.connected: alive = False; break
            elapsed = time.time() - t0; log = [l.split(' ', 1)[1] for l in LOGF.read_text().splitlines()]; print(f'  {label:<24} 空闲 7 秒后客户端是否还连着:{c.connected}(断开发生在约 {elapsed:.1f} 秒)| 服务端日志:{log}'); R['idle'][label] = [c.connected, round(elapsed, 1), log]
            try: c.disconnect()
            except Exception: pass
print()
print('== 三:经过 nginx 的往返延迟:websocket 与 polling(echo 事件,200 次中位数)')
R['rtt'] = {}
with srv() as s:
    hp, sp = free_port(), free_port()
    with Nginx(conf(s.port, hp, sp, upgrade=True)):
        time.sleep(0.5)
        for tr in (['websocket'], ['polling']):
            c = client(sp, tr); c.call('echo', 1, timeout=5); L = []
            for i in range(200): t0 = time.perf_counter(); c.call('echo', i, timeout=5); L.append(ms(t0))
            print(f'  {tr[0]:<10} 中位数 {statistics.median(L):.2f} ms,p95 {sorted(L)[int(len(L) * 0.95)]:.2f} ms'); R['rtt'][tr[0]] = [statistics.median(L), sorted(L)[int(len(L) * 0.95)]]; c.disconnect()
save('f150', R)
