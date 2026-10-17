import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f175'); R = {}
import textwrap, http.client as hc
from flask import Flask, request, jsonify, url_for, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
def mk(fix=None):
    a = Flask('pf'); a.logger.disabled = True
    @a.get('/items/')
    def items(): return jsonify(remote_addr=request.remote_addr, scheme=request.scheme, host=request.host, script_root=request.script_root, path=request.path, url=request.url, link=url_for('items'), static=url_for('static', filename='a.css'), external=url_for('items', _external=True))
    @a.get('/go')
    def go(): return redirect(url_for('items'))
    if fix: a.wsgi_app = ProxyFix(a.wsgi_app, **fix)
    return a
H = {'X-Forwarded-For': '203.0.113.5, 10.0.0.1', 'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'shop.example.test', 'X-Forwarded-Port': '8443', 'X-Forwarded-Prefix': '/app'}
print('== 一:ProxyFix 在 WSGI 环境里改了什么:同一个请求(带全套 X-Forwarded-* 头),不同的 ProxyFix 参数')
R['env'] = {}
cases = [('没有 ProxyFix', None), ('x_for=1, x_proto=1', dict(x_for=1, x_proto=1)), ('x_for=1, x_proto=1, x_host=1', dict(x_for=1, x_proto=1, x_host=1)), ('x_for=2', dict(x_for=2)), ('全部 =1(x_for/proto/host/port/prefix)', dict(x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1))]
for label, fix in cases:
    r = mk(fix).test_client().get('/items/', headers=H, base_url='http://internal:8000'); j = r.get_json(); R['env'][label] = j
    print(f'  [{label}]'); print(f'     remote_addr={j["remote_addr"]} scheme={j["scheme"]} host={j["host"]} script_root={j["script_root"]!r}'); print(f'     url_for("items")={j["link"]} | 静态文件={j["static"]} | _external={j["external"]}')
print()
print('== 二:nginx 把应用挂在子路径 /app/ 下(location /app/ { proxy_pass http://后端/; }):生成的链接对不对')
APP = '''
import os
from flask import Flask, request, jsonify, url_for, redirect, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix
app = Flask(__name__)
if os.environ.get("FIX") == "1": app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1, x_for=1, x_proto=1, x_host=1)
@app.get("/items/")
def items(): return jsonify(link=url_for("items"), static=url_for("static", filename="a.css"), form=render_template_string("<form action='{{ url_for(\\"items\\") }}'></form>"), path=request.path, script_root=request.script_root)
@app.get("/go")
def go(): return redirect(url_for("items"))
'''
d = mkapp('f175', {'app.py': APP, 'static/a.css': 'x'})
W = FT / 'f175nginx'; shutil.rmtree(W, ignore_errors=True); (W / 'logs').mkdir(parents=True); (W / 'tmp').mkdir()
def conf(up, lp, prefix_header):
    return textwrap.dedent(f'''
    worker_processes 1; daemon off; pid {W}/nginx.pid; error_log {W}/logs/error.log;
    events {{ worker_connections 64; }}
    http {{
      access_log off; client_body_temp_path {W}/tmp/b; proxy_temp_path {W}/tmp/p; fastcgi_temp_path {W}/tmp/f; uwsgi_temp_path {W}/tmp/u; scgi_temp_path {W}/tmp/s;
      server {{ listen 127.0.0.1:{lp}; location /app/ {{ proxy_pass http://127.0.0.1:{up}/; proxy_set_header Host $http_host; proxy_set_header X-Forwarded-For $remote_addr; proxy_set_header X-Forwarded-Proto $scheme; {"proxy_set_header X-Forwarded-Prefix /app;" if prefix_header else ""} }} }}
    }}''')
R['prefix'] = {}
for label, fix, ph in (('没有 ProxyFix', '0', False), ('ProxyFix(x_prefix=1),但 nginx 没传 X-Forwarded-Prefix', '1', False), ('ProxyFix(x_prefix=1) + nginx 传 X-Forwarded-Prefix: /app', '1', True)):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--forwarded-allow-ips', '10.9.9.9', 'app:app'], FIX=fix) as s:
        lp = free_port(); (W / 'nginx.conf').write_text(conf(s.port, lp, ph)); p = subprocess.Popen(['/opt/homebrew/bin/nginx', '-p', str(W), '-c', str(W / 'nginx.conf')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True); time.sleep(0.8)
        try:
            c = hc.HTTPConnection('127.0.0.1', lp, timeout=5); c.request('GET', '/app/items/'); j = json.loads(c.getresponse().read()); c.close(); c = hc.HTTPConnection('127.0.0.1', lp, timeout=5); c.request('GET', '/app/go'); r = c.getresponse(); loc = r.getheader('Location'); r.read(); c.close()
        finally:
            os.killpg(p.pid, signal.SIGTERM); p.wait(5)
    print(f'  [{label}]'); print(f'     浏览器访问 /app/items/ → url_for = {j["link"]} | 静态 = {j["static"]} | 表单 action = {j["form"][j["form"].index("action=") + 8:j["form"].index("action=") + 8 + len(j["link"])]} | 重定向 Location = {loc}'); R['prefix'][label] = dict(link=j['link'], static=j['static'], loc=loc, script_root=j['script_root'])
save('f175', R)
