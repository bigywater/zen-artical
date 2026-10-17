import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f149'); R = {}
import http.client as hc, ssl, pathlib, textwrap
APP = '''
import time, os, json
from flask import Flask, Response, request, stream_with_context
app = Flask(__name__)
LOG = os.environ["LOGF"]
def log(s):
    with open(LOG, "a") as f: f.write(s + "\\n")
def sse(event_id, data, event=None):
    return (f"id: {event_id}\\n" + (f"event: {event}\\n" if event else "") + f"data: {data}\\n\\n")
@app.get("/events")
def events():
    last = request.headers.get("Last-Event-ID"); log(f"connect Last-Event-ID={last}")
    start = int(last) + 1 if last else 1
    def gen():
        for i in range(start, start + 3):
            yield sse(i, json.dumps({"n": i})); time.sleep(0.3)
        yield ": keep-alive comment\\n\\n"
    resp = Response(stream_with_context(gen()), mimetype="text/event-stream"); resp.headers["Cache-Control"] = "no-cache"
    if os.environ.get("XAB") == "1": resp.headers["X-Accel-Buffering"] = "no"
    return resp
@app.get("/ping")
def ping(): return "pong"
@app.get("/page")
def page():
    return "<!doctype html><body><script>const got = []; const es = new EventSource('/events'); es.onmessage = e => { got.push(e.lastEventId + ':' + e.data); }; es.onerror = () => { got.push('onerror(readyState=' + es.readyState + ')'); }; setTimeout(() => { es.close(); document.body.setAttribute('data-got', JSON.stringify(got)); }, 5000);</script>"
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
d = mkapp('f149', {'app.py': APP}); LOGF = d / 'sse.log'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
import html as htmlmod, threading as th_
print('== 一:SSE 的线上格式:用原始 socket 读(不经过浏览器)')
LOGF.write_text('')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'], LOGF=LOGF, XAB='0') as s:
    time.sleep(1.0); c = hc.HTTPConnection('127.0.0.1', s.port, timeout=10); c.request('GET', '/events'); r = c.getresponse(); print('  状态', r.status, '| Content-Type:', r.getheader('Content-Type'), '| Cache-Control:', r.getheader('Cache-Control'), '| Transfer-Encoding:', r.getheader('Transfer-Encoding')); R['hdr'] = [r.getheader('Content-Type'), r.getheader('Cache-Control'), r.getheader('Transfer-Encoding')]
    body = r.read().decode(); print('  响应正文(原样):'); [print('    ' + repr(l)) for l in body.split('\n')]; R['body'] = body; c.close()
print()
print('== 二:真实 Chrome 的 EventSource:服务端每次发完 3 条就结束响应,浏览器自动重连并带 Last-Event-ID')
LOGF.write_text('')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'], LOGF=LOGF, XAB='0') as s:
    time.sleep(1.0); prof = FT / 'f149chrome'; shutil.rmtree(prof, ignore_errors=True)
    pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', '--virtual-time-budget=9000', '--dump-dom', f'http://127.0.0.1:{s.port}/page'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    tm = th_.Timer(50, lambda: os.killpg(pc.pid, signal.SIGKILL) if pc.poll() is None else None); tm.daemon = True; tm.start(); buf = ''; t0 = time.time()
    while time.time() - t0 < 60:
        l = pc.stdout.readline()
        if not l: break
        buf += l
        if '</html>' in l: break
    try: os.killpg(pc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError): pass
    tm.cancel(); pc.wait(); m = re.search(r'data-got="([^"]*)"', buf); got = json.loads(htmlmod.unescape(m.group(1))) if m else ['(没有结果)']
    print('  页面收到的事件(id:数据):', got); print('  服务端日志里的连接:', LOGF.read_text().strip().splitlines()); R['chrome'] = [got, LOGF.read_text().strip().splitlines()]
print()
print('== 三:经过 nginx(proxy_buffering on 默认):没有 X-Accel-Buffering 头与有这个头')
R['nginx'] = {}
for label, xab in (('没有 X-Accel-Buffering', '0'), ('响应头 X-Accel-Buffering: no', '1')):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'], LOGF=LOGF, XAB=xab) as s:
        hp, sp = free_port(), free_port()
        with Nginx(conf(s.port, hp, sp)):
            c = hc.HTTPSConnection('127.0.0.1', sp, context=CTX, timeout=20); t0 = time.perf_counter(); c.request('GET', '/events', headers={'Host': f'localhost:{sp}'}); r = c.getresponse(); times = []
            while True:
                ch = r.read(1)
                if not ch: break
                if ch == b'\n' and (not times or ms(t0) - times[-1] > 100): times.append(ms(t0))
            print(f'  {label:<30} 数据到达的时间点(ms,按 100 ms 以上的间隔分组):', [round(x) for x in times]); R['nginx'][label] = [round(x) for x in times]
print()
print('== 四:每个 SSE 连接占一个线程(gthread 8 线程,8 个连接挂着)')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'], LOGF=LOGF, XAB='0') as s:
    time.sleep(1.0)
    def hold(): c = hc.HTTPConnection('127.0.0.1', s.port, timeout=20); c.request('GET', '/events'); c.getresponse().read(); c.close()
    hs = [th_.Thread(target=hold) for _ in range(8)]; [h.start() for h in hs]; time.sleep(0.2)
    c = hc.HTTPConnection('127.0.0.1', s.port, timeout=20); t0 = time.perf_counter(); c.request('GET', '/ping'); c.getresponse().read(); dt = ms(t0); [h.join() for h in hs]; print(f'  8 个 SSE 连接在进行时,/ping 用了 {dt:.0f} ms(每个连接要 1 秒才结束)'); R['cap'] = dt
save('f149', R)
