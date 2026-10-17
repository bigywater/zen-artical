import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f166'); R = {}
import threading, http.client as hc, statistics
APP = '''
import time, os
time.sleep(float(os.environ.get("IMPORT_DELAY", "0")))     # 模拟导入重型依赖
from flask import Flask, request
app = Flask(__name__)
@app.get("/fast")
def fast(): return "ok"
@app.get("/slow")
def slow(): time.sleep(float(request.args.get("s", "5"))); return "slow done"
'''
d = mkapp('f166', {'app.py': APP})
def call(port, path, timeout=30):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=timeout); t0 = time.perf_counter()
    try: c.request('GET', path); r = c.getresponse(); r.read(); return r.status, ms(t0)
    except Exception as e: return type(e).__name__, ms(t0)
    finally: c.close()
def scenario(extra, import_delay, label, duration=9, workers=2):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', str(workers), '--timeout', '2'] + extra + ['app:app'], IMPORT_DELAY=str(import_delay), wait=30) as s:
        time.sleep(import_delay + 1.0); res = []; stop = threading.Event()
        def steady():
            while not stop.is_set(): t0 = time.time(); res.append((t0, *call(s.port, '/fast'))); time.sleep(0.05)
        ths = [threading.Thread(target=steady) for _ in range(2)]; [t.start() for t in ths]; time.sleep(1.0)
        slow = []; sl = threading.Thread(target=lambda: slow.append(call(s.port, '/slow?s=6'))); sl.start(); sl.join(); time.sleep(duration - 3); stop.set(); [t.join() for t in ths]
        lat = [x[2] for x in res if x[1] == 200]; bad = [x for x in res if x[1] != 200]; mx = max(lat); p99 = sorted(lat)[int(len(lat) * 0.99)]; slow_res = slow[0]
        log = s.logtext(); n_to = log.count('WORKER TIMEOUT'); n_boot = log.count('Booting worker')
        print(f'  {label:<36} /fast {len(res)} 个请求:失败 {len(bad)},p99 {p99:.0f} ms,最大 {mx:.0f} ms | 慢请求:{slow_res[0]} 用 {slow_res[1]:.0f} ms | WORKER TIMEOUT {n_to} 次,worker 启动 {n_boot} 次'); R[label] = dict(n=len(res), bad=len(bad), p99=p99, mx=mx, slow=slow_res, to=n_to, boots=n_boot)
print('== 一:2 个 sync worker,--timeout 2:一个 6 秒的慢请求把其中一个 worker 拖到被杀;期间两个客户端持续请求 /fast(每 50 ms 一次)。应用导入要 1.5 秒(模拟重型依赖)')
scenario([], 1.5, '2 个 worker,不加 --preload', workers=2)
scenario(['--preload'], 1.5, '2 个 worker,--preload', workers=2)
print()
print('== 二:只有 1 个 worker 时,worker 被杀与重启期间的请求(同样的场景)')
scenario([], 1.5, '1 个 worker,不加 --preload(导入 1.5 秒)', workers=1)
scenario(['--preload'], 1.5, '1 个 worker,--preload', workers=1)
scenario([], 0, '1 个 worker,导入很快', workers=1)
print()
print('== 三:--timeout 0 关闭超时:慢请求不会被杀')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '2', '--timeout', '0', 'app:app']) as s:
    time.sleep(1.0); r = call(s.port, '/slow?s=4'); print(f'  --timeout 0,慢请求 4 秒:{r[0]},用 {r[1]:.0f} ms,日志里 WORKER TIMEOUT {s.logtext().count("WORKER TIMEOUT")} 次'); R['t0'] = [r[0], r[1]]
save('f166', R)
