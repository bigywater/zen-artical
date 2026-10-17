import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f133'); R = {}
import html as htmlmod, secrets, threading
from flask import request
SRV = '''
import os, secrets
from flask import Flask, request, g, make_response
app = Flask(__name__); mode = os.environ["MODE"]; OTHER = os.environ["OTHER"]
@app.before_request
def nonce(): g.nonce = secrets.token_urlsafe(12)
@app.after_request
def headers(r):
    if mode == "strict" and request.path in ("/page", "/framed"):
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'nonce-{g.nonce}'; frame-ancestors 'none'; connect-src 'self' {OTHER}"
        r.headers["Referrer-Policy"] = "no-referrer"
    if mode == "strict" and request.path == "/plain.js": r.headers["X-Content-Type-Options"] = "nosniff"
    return r
@app.get("/page")
def page():
    return f"""<!doctype html><meta charset=utf-8><body>
<script>document.body.setAttribute('data-inline', 'ran');</script>
<script nonce="{g.nonce}">document.body.setAttribute('data-nonce', 'ran');</script>
<script src="/plain.js"></script>
<script nonce="{g.nonce}">
fetch('{OTHER}/ref', {{mode:'cors'}}).then(r => r.text()).then(t => document.body.setAttribute('data-referer', t)).catch(e => document.body.setAttribute('data-referer', 'fetch error'));
setTimeout(() => {{ document.body.setAttribute('data-done', '1'); }}, 2500);
</script>"""
@app.get("/plain.js")
def plainjs():
    r = make_response("document.body.setAttribute('data-extjs', 'ran');"); r.headers["Content-Type"] = "text/plain"; return r
@app.get("/framed")
def framed(): return f"<!doctype html><script nonce='{g.nonce}'>parent.postMessage('embedded content loaded', '*')</script>framed page"
'''
OTHERSRV = '''
import os
from flask import Flask, request, make_response
app = Flask(__name__); TARGET = os.environ["TARGET"]
@app.get("/ref")
def ref():
    r = make_response("Referer=" + str(request.headers.get("Referer"))); r.headers["Access-Control-Allow-Origin"] = "*"; return r
@app.get("/outer")
def outer():
    return """<!doctype html><body><iframe src='%s/framed'></iframe><script>
window.addEventListener('message', e => { document.body.setAttribute('data-frame', '被嵌入的页面加载并回报了'); });
setTimeout(() => { if (!document.body.hasAttribute('data-frame')) document.body.setAttribute('data-frame', '没有回报(被拒绝嵌入)'); }, 3000);
</script>""" % TARGET
'''
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
def run_chrome(url):
    prof = FT / 'f133chrome'; shutil.rmtree(prof, ignore_errors=True)
    pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', '--virtual-time-budget=8000', '--dump-dom', url], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    buf = ''; t0 = time.time(); tm = threading.Timer(45, lambda: (lambda: os.killpg(pc.pid, signal.SIGKILL))() if pc.poll() is None else None); tm.daemon = True; tm.start()
    while time.time() - t0 < 60:
        l = pc.stdout.readline()
        if not l: break
        buf += l
        if '</html>' in l: break
    try: os.killpg(pc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError): pass
    tm.cancel(); pc.wait(); return buf
print('== 同一个页面,不加安全响应头 vs 加一组安全响应头,在真实 Chrome 里各检查什么被执行或被拦下')
R['modes'] = {}
for mode, label in (('none', '没有安全响应头'), ('strict', '加了 nosniff、X-Frame-Options、CSP(nonce)、Referrer-Policy')):
    p1 = free_port(); p2 = free_port(); o1 = f'http://127.0.0.1:{p1}'; o2 = f'http://localhost:{p2}'
    d1 = mkapp('f133a', {'app.py': SRV}); d2 = mkapp('f133b', {'app.py': OTHERSRV})
    with Server(d1, ['gunicorn', '-b', f'127.0.0.1:{p1}', '-w', '1', 'app:app'], port=p1, MODE=mode, OTHER=o2):
        with Server(d2, ['gunicorn', '-b', f'127.0.0.1:{p2}', '-w', '1', 'app:app'], port=p2, TARGET=o1):
            dom = run_chrome(f'{o1}/page'); dom2 = run_chrome(f'{o2}/outer')
    attrs = dict(re.findall(r'data-([a-z]+)="([^"]*)"', dom)); res = {'内联脚本': attrs.get('inline', '没有执行'), '带 nonce 的内联脚本': attrs.get('nonce', '没有执行'), 'MIME 是 text/plain 的外部脚本': attrs.get('extjs', '没有执行'), '收到的 Referer': htmlmod.unescape(attrs.get('referer', '(无)')), '被另一个站点用 iframe 嵌入': dict(re.findall(r'data-([a-z]+)="([^"]*)"', dom2)).get('frame', '(无结果)')}
    print(f'  [{label}]'); [print(f'     {k:<28} {v}') for k, v in res.items()]; R['modes'][mode] = res
print()
print('== 响应头本身(test_client,看 /page 的响应头)')
from flask import Flask
os.environ['MODE'] = 'strict'; os.environ['OTHER'] = 'http://localhost:1'
import importlib.util
spec = importlib.util.spec_from_file_location('sec_app', str(FT / 'f133a' / 'app.py')); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r = m.app.test_client().get('/page'); hh = {k: v for k, v in r.headers if k in ('X-Content-Type-Options', 'X-Frame-Options', 'Content-Security-Policy', 'Referrer-Policy')}; [print(f'  {k}: {v}'[:150]) for k, v in hh.items()]; R['hdrs'] = hh
print()
print('== HSTS 只能在 HTTPS 响应里发(浏览器忽略 http 上的 HSTS):按 request.is_secure 判断')
a = Flask('h'); a.logger.disabled = True
@a.get('/')
def i(): return 'x'
@a.after_request
def hsts(r):
    if request.is_secure: r.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return r
c = a.test_client(); r1 = c.get('/'); r2 = c.get('/', base_url='https://localhost'); print('  http 请求:', r1.headers.get('Strict-Transport-Security'), '| https 请求:', r2.headers.get('Strict-Transport-Security')); R['hsts'] = [r1.headers.get('Strict-Transport-Security'), r2.headers.get('Strict-Transport-Security')]
print('  behind a TLS-terminating proxy, request.is_secure 是否为真取决于 ProxyFix(x_proto=1)(见第 135 篇);没配时即使用户走的是 https,这里也是 http')
r3 = Flask('p'); r3.logger.disabled = True
from werkzeug.middleware.proxy_fix import ProxyFix
@r3.get('/')
def j(): return str(request.is_secure)
print('  无 ProxyFix,带 X-Forwarded-Proto: https →', r3.test_client().get('/', headers={'X-Forwarded-Proto': 'https'}).get_data(as_text=True)); r3.wsgi_app = ProxyFix(r3.wsgi_app, x_proto=1); print('  ProxyFix(x_proto=1) →', r3.test_client().get('/', headers={'X-Forwarded-Proto': 'https'}).get_data(as_text=True)); R['proto'] = ['False', 'True']
save('f133', R)
