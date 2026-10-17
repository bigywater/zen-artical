import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import threading, json as _j
tee('f179'); R = {}
APP = '''
import os, socket, time
from flask import Flask, jsonify
app = Flask(__name__)
DEP = int(os.environ["DEP_PORT"]); TMO = os.environ.get("DEP_TIMEOUT", "none")
@app.get("/healthz")
def healthz(): return "ok"
@app.get("/readyz")
def readyz():
    t0 = time.perf_counter(); checks = {}
    try:
        s = socket.create_connection(("127.0.0.1", DEP), timeout=None if TMO == "none" else float(TMO))
        s.settimeout(None if TMO == "none" else float(TMO)); s.sendall(b"PING\\n"); got = s.recv(16); s.close()
        checks["dep"] = "ok" if got.startswith(b"PONG") else "bad reply"
    except Exception as e: checks["dep"] = type(e).__name__
    ok = all(v == "ok" for v in checks.values())
    return jsonify(status="ready" if ok else "not ready", checks=checks), (200 if ok else 503)
@app.get("/slow")
def slow(): time.sleep(3); return "slow done"
@app.get("/")
def index(): return "index"
'''
DEP = '''
import socket, sys, time, threading
mode, port = sys.argv[1], int(sys.argv[2])
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", port)); srv.listen(32)
def h(c):
    if mode == "ok":
        c.recv(16); c.sendall(b"PONG\\n"); c.close()
    else: time.sleep(60)
while True:
    c, _ = srv.accept(); threading.Thread(target=h, args=(c,), daemon=True).start()
'''
LOGGER = '''
from gunicorn.glogging import Logger
class QuietHealth(Logger):
    def access(self, resp, req, environ, request_time):
        if req.path in ("/healthz", "/readyz"): return
        super().access(resp, req, environ, request_time)
'''
d = mkapp('f179', {'app.py': APP, 'dep.py': DEP, 'qlog.py': LOGGER})
deps = []
def dep(mode):
    port = free_port(); p = subprocess.Popen([str(PY), 'dep.py', mode, str(port)], cwd=d, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); deps.append(p); time.sleep(0.4); return p, port
def kill(p):
    try: os.killpg(p.pid, signal.SIGKILL)
    except Exception: pass
    p.wait()
def fmt(r): return f'{r[0]} {r[2].decode().strip()[:80]} ({r[3]:.0f} ms)'
print('== 一:存活(/healthz)与就绪(/readyz)是两件事:依赖(一个 TCP 服务)正常 → 依赖被杀掉 → 重新起来')
p1, dport = dep('ok'); R['probe'] = {}
with Server(d, ['gunicorn', '-w', '2', '-b', '127.0.0.1:{port}', 'app:app'], DEP_PORT=str(dport), DEP_TIMEOUT='1') as s:
    r = [('依赖正常', s.get('/healthz'), s.get('/readyz'))]
    kill(p1); r.append(('依赖被杀掉', s.get('/healthz'), s.get('/readyz')))
    p1, _ = None, None
    p2 = subprocess.Popen([str(PY), 'dep.py', 'ok', str(dport)], cwd=d, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); deps.append(p2); time.sleep(0.5)
    r.append(('依赖重新起来', s.get('/healthz'), s.get('/readyz')))
    for name, a, b in r: print(f'  {name:<10} /healthz → {fmt(a)}   /readyz → {fmt(b)}'); R['probe'][name] = [[a[0], a[2].decode().strip()], [b[0], b[2].decode().strip()]]
    print('  依赖被杀掉时,进程本身没问题(不该被重启),只是暂时不该接流量')
    rh = s.req('HEAD', '/healthz'); print(f'  HEAD /healthz → {rh[0]},正文 {len(rh[2])} 字节,Content-Length {dict(rh[1]).get("Content-Length")}')
    R['head'] = [rh[0], len(rh[2]), dict(rh[1]).get('Content-Length')]
    kill(p2)
print()
print('== 二:健康检查走的是同一批 worker:1 个 sync worker 正在处理 3 秒的 /slow 请求时,/healthz 要等多久?')
pq, dport = dep('ok'); R['busy'] = {}
cfgs = [('sync ×1', ['-w', '1']), ('sync ×2', ['-w', '2']), ('gthread 1 进程 ×4 线程', ['-w', '1', '--threads', '4'])]
for name, a in cfgs:
    with Server(d, ['gunicorn'] + a + ['-b', '127.0.0.1:{port}', 'app:app'], DEP_PORT=str(dport)) as s:
        th = threading.Thread(target=lambda: s.get('/slow', timeout=10)); th.start(); time.sleep(0.4)
        r = s.get('/healthz', timeout=10); th.join(); print(f'  {name:<22} /slow 处理中时 /healthz → {r[0]},耗时 {r[3]:.0f} ms'); R['busy'][name] = [r[0], round(r[3])]
kill(pq)
print()
print('== 三:就绪检查里依赖卡住(接受连接但不回复):不设超时 vs 设 0.5 秒超时(探针客户端自己 8 秒放弃)')
ph, dport = dep('hang'); R['hang'] = {}
for name, tmo in (('依赖调用不设超时', 'none'), ('依赖调用超时 0.5 秒', '0.5')):
    with Server(d, ['gunicorn', '-w', '2', '-b', '127.0.0.1:{port}', 'app:app'], DEP_PORT=str(dport), DEP_TIMEOUT=tmo) as s:
        try: r = s.get('/readyz', timeout=8); out = f'{r[0]} {r[2].decode().strip()[:60]} ({r[3]:.0f} ms)'; R['hang'][name] = [r[0], round(r[3])]
        except Exception as e: out = f'探针客户端 8 秒后放弃:{type(e).__name__}'; R['hang'][name] = [None, type(e).__name__]
        print(f'  {name:<20} → {out}')
        if tmo == 'none':
            t0 = time.time(); r2 = None
            try: r2 = s.get('/healthz', timeout=3); print(f'  (同时)/healthz → {r2[0]} ({r2[3]:.0f} ms)')
            except Exception as e: print(f'  (同时)/healthz → {type(e).__name__}')
kill(ph)
print()
print('== 四:探针很频繁,访问日志会被刷满:20 次 /healthz 与 /readyz 探测 + 2 次真实请求,默认日志 vs 自定义 logger_class 跳过探针')
pq, dport = dep('ok'); R['log'] = {}
for name, extra in (('默认 accesslog', []), ('logger-class qlog.QuietHealth', ['--logger-class', 'qlog.QuietHealth'])):
    with Server(d, ['gunicorn', '-w', '1', '--access-logfile', '-', '-b', '127.0.0.1:{port}'] + extra + ['app:app'], DEP_PORT=str(dport)) as s:
        for i in range(10): s.get('/healthz'); s.get('/readyz')
        s.get('/'); s.get('/')
        time.sleep(0.3); n = sum(1 for l in s.logtext().splitlines() if '"GET ' in l); hz = sum(1 for l in s.logtext().splitlines() if '"GET /healthz' in l or '"GET /readyz' in l)
    print(f'  {name:<32} 访问日志共 {n} 行,其中探针 {hz} 行'); R['log'][name] = [n, hz]
kill(pq); [kill(x) for x in deps if x.poll() is None]
save('f179', R)
