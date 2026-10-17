import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import json as _j
tee('f186'); R = {}
APP = '''
import os
from flask import Flask, render_template_string
app = Flask(__name__)
SECRET_MARK = "marker-in-source-code"
@app.get("/boom")
def boom():
    value = SECRET_MARK
    return 1 / 0
@app.get("/dbg")
def dbg(): return f"debug={app.debug} propagate={app.config['PROPAGATE_EXCEPTIONS']} auto_reload={app.config['TEMPLATES_AUTO_RELOAD']} level={app.logger.getEffectiveLevel()}"
'''
GUARD = '''
import os
from flask import Flask
app = Flask(__name__)
if os.environ.get("APP_ENV") == "production" and app.debug: raise RuntimeError("refusing to start: DEBUG is on in production")
@app.get("/")
def i(): return "up"
'''
PERF = '''
import os, sys, time, statistics, json
from flask import Flask, render_template
app = Flask(__name__, template_folder="tpl")
if sys.argv[1] == "debug": app.debug = True
@app.get("/t")
def t(): return render_template("p.html", items=range(20))
c = app.test_client(); c.get("/t"); L = []
for _ in range(7):
    t0 = time.perf_counter()
    for _ in range(1500): c.get("/t")
    L.append((time.perf_counter() - t0) / 1500 * 1e6)
print("JSON:" + json.dumps({"us": statistics.median(L), "auto_reload": app.config["TEMPLATES_AUTO_RELOAD"], "jinja_auto_reload": app.jinja_env.auto_reload}))
'''
d = mkapp('f186', {'app.py': APP, 'guard.py': GUARD, 'perf.py': PERF, 'tpl/p.html': '<ul>{% for i in items %}<li>{{ i }}</li>{% endfor %}</ul>'})
def probe(s):
    r = s.get('/boom'); body = r[2].decode(errors='replace'); info = s.get('/dbg')[2].decode() if s.get('/dbg')[0] == 200 else ''
    return dict(status=r[0], length=len(body), traceback='Traceback' in body, has_source='1 / 0' in body, has_marker='marker-in-source-code' in body, has_path='File &quot;' in body or 'File "' in body, info=info)
print('== 一:同一个 /boom(视图里 1/0),不同的启动方式下,浏览器收到的 500 响应里有什么')
R['modes'] = {}
cases = (('gunicorn,DEBUG 关(默认)', ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'app:app'], {}),
         ('gunicorn + FLASK_DEBUG=1', ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'app:app'], {'FLASK_DEBUG': '1'}),
         ('flask run(默认,无 --debug)', ['flask', '--app', 'app', 'run', '-p', '{port}'], {}),
         ('flask run --debug', ['flask', '--app', 'app', 'run', '--debug', '-p', '{port}'], {}))
print(f'{"启动方式":<30}{"状态":>5}{"响应字节":>9} {"含 Traceback":<12}{"含源码行 1 / 0":<14}{"含文件路径":<10} app 状态')
for label, cmd, ex in cases:
    with Server(d, cmd, **ex) as s: p = probe(s)
    R['modes'][label] = p; print(f'{label:<30}{p["status"]:>5}{p["length"]:>9} {str(p["traceback"]):<12}{str(p["has_source"]):<14}{str(p["has_path"]):<10} {p["info"]}')
print()
print('== 二:DEBUG 开着对性能有没有影响:渲染一个 20 项的模板,test_client 1500 次一轮,取 7 轮的中位数')
R['perf'] = {}
for mode in ('off', 'debug'):
    rc, o = pyfile(d, 'perf.py', args=[mode]); r = _j.loads([l for l in o.splitlines() if l.startswith('JSON:')][-1][5:]); R['perf'][mode] = r
    print(f'  DEBUG {mode:<6}:每个请求 {r["us"]:.0f} µs(TEMPLATES_AUTO_RELOAD={r["auto_reload"]},jinja_env.auto_reload={r["jinja_auto_reload"]})')
print()
print('== 三:启动守卫:生产环境(APP_ENV=production)如果误开了 DEBUG,拒绝启动')
R['guard'] = {}
for label, ex in (('APP_ENV=production,DEBUG 关', {'APP_ENV': 'production'}), ('APP_ENV=production + FLASK_DEBUG=1', {'APP_ENV': 'production', 'FLASK_DEBUG': '1'})):
    with Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'guard:app'], wait=6, **ex) as s:
        time.sleep(2.0)
        try: out = 'HTTP ' + str(s.get('/', timeout=3)[0])
        except Exception as e: out = '请求失败:' + type(e).__name__
        lg = s.logtext(); key = [l.strip()[-95:] for l in lg.splitlines() if 'refusing to start' in l or 'failed to boot' in l or 'App failed to load' in l or 'Shutting down' in l][:3]
        alive = s.p.poll() is None
        out += f'(master 还在运行:{alive})' + ('' if not key else ';日志:' + ' | '.join(key))
    print(f'  {label:<36}→ {out}'); R['guard'][label] = out
save('f186', R)
