"""起真实的 uvicorn / gunicorn 进程测异步行为。端口 9500+。"""
import subprocess, http.client, time, signal, threading, json, os, pathlib
from dj import HERE, env
BIN = HERE.parent / 'djlab' / 'bin'
def serve(d, kind, port, workers=1, log='srv.log', extra=(), **envx):
    lf = open(d / log, 'w')
    if kind == 'uvicorn': cmd = [str(BIN / 'uvicorn'), 'proj.asgi:application', '--host', '127.0.0.1', '--port', str(port), '--workers', str(workers), '--log-level', 'warning', *extra]
    elif kind == 'gunicorn': cmd = [str(BIN / 'gunicorn'), 'proj.wsgi:application', '-b', f'127.0.0.1:{port}', '-w', str(workers), '--timeout', '120', '--log-level', 'warning', *extra]
    elif kind == 'gunicorn-uvicorn': cmd = [str(BIN / 'gunicorn'), 'proj.asgi:application', '-k', 'uvicorn_worker.UvicornWorker', '-b', f'127.0.0.1:{port}', '-w', str(workers), '--log-level', 'warning', *extra]
    elif kind == 'daphne': cmd = [str(BIN / 'daphne'), '-b', '127.0.0.1', '-p', str(port), 'proj.asgi:application', *extra]
    p = subprocess.Popen(cmd, cwd=d, env=env(d, **envx), stdout=lf, stderr=subprocess.STDOUT)
    for _ in range(150):
        try:
            c = http.client.HTTPConnection('127.0.0.1', port, timeout=1); c.request('GET', '/ping/'); c.getresponse().read(); break
        except Exception: time.sleep(0.1)
    time.sleep(0.3); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    time.sleep(0.5)
def get(port, path, timeout=120):
    t0 = time.perf_counter(); c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout); c.request('GET', path); r = c.getresponse(); b = r.read().decode(errors='replace')
    return r.status, b, (time.perf_counter() - t0) * 1000
def conc(port, path, n, timeout=120):
    """n 个并发请求;返回 (总耗时 ms, [(status, body, ms)...])"""
    res = [None] * n
    def w(i):
        try: res[i] = get(port, path, timeout)
        except Exception as e: res[i] = (0, repr(e), 0)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(n)]; t0 = time.perf_counter()
    [t.start() for t in ts]; [t.join() for t in ts]
    return (time.perf_counter() - t0) * 1000, res
