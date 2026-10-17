import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f142'); R = {}
import threading, http.client as hc
APP = '''
import os, time, threading
from flask import Flask, g, request, jsonify, current_app
app = Flask(__name__)
@app.get("/sleep")
def sleeper():
    g.mine = request.args["n"]; time.sleep(1); return jsonify(read_back=g.mine, ident=threading.get_ident(), pid=os.getpid())
@app.get("/cpu")
def cpu():
    x = 1
    for _ in range(int(request.args["n"])): x = (x * x + 7) % 7919
    return "done"
@app.get("/fast")
def fast(): return "fast"
'''
d = mkapp('f142', {'app.py': APP})
def burst(port, paths):
    res = []
    def one(p):
        c = hc.HTTPConnection('127.0.0.1', port, timeout=60); t0 = time.perf_counter(); c.request('GET', p); r = c.getresponse(); b = r.read(); res.append((p, r.status, ms(t0), b)); c.close()
    ths = [threading.Thread(target=one, args=(p,)) for p in paths]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; return ms(t0), res
print('== 一:gunicorn 的 gevent worker:1 个进程同时处理 100 个各睡 1 秒的请求;每个请求的 g 是否串')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gevent', '-w', '1', '--worker-connections', '200', 'app:app']) as s:
    time.sleep(1); total, res = burst(s.port, [f'/sleep?n=req{i}' for i in range(100)])
    bodies = [(p, json.loads(b)) for p, st, t, b in res]; wrong = [p for p, j in bodies if p.split('=')[1] != j['read_back']]; idents = {j['ident'] for _, j in bodies}; pids = {j['pid'] for _, j in bodies}
    print(f'  100 个并发请求总耗时 {total / 1000:.2f} 秒 | 进程数 {len(pids)} | threading.get_ident() 有 {len(idents)} 个不同的值(每个请求一个 greenlet)| g 读回别人的值的有 {len(wrong)} 个'); R['gevent'] = [total, len(pids), len(idents), len(wrong)]
print()
print('== 二:同样的 100 个请求,gunicorn gthread(1 个 worker × 8 线程)与 sync(1 个 worker)对比')
R['cmp'] = {}
for label, cmd, n in (('gthread 1×8 线程', ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '8', '-w', '1', 'app:app'], 100), ('sync 1 个 worker(只测 8 个)', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app'], 8)):
    with Server(d, cmd) as s:
        time.sleep(0.8); total, res = burst(s.port, [f'/sleep?n=req{i}' for i in range(n)]); print(f'  {label:<26} {n} 个请求总耗时 {total / 1000:.2f} 秒'); R['cmp'][label] = [n, total]
print()
print('== 三:greenlet 是协作式的:一个纯计算的请求会卡住同一个 worker 里的所有 greenlet')
def work(n):
    x = 1
    for _ in range(n): x = (x * x + 7) % 7919
N = 1000000; t0 = time.perf_counter(); work(N); one = time.perf_counter() - t0; N = int(N * 0.8 / one)
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gevent', '-w', '1', 'app:app']) as s:
    time.sleep(1); th = threading.Thread(target=lambda: burst(s.port, [f'/cpu?n={N}'])); th.start(); time.sleep(0.2)
    c = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); t0 = time.perf_counter(); c.request('GET', '/fast'); c.getresponse().read(); dt = ms(t0); th.join()
    print(f'  一个约 0.8 秒的纯计算请求进行中,一个 /fast 请求用了 {dt:.0f} ms(gevent 下没有抢占,要等计算让出)'); R['cpu_block'] = dt
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '8', '-w', '1', 'app:app']) as s:
    time.sleep(0.8); th = threading.Thread(target=lambda: burst(s.port, [f'/cpu?n={N}'])); th.start(); time.sleep(0.2)
    c = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); t0 = time.perf_counter(); c.request('GET', '/fast'); c.getresponse().read(); dt2 = ms(t0); th.join()
    print(f'  gthread 同样的场景:/fast 用了 {dt2:.0f} ms(线程由 GIL 轮流调度,有切换)'); R['cpu_block_gthread'] = dt2
print()
print('== 四:threading.local 与 greenlet:没有 monkey patch 的 threading.local 会被同一线程里的 greenlet 共享')
CODE = """
import threading, gevent
tl = threading.local()
def worker(name, out):
    tl.value = name; gevent.sleep(0.1); out[name] = getattr(tl, 'value', None)
def run():
    out = {}; gs = [gevent.spawn(worker, n, out) for n in ('A', 'B', 'C')]; gevent.joinall(gs); return out
print('未 patch:', run())
from gevent import monkey; monkey.patch_all()
tl2 = threading.local()
def worker2(name, out):
    tl2.value = name; gevent.sleep(0.1); out[name] = getattr(tl2, 'value', None)
out = {}; gs = [gevent.spawn(worker2, n, out) for n in ('A', 'B', 'C')]; gevent.joinall(gs); print('patch_all 之后(新建的 threading.local):', out)
import contextvars
cv = contextvars.ContextVar('cv', default=None)
def worker3(name, out): cv.set(name); gevent.sleep(0.1); out[name] = cv.get()
out = {}; gs = [gevent.spawn(worker3, n, out) for n in ('A', 'B', 'C')]; gevent.joinall(gs); print('contextvars(不需要 patch):', out)
"""
dd = mkapp('f142b', {'x.py': 'pass'}); rc, out = py(dd, CODE); print('\n'.join('  ' + l for l in out.splitlines())); R['local'] = out.splitlines()
save('f142', R)
