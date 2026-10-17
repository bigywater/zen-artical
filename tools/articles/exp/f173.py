import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f173'); R = {}
import socket, threading, http.client as hc
APP = '''
import os, random, time, threading
from flask import Flask, jsonify, request
app = Flask(__name__)
TOKEN = random.randint(1000, 9999)
FLAG = {"thread_ran": False}
@app.get("/")
def index(): return jsonify(pid=os.getpid(), token=TOKEN)
@app.post("/bg")
def bg():
    def job(): time.sleep(0.2); FLAG["thread_ran"] = True
    threading.Thread(target=job).start(); return "started"
@app.get("/flag")
def flag(): return jsonify(FLAG)
@app.get("/slow")
def slow(): time.sleep(float(request.args.get("s", "5"))); return "done"
'''
d = mkapp('f173', {'app.py': APP})
UW = str(BIN / 'uwsgi')
def start(args):
    port = free_port(); p = subprocess.Popen([UW, '--http', f'127.0.0.1:{port}', '--master', '--die-on-term', '--disable-logging'] + args, cwd=d, env=env(d), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 12:
        if p.poll() is not None: return None, port, p.stdout.read()
        with socket.socket() as s_:
            if s_.connect_ex(('127.0.0.1', port)) == 0: time.sleep(0.5); return p, port, ''
        time.sleep(0.1)
    return p, port, ''
def stop(p):
    if p is None: return
    try: os.killpg(p.pid, signal.SIGTERM)
    except Exception: pass
    try: p.wait(8)
    except Exception: os.killpg(p.pid, signal.SIGKILL)
def req(port, method, path, timeout=10):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=timeout); t0 = time.perf_counter()
    try: c.request(method, path); r = c.getresponse(); b = r.read().decode(); return r.status, b, ms(t0)
    except Exception as e: return type(e).__name__, '', ms(t0)
    finally: c.close()
print('== 一:入口:--module 与 --callable(默认找名叫 application 的变量)')
R['entry'] = {}
for label, args in (('--module app --callable app', ['--module', 'app', '--callable', 'app']), ('--module app(不写 --callable)', ['--module', 'app'])):
    p, port, err = start(args + ['--processes', '1'])
    if p: r = req(port, 'GET', '/'); out = f'{r[0]} {r[1].strip()[:50]}'; stop(p)
    else: out = '启动失败:' + [l.strip() for l in err.splitlines() if 'callable' in l.lower() or 'Error' in l][-1:].__str__()[:140]
    print(f'  {label:<32} → {out}'); R['entry'][label] = out
print()
print('== 二:uWSGI 默认不启用线程支持:视图里自己启动的 threading.Thread 会不会跑?')
R['threads'] = {}
for label, args in (('默认', []), ('--enable-threads', ['--enable-threads'])):
    p, port, err = start(['--module', 'app', '--callable', 'app', '--processes', '1'] + args); req(port, 'POST', '/bg'); time.sleep(1.0); r = req(port, 'GET', '/flag'); stop(p); print(f'  {label:<18} 1 秒后 FLAG = {r[1].strip()}'); R['threads'][label] = r[1].strip()
print()
print('== 三:--lazy-apps:默认在 master 里加载应用再 fork(各 worker 共享导入时算的值);--lazy-apps 让每个 worker 各自加载(8 个并发客户端各请求 40 次)')
R['lazy'] = {}
for label, args in (('默认(master 加载后 fork)', []), ('--lazy-apps', ['--lazy-apps'])):
    p, port, err = start(['--module', 'app', '--callable', 'app', '--processes', '3'] + args); toks = {}; lk = threading.Lock()
    def hit():
        for _ in range(40):
            r = req(port, 'GET', '/'); j = json.loads(r[1])
            with lk: toks[j['pid']] = j['token']
    ths = [threading.Thread(target=hit) for _ in range(8)]; [t.start() for t in ths]; [t.join() for t in ths]
    stop(p); print(f'  {label:<26} 看到 {len(toks)} 个 worker,TOKEN 有 {len(set(toks.values()))} 个不同的值'); R['lazy'][label] = [len(toks), len(set(toks.values()))]
print()
print('== 四:--harakiri 2 秒(单个请求超过就杀掉 worker):慢请求 5 秒')
p, port, err = start(['--module', 'app', '--callable', 'app', '--processes', '1', '--harakiri', '2']); r = req(port, 'GET', '/slow?s=5'); time.sleep(1.0); r2 = req(port, 'GET', '/'); stop(p); print(f'  慢请求 → {r[0]},用时 {r[2]:.0f} ms;之后新请求 → {r2[0]}(worker 被重新拉起)'); R['harakiri'] = [r[0], r[2], r2[0]]
print()
print('== 五:吞吐对比(ApacheBench,32 并发 4000 个请求):uwsgi 4 进程 vs gunicorn sync 4 worker')
def ab(port, n=4000, c=32):
    out = subprocess.run(['ab', '-n', str(n), '-c', str(c), f'http://127.0.0.1:{port}/'], capture_output=True, text=True, timeout=120).stdout; return float(re.search(r'Requests per second:\s+([\d.]+)', out).group(1)), int(re.search(r'Failed requests:\s+(\d+)', out).group(1))
R['bench'] = {}
p, port, err = start(['--module', 'app', '--callable', 'app', '--processes', '4']); ab(port, 300, 8); a = ab(port); stop(p); print(f'  uwsgi --http 4 进程 {a[0]:.0f} 请求/秒(失败 {a[1]})'); R['bench']['uwsgi'] = a[0]
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app']) as s: time.sleep(1.0); ab(s.port, 300, 8); b = ab(s.port)
print(f'  gunicorn sync 4 worker {b[0]:.0f} 请求/秒(失败 {b[1]})'); R['bench']['gunicorn'] = b[0]
save('f173', R)
