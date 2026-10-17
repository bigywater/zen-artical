import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f176'); R = {}
import textwrap, gzip as gz, http.client as hc
APP = '''
import os
from flask import Flask
app = Flask(__name__)
if os.environ.get("MAXAGE"): app.config["SEND_FILE_MAX_AGE_DEFAULT"] = int(os.environ["MAXAGE"])
@app.get("/")
def index(): return "home"
'''
CSS = '\n'.join(f'.cls{i} {{ color: #{i % 1000:03d}; margin: {i % 20}px; padding: {i % 7}px 4px; font-family: "Helvetica", sans-serif; }}' for i in range(500))
d = mkapp('f176', {'app.py': APP, 'static/app.css': CSS})
W = FT / 'f176nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
def conf(up, lp, static_dir, gzip_on=False, expires=None):
    return textwrap.dedent(f'''
    worker_processes 1; daemon off; pid {W}/nginx.pid; error_log {W}/logs/error.log;
    events {{ worker_connections 256; }}
    http {{
      access_log off; client_body_temp_path {W}/tmp/b; proxy_temp_path {W}/tmp/p; fastcgi_temp_path {W}/tmp/f; uwsgi_temp_path {W}/tmp/u; scgi_temp_path {W}/tmp/s;
      include /opt/homebrew/etc/nginx/mime.types;
      {"gzip on; gzip_types text/css application/javascript; gzip_min_length 256;" if gzip_on else ""}
      server {{ listen 127.0.0.1:{lp};
        location /static/ {{ alias {static_dir}/; {("expires " + expires + ";") if expires else ""} }}
        location / {{ proxy_pass http://127.0.0.1:{up}; }} }}
    }}''')
def req(port, path, headers=None):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=10); c.request('GET', path, headers=headers or {}); r = c.getresponse(); b = r.read(); h = {k.lower(): v for k, v in r.getheaders()}; c.close(); return r.status, h, b
def ab(port, path, n=4000, c=32):
    out = subprocess.run(['ab', '-n', str(n), '-c', str(c), f'http://127.0.0.1:{port}{path}'], capture_output=True, text=True, timeout=120).stdout; return float(re.search(r'Requests per second:\s+([\d.]+)', out).group(1)), int(re.search(r'Failed requests:\s+(\d+)', out).group(1))
print(f'== 一:Flask 自带的 static 路由返回的缓存相关响应头(CSS 文件 {len(CSS) / 1024:.0f} KB)')
R['hdr'] = {}
for label, env_ in (('默认', {}), ('SEND_FILE_MAX_AGE_DEFAULT = 31536000', {'MAXAGE': '31536000'})):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app'], **env_) as s:
        time.sleep(0.8); st, h, b = req(s.port, '/static/app.css'); st2, h2, b2 = req(s.port, '/static/app.css', {'If-None-Match': h['etag']})
    print(f'  [{label}] Cache-Control: {h.get("cache-control")} | ETag: {bool(h.get("etag"))} | Last-Modified: {bool(h.get("last-modified"))} | 带 If-None-Match 再请求 → {st2}'); R['hdr'][label] = [h.get('cache-control'), st2]
print()
print('== 二:吞吐:ApacheBench 4000 个请求、32 并发,取同一个 CSS 文件(gunicorn sync × 4 vs nginx 直接发文件;同机压测,只看相对关系)')
R['bench'] = {}
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app']) as s:
    time.sleep(1.0); ab(s.port, '/static/app.css', 300, 8); a = ab(s.port, '/static/app.css')
    lp = free_port(); (W / 'nginx.conf').write_text(conf(s.port, lp, str(d / 'static'))); p = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
    try: ab(lp, '/static/app.css', 300, 8); b = ab(lp, '/static/app.css'); c_ = ab(lp, '/')
    finally:
        try: os.killpg(p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError): pass
        p.wait(5)
print(f'  Flask static 路由(gunicorn sync×4){a[0]:.0f} 请求/秒 | nginx 直接发静态文件 {b[0]:.0f} 请求/秒 | (对照:经 nginx 代理到 Flask 的动态页 / {c_[0]:.0f} 请求/秒)'); R['bench'] = [a[0], b[0], c_[0]]
print()
print('== 三:nginx 的 gzip 与 expires:压缩后体积、缓存头')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app']) as s:
    time.sleep(0.8); lp = free_port(); (W / 'nginx.conf').write_text(conf(s.port, lp, str(d / 'static'), gzip_on=True, expires='1y')); p = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
    try:
        st, h, b = req(lp, '/static/app.css'); st2, h2, b2 = req(lp, '/static/app.css', {'Accept-Encoding': 'gzip'})
    finally:
        try: os.killpg(p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError): pass
        p.wait(5)
print(f'  不带 Accept-Encoding:{len(b)} 字节,Content-Encoding={h.get("content-encoding")},Cache-Control={h.get("cache-control")}'); print(f'  带 Accept-Encoding: gzip:{len(b2)} 字节({len(b2) / len(b) * 100:.1f}%),Content-Encoding={h2.get("content-encoding")},Vary={h2.get("vary")}'); R['gzip'] = [len(b), len(b2), h.get('cache-control'), h2.get('content-encoding')]
print()
print('== 四:缓存失效:长缓存(1 年)的文件改了内容,浏览器不会重新请求——文件名带内容哈希(或查询参数版本号)解决')
import hashlib
def versioned(name): return f'{name}?v={hashlib.md5((d / "static" / name).read_bytes()).hexdigest()[:8]}'
v1 = versioned('app.css'); (d / 'static' / 'app.css').write_text(CSS + '\n.new { color: red; }'); v2 = versioned('app.css'); print('  内容改之前 URL:', '/static/' + v1, '| 改之后 URL:', '/static/' + v2, '→ URL 变了,浏览器会当作新资源重新下载'); R['version'] = [v1, v2]
save('f176', R)
