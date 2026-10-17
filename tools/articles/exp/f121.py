import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f121'); R = {}
import html as htmlmod
API = '''
import os
from flask import Flask, session, request, jsonify, make_response
app = Flask(__name__); app.config['SECRET_KEY'] = 'k' * 32
app.config['SESSION_COOKIE_HTTPONLY'] = os.environ['HTTPONLY'] == '1'
ss = os.environ['SAMESITE']; app.config['SESSION_COOKIE_SAMESITE'] = None if ss == 'unset' else ss
app.config['SESSION_COOKIE_SECURE'] = os.environ['SECURE'] == '1'
B_ORIGIN = os.environ['B_ORIGIN']
PAGE_A = """<!doctype html><meta charset=utf-8><pre id=out>running</pre><script>
(async () => {
  const res = {};
  const r = await fetch('/login', {method: 'POST'}); res.login = r.status;
  res.js_cookie_visible = document.cookie.includes('session');
  res.js_cookie = document.cookie ? document.cookie.split('=')[0] + '=<值>' : '(空)';
  const r2 = await fetch('/read', {credentials: 'same-origin'}); res.first_party_read = (await r2.json()).has_session;
  const fr = document.createElement('iframe'); fr.src = '__B__/b';
  window.addEventListener('message', (e) => { res.cross_site_read = e.data; document.getElementById('out').textContent = 'RESULT:' + JSON.stringify(res); });
  document.body.appendChild(fr);
  setTimeout(() => { if (!res.cross_site_read) { res.cross_site_read = 'no message'; document.getElementById('out').textContent = 'RESULT:' + JSON.stringify(res); } }, 8000);
})();
</script>"""
@app.get('/a')
def a(): return PAGE_A.replace('__B__', B_ORIGIN)
@app.post('/login')
def login(): session['u'] = 'ann'; return 'ok'
@app.get('/read')
def read():
    r = make_response(jsonify(has_session=bool(session.get('u'))))
    r.headers['Access-Control-Allow-Origin'] = B_ORIGIN; r.headers['Access-Control-Allow-Credentials'] = 'true'; return r
'''
BPAGE = '''from flask import Flask
import os
app = Flask(__name__)
@app.get('/b')
def b(): return """<!doctype html><script>
fetch('%s/read', {credentials: 'include'}).then(r => r.json()).then(j => parent.postMessage('cookie sent: ' + j.has_session, '*')).catch(e => parent.postMessage('fetch failed: ' + e.message, '*'));
</script>""" % os.environ['API_ORIGIN']
'''
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
R['modes'] = {}
print('== 页面 A 在 http://127.0.0.1:P2(cookie 所属站点),页面 B 在 http://localhost:P1(跨站)被 A 以 iframe 嵌入,B 用 fetch(credentials: include) 请求 127.0.0.1:P2/read')
cases = [('HttpOnly=True, SameSite 未设置', '1', 'unset', '0'), ('HttpOnly=False, SameSite 未设置', '0', 'unset', '0'), ('HttpOnly=True, SameSite=Lax', '1', 'Lax', '0'), ('HttpOnly=True, SameSite=Strict', '1', 'Strict', '0'), ('HttpOnly=True, SameSite=None(无 Secure)', '1', 'None', '0'), ('HttpOnly=True, SameSite=None + Secure', '1', 'None', '1'), ('HttpOnly=True, SameSite=Lax + Secure', '1', 'Lax', '1')]
for label, ho, ss, sec in cases:
    p2 = free_port(); p1 = free_port(); a_origin = f'http://127.0.0.1:{p2}'; b_origin = f'http://localhost:{p1}'
    da = mkapp('f121a', {'app.py': API}); db_ = mkapp('f121b', {'app.py': BPAGE})
    with Server(da, ['gunicorn', '-b', f'127.0.0.1:{p2}', '-w', '1', 'app:app'], port=p2, HTTPONLY=ho, SAMESITE=ss, SECURE=sec, B_ORIGIN=b_origin):
        with Server(db_, ['gunicorn', '-b', f'127.0.0.1:{p1}', '-w', '1', 'app:app'], port=p1, API_ORIGIN=a_origin):
            for attempt in range(4):
                prof = FT / 'f121chrome'; shutil.rmtree(prof, ignore_errors=True)
                pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', '--virtual-time-budget=20000', '--dump-dom', f'{a_origin}/a'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
                buf = ''; t0 = time.time()
                while time.time() - t0 < 80:
                    l = pc.stdout.readline()
                    if not l: break
                    buf += l
                    if '</html>' in l: break
                try: os.killpg(pc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                pc.wait(); m = re.search(r'RESULT:(\{.*?\})</pre>', buf, re.S); res = json.loads(htmlmod.unescape(m.group(1))) if m else {'?': 'no result: ' + buf[-200:]}
                if res.get('cross_site_read') not in (None, 'no message'): break
    print(f'  [{label}]'); [print(f'     {k:<20} {v}') for k, v in res.items()]; R['modes'][label] = res
save('f121', R)
