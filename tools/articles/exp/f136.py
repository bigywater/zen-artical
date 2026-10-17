import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f136'); R = {}
import threading, http.client as hc
APP = '''
import os, time, threading
from flask import Flask, jsonify, request
app = Flask(__name__)
@app.get("/who")
def who(): time.sleep(float(request.args.get("s", "0"))); return jsonify(pid=os.getpid(), thread=threading.get_ident())
@app.get("/cpu")
def cpu():
    x = 1
    for _ in range(int(request.args["n"])): x = (x * x + 7) % 7919
    return jsonify(pid=os.getpid())
'''
d = mkapp('f136', {'app.py': APP})
def burst(port, path, n):
    res = []; lock = threading.Lock()
    def one():
        c = hc.HTTPConnection('127.0.0.1', port, timeout=60); t0 = time.perf_counter(); c.request('GET', path); r = c.getresponse(); b = r.read(); dt = ms(t0); c.close()
        with lock: res.append((r.status, dt, json.loads(b)))
    ths = [threading.Thread(target=one) for _ in range(n)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; return ms(t0), res
cfgs = [('gunicorn sync,1 个 worker', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app']), ('gunicorn sync,4 个 worker', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app']), ('gunicorn gthread,1 个 worker × 8 线程', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app']), ('flask run(开发服务器,默认多线程)', ['flask', '--app', 'app', 'run', '--no-reload', '--port', '{port}']), ('flask run --without-threads', ['flask', '--app', 'app', 'run', '--no-reload', '--without-threads', '--port', '{port}'])]
print('== 一:8 个并发请求,每个请求在视图里等待 1 秒(模拟等数据库或外部接口):总耗时与并发情况')
R['io'] = {}
for label, cmd in cfgs:
    with Server(d, cmd) as s:
        time.sleep(0.5); total, res = burst(s.port, '/who?s=1', 8); pids = {r[2]['pid'] for r in res}; thr = {r[2]['thread'] for r in res}; ok = all(r[0] == 200 for r in res)
        print(f'  {label:<38} 总耗时 {total / 1000:5.2f} 秒 | 用到 {len(pids)} 个进程、{len(thr)} 个线程 | 全部 200: {ok}'); R['io'][label] = [total, len(pids), len(thr)]
print()
def work(n):
    x = 1
    for _ in range(n): x = (x * x + 7) % 7919
N = 1000000; t0 = time.perf_counter(); work(N); one = time.perf_counter() - t0; N = int(N * 0.3 / one); t0 = time.perf_counter(); work(N); one = time.perf_counter() - t0
print(f'== 二:8 个并发请求,每个请求在视图里做固定量的纯计算(单独跑一次约 {one:.2f} 秒的 CPU 时间)')
R['cpu'] = {}
for label, cmd in cfgs[:4]:
    with Server(d, cmd) as s:
        time.sleep(0.5); total, res = burst(s.port, f'/cpu?n={N}', 8); print(f'  {label:<38} 总耗时 {total / 1000:5.2f} 秒 | 用到 {len({r[2]["pid"] for r in res})} 个进程'); R['cpu'][label] = total; R['cpu_one'] = one
print('  (本机 CPU 核数:', os.cpu_count(), ')')
print()
print('== 三:同一个 worker 里,一个慢请求会不会挡住快请求(sync worker 1 个 vs gthread)')
R['block'] = {}
for label, cmd in (cfgs[0], cfgs[2]):
    with Server(d, cmd) as s:
        time.sleep(0.5); th = threading.Thread(target=lambda: burst(s.port, '/who?s=2', 1)); th.start(); time.sleep(0.3)
        c = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); t0 = time.perf_counter(); c.request('GET', '/who?s=0'); r = c.getresponse(); r.read(); dt = ms(t0); th.join()
        print(f'  {label:<38} 慢请求(2 秒)进行中,一个只要 0 秒的请求用了 {dt:.0f} ms'); R['block'][label] = dt
print()
print('== 四:每个请求的 request 与 g、session 是各线程独立的:同一个 worker 内 8 个线程并发各读自己的参数')
APP2 = APP + '''
from flask import g
@app.get("/ctx")
def ctx():
    g.mine = request.args["n"]; time.sleep(0.3); return g.mine
'''
d2 = mkapp('f136b', {'app.py': APP2})
with Server(d2, cfgs[2][1]) as s:
    res = []
    def one(i): c = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); c.request('GET', f'/ctx?n=req{i}'); res.append((i, c.getresponse().read().decode())); c.close()
    ths = [threading.Thread(target=one, args=(i,)) for i in range(8)]; [t.start() for t in ths]; [t.join() for t in ths]
    wrong = [i for i, b in res if b != f'req{i}']; print(f'  8 个并发请求在同一个进程的 8 个线程里,各自读回自己写进 g 的值,读错的有 {len(wrong)} 个'); R['ctx_wrong'] = len(wrong)
save('f136', R)
