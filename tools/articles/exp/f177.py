import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f177'); R = {}
import textwrap, http.client as hc
APP = '''
import os
from flask import Flask, request, session, abort, Response, jsonify
app = Flask(__name__); app.config["SECRET_KEY"] = "k" * 32
DOCS = {"1": {"owner": "ann", "file": "report.pdf", "name": "年度 报告.pdf"}, "2": {"owner": "bob", "file": "secret.txt", "name": "secret.txt"}}
@app.post("/login/<u>")
def login(u): session["u"] = u; return "ok"
@app.get("/docs/<did>")
def doc(did):
    u = session.get("u")
    if not u: abort(401)
    d = DOCS.get(did)
    if d is None: abort(404)
    if d["owner"] != u: abort(403)
    r = Response(status=200); r.headers["X-Accel-Redirect"] = "/_protected/" + d["file"]
    from urllib.parse import quote
    r.headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(d["name"]); r.headers["Content-Type"] = "application/octet-stream"; return r
'''
d = mkapp('f177', {'app.py': APP})
media = FT / 'f177_media'; shutil.rmtree(media, ignore_errors=True); (media / 'public').mkdir(parents=True); (media / 'private').mkdir()
(media / 'public' / 'a.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'x' * 100); (media / 'public' / 'v.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>hi</text></svg>'); (media / 'private' / 'report.pdf').write_bytes(b'%PDF-1.4 ann-report'); (media / 'private' / 'secret.txt').write_text('bob secret')
W = FT / 'f177nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
def conf(up, lp):
    return textwrap.dedent(f'''
    worker_processes 1; daemon off; pid {W}/nginx.pid; error_log {W}/logs/error.log;
    events {{ worker_connections 64; }}
    http {{
      access_log off; client_body_temp_path {W}/tmp/b; proxy_temp_path {W}/tmp/p; fastcgi_temp_path {W}/tmp/f; uwsgi_temp_path {W}/tmp/u; scgi_temp_path {W}/tmp/s;
      include /opt/homebrew/etc/nginx/mime.types;
      server {{ listen 127.0.0.1:{lp};
        location /media/ {{ alias {media}/public/; autoindex off; add_header X-Content-Type-Options nosniff always; add_header Content-Security-Policy "default-src 'none'; sandbox" always; expires 7d; }}
        location /_protected/ {{ internal; alias {media}/private/; }}
        location / {{ proxy_pass http://127.0.0.1:{up}; proxy_set_header Host $http_host; }} }}
    }}''')
def req(port, method, path, headers=None):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=10); c.request(method, path, headers=headers or {}); r = c.getresponse(); b = r.read(); h = {k.lower(): v for k, v in r.getheaders()}; c.close(); return r.status, h, b
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app']) as s:
    time.sleep(0.8); lp = free_port(); (W / 'nginx.conf').write_text(conf(s.port, lp)); p = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
    try:
        print('== 一:公开的媒体文件:nginx 直接发,带安全响应头;不存在的文件与目录')
        st, h, b = req(lp, 'GET', '/media/a.png'); print(f'  GET /media/a.png → {st} | Content-Type {h.get("content-type")} | X-Content-Type-Options {h.get("x-content-type-options")} | CSP {h.get("content-security-policy")} | Cache-Control {h.get("cache-control")}'); R['public'] = [st, h.get('content-type'), h.get('x-content-type-options'), h.get('content-security-policy'), h.get('cache-control')]
        st, h, b = req(lp, 'GET', '/media/v.svg'); print(f'  GET /media/v.svg → {st} | Content-Type {h.get("content-type")}(SVG 可以内嵌脚本,所以加了 CSP sandbox 限制它)'); R['svg'] = [st, h.get('content-type')]
        for path in ('/media/nope.png', '/media/', '/media/../private/secret.txt'): st, h, b = req(lp, 'GET', path); print(f'  GET {path:<30} → {st}'); R.setdefault('miss', {})[path] = st
        print()
        print('== 二:私有文件:必须先过 Flask 的权限检查,再由 nginx 发(X-Accel-Redirect 到 internal location)')
        R['private'] = {}
        def case(label, cookie, path):
            st, h, b = req(lp, 'GET', path, {'Cookie': cookie} if cookie else None); body = b[:40]; print(f'  {label:<34} → {st} | {body!r} | Content-Disposition: {h.get("content-disposition")}'); R['private'][label] = [st, body.decode(errors='replace'), h.get('content-disposition')]
        case('未登录访问 /docs/1', None, '/docs/1')
        c = hc.HTTPConnection('127.0.0.1', lp); c.request('POST', '/login/ann'); r = c.getresponse(); r.read(); ck_ann = r.getheader('Set-Cookie').split(';')[0]; c.close()
        c = hc.HTTPConnection('127.0.0.1', lp); c.request('POST', '/login/bob'); r = c.getresponse(); r.read(); ck_bob = r.getheader('Set-Cookie').split(';')[0]; c.close()
        case('ann 访问自己的 /docs/1', ck_ann, '/docs/1'); case('ann 访问 bob 的 /docs/2', ck_ann, '/docs/2'); case('bob 访问自己的 /docs/2', ck_bob, '/docs/2'); case('访问不存在的 /docs/9', ck_ann, '/docs/9')
        st, h, b = req(lp, 'GET', '/_protected/report.pdf'); print(f'  直接请求内部地址 /_protected/report.pdf → {st}(internal location 只能由 nginx 内部重定向访问)'); R['direct_internal'] = st
        st, h, b = req(lp, 'GET', '/docs/1', {'Cookie': ck_ann, 'Range': 'bytes=0-4'}); print(f'  带 Range 的授权请求 → {st} | {b!r} | Content-Range {h.get("content-range")}(nginx 对 X-Accel-Redirect 的文件也支持 Range)'); R['range'] = [st, b.decode(errors='replace'), h.get('content-range')]
    finally:
        try: os.killpg(p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError): pass
        p.wait(5)
save('f177', R)
