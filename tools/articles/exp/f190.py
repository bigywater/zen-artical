import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import threading, json as _j, tempfile
tee('f190'); R = {}
LIGHT = '''
from flask import Flask
app = Flask(__name__)
@app.get("/")
def i(): return "ok"
'''
HEAVY = '''
import sqlalchemy, flask_sqlalchemy, pydantic, marshmallow, cryptography.fernet, jwt, apispec
from flask import Flask
app = Flask(__name__)
@app.get("/")
def i(): return "ok"
'''
LAZY = '''
from flask import Flask
app = Flask(__name__)
@app.get("/")
def i():
    import sqlalchemy, flask_sqlalchemy, pydantic, marshmallow, cryptography.fernet, jwt, apispec
    return "ok"
'''
SLOW = '''
import time
time.sleep(3)
from flask import Flask
app = Flask(__name__)
@app.get("/")
def i(): return "ok"
'''
d = mkapp('f190', {'light.py': LIGHT, 'heavy.py': HEAVY, 'lazy.py': LAZY, 'slow.py': SLOW})
def tcmd(code, prefix=None, B=False, n=5):
    e = env(d)
    if not B: e.pop('PYTHONDONTWRITEBYTECODE', None)
    if prefix: e['PYTHONPYCACHEPREFIX'] = prefix
    L = []
    for _ in range(n):
        t0 = time.perf_counter(); subprocess.run([str(PY)] + (['-B'] if B else []) + ['-c', code], cwd=d, env=e, capture_output=True); L.append((time.perf_counter() - t0) * 1000)
    return median(L)
print('== 一:导入时间:python -c "import ..." 的墙钟(含解释器启动),各 5 次取中位数')
base = tcmd('pass'); R['base'] = base
R['imp'] = {}
for label, code in (('解释器本身(pass)', 'pass'), ('import flask', 'import flask'), ('import flask + flask_sqlalchemy', 'import flask, flask_sqlalchemy'), ('重一些的一组(sqlalchemy、pydantic、marshmallow、cryptography、jwt、apispec)', 'import flask, flask_sqlalchemy, pydantic, marshmallow, cryptography.fernet, jwt, apispec')):
    v = tcmd(code); R['imp'][label] = v; print(f'  {label:<70}{v:>8.0f} ms')
print()
print('== 二:字节码缓存的作用:同样的 import,有 .pyc 缓存 vs 每次都重新编译(-B 且缓存目录是空的;缓存目录用 PYTHONPYCACHEPREFIX 指定,预热一次)')
code = 'import flask, flask_sqlalchemy, pydantic, marshmallow, cryptography.fernet, jwt, apispec'
pre = tempfile.mkdtemp(prefix='f190pyc'); tcmd(code, prefix=pre, n=1)
warm = tcmd(code, prefix=pre); cold = tcmd(code, prefix=tempfile.mkdtemp(prefix='f190pyc2'), B=True)
print(f'  有缓存(预热过):{warm:.0f} ms | 没有缓存、每次重新编译:{cold:.0f} ms | 比值 {cold / warm:.1f}×'); R['pyc'] = [warm, cold]
shutil.rmtree(pre, ignore_errors=True)
print()
print('== 三:-X importtime 里累计耗时最大的几个顶层包(同一组 import)')
r = subprocess.run([str(PY), '-X', 'importtime', '-c', code], cwd=d, env=env(d), capture_output=True, text=True)
rows = []
for l in r.stderr.splitlines():
    m = re.match(r'import time:\s+(\d+) \|\s+(\d+) \| (\s*)(\S+)', l)
    if m and len(m.group(3)) == 0: rows.append((int(m.group(2)) / 1000, m.group(4)))
rows.sort(reverse=True); R['top'] = rows[:6]
for t, n in rows[:6]: print(f'  {n:<24}{t:>8.1f} ms(累计)')
print()
print('== 四:gunicorn 从启动到第一个 200 响应(-w 3):轻应用、重 import、重 import + --preload、import 放进视图(惰性)')
def first200(app, extra=(), w='3'):
    port = free_port(); t0 = time.perf_counter()
    p = subprocess.Popen([str(BIN / 'gunicorn'), '-w', w, '-b', f'127.0.0.1:{port}', *extra, app], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    t_first = None
    while time.perf_counter() - t0 < 20:
        try:
            r = http(port, 'GET', '/', timeout=2)
            if r[0] == 200: t_first = (time.perf_counter() - t0) * 1000; break
        except Exception: pass
        time.sleep(0.02)
    lat = [http(port, 'GET', '/', timeout=5)[3] for _ in range(12)]
    os.killpg(p.pid, signal.SIGKILL); p.wait(); return t_first, lat
R['boot'] = {}
print(f'{"配置":<34}{"首个 200(ms)":>14}{"之后 12 个请求中最慢(ms)":>26}')
for label, app_, extra in (('轻应用', 'light:app', ()), ('重 import', 'heavy:app', ()), ('重 import + --preload', 'heavy:app', ('--preload',)), ('重 import 放进视图(惰性)', 'lazy:app', ())):
    rs = [first200(app_, extra) for _ in range(3)]; tf = median([x[0] for x in rs]); mx = median([max(x[1]) for x in rs])
    print(f'{label:<34}{tf:>14.0f}{mx:>26.1f}'); R['boot'][label] = [tf, mx]
print()
print('== 五:模块导入时就要 3 秒(例如加载模型):--timeout 2 vs --timeout 30(-w 1),看 worker 能不能起来')
R['slow'] = {}
for to in ('2', '30'):
    port = free_port(); t0 = time.perf_counter(); p = subprocess.Popen([str(BIN / 'gunicorn'), '-w', '1', '--timeout', to, '-b', f'127.0.0.1:{port}', 'slow:app'], cwd=d, env=env(d), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    got = None
    while time.perf_counter() - t0 < 9:
        try:
            r = http(port, 'GET', '/', timeout=1)
            if r[0] == 200: got = (time.perf_counter() - t0) * 1000; break
        except Exception: pass
        time.sleep(0.05)
    
    for sg in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(p.pid, sg)
        except Exception: pass
        time.sleep(0.4)
    out = p.stdout.read(); n_boot = out.count('Booting worker'); n_to = out.count('WORKER TIMEOUT')
    print(f'  --timeout {to:<3}→ ' + (f'{got:.0f} ms 后第一个 200' if got else '9 秒内没有 200') + f';日志里 Booting worker {n_boot} 次、WORKER TIMEOUT {n_to} 次'); R['slow'][to] = [got, n_boot, n_to]
save('f190', R)
