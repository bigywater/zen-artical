import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f171'); R = {}
import threading, http.client as hc
APP = '''
import time, os
from flask import Flask, request
app = Flask(__name__)
@app.get("/hello")
def hello(): return "hi"
@app.get("/wait")
def wait(): time.sleep(float(request.args.get("s", "0.5"))); return "ok"
'''
d = mkapp('f171', {'app.py': APP})
def ab(port, path, n, c):
    out = subprocess.run(['ab', '-n', str(n), '-c', str(c), f'http://127.0.0.1:{port}{path}'], capture_output=True, text=True, timeout=300).stdout
    return float(re.search(r'Requests per second:\s+([\d.]+)', out).group(1)), int(re.search(r'\s+99%\s+(\d+)', out).group(1)), int(re.search(r'Failed requests:\s+(\d+)', out).group(1))
stacks = [('flask run(开发服务器,默认多线程)', ['flask', '--app', 'app', 'run', '--no-reload', '--port', '{port}']), ('flask run --without-threads', ['flask', '--app', 'app', 'run', '--no-reload', '--without-threads', '--port', '{port}']), ('gunicorn sync × 4', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app']), ('gunicorn gthread 2 × 8', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '2', '-k', 'gthread', '--threads', '8', 'app:app'])]
print('== 一:启动时的警告:开发服务器自己说它不适合生产')
with Server(d, stacks[0][1]) as s:
    time.sleep(0.5); log = s.logtext(); lines = [l.strip() for l in log.splitlines() if 'WARNING' in l or 'development' in l.lower()]; print('  ', lines[:3]); R['warn'] = lines[:3]
print()
print('== 二:吞吐与并发(ApacheBench,32 并发;/hello 轻量接口 4000 个请求;/wait 每个等 0.5 秒 64 个请求)')
R['bench'] = {}
for label, cmd in stacks:
    with Server(d, cmd) as s:
        time.sleep(1.0); ab(s.port, '/hello', 200, 8); a = ab(s.port, '/hello', 4000, 32); t0 = time.perf_counter(); b = ab(s.port, '/wait?s=0.5', 64, 32); dt = time.perf_counter() - t0
    print(f'  {label:<34} /hello {a[0]:6.0f} 请求/秒(p99 {a[1]} ms,失败 {a[2]}) | /wait 64 个请求总耗时 {dt:5.1f} 秒'); R['bench'][label] = [a[0], a[1], a[2], dt]
print()
print('== 三:自动重载(--debug 时 reloader 的行为):改动代码文件之后,服务器自己重启')
with Server(d, ['flask', '--app', 'app', 'run', '--debug', '--port', '{port}']) as s:
    time.sleep(1.5); r1 = s.get('/hello')[2].decode()
    (d / 'app.py').write_text((d / 'app.py').read_text().replace('return "hi"', 'return "hi v2"')); t0 = time.time(); r2 = None
    while time.time() - t0 < 10:
        try:
            r2 = s.get('/hello')[2].decode()
            if r2 == 'hi v2': break
        except Exception: pass
        time.sleep(0.2)
    print(f'  改文件之前 → {r1!r};改文件后 {time.time() - t0:.1f} 秒内请求得到 → {r2!r}(重载器重启了进程)'); R['reload'] = [r1, r2, time.time() - t0]
    (d / 'app.py').write_text((d / 'app.py').read_text().replace('hi v2', 'hi'))
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app']) as s:
    time.sleep(1.0); r1 = s.get('/hello')[2].decode(); (d / 'app.py').write_text((d / 'app.py').read_text().replace('return "hi"', 'return "hi v3"')); time.sleep(2.0); r2 = s.get('/hello')[2].decode(); print(f'  gunicorn(没有 --reload):改文件之前 {r1!r},2 秒之后 {r2!r}(不会自动重载)'); R['gunicorn_reload'] = [r1, r2]
    (d / 'app.py').write_text((d / 'app.py').read_text().replace('hi v3', 'hi'))
print()
print('== 四:开发服务器的进程模型:一个进程,每个请求一个线程;gunicorn 是一个 master 加多个 worker 进程')
for label, cmd in (stacks[0], stacks[2]):
    with Server(d, cmd) as s:
        time.sleep(1.0); n = len(subprocess.run(['pgrep', '-f', '--', f'127.0.0.1:{s.port}' if 'gunicorn' in label else f'port {s.port}'], capture_output=True, text=True).stdout.split()); print(f'  {label:<34} 相关进程数(含 master / 父进程){n}'); R.setdefault('procs', {})[label] = n
save('f171', R)
