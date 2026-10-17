import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import threading
tee('f180'); R = {}
APP = '''
import os, time, atexit
from flask import Flask
app = Flask(__name__)
atexit.register(lambda: open("atexit.log", "a").write(f"atexit in pid {os.getpid()}\\n"))
@app.get("/slow")
def slow(): time.sleep(3); return f"done by {os.getpid()}"
@app.get("/pid")
def pid(): return str(os.getpid())
'''
CONF = '''
import os
def worker_exit(server, worker): open("hook.log", "a").write(f"worker_exit hook pid {worker.pid}\\n")
'''
d = mkapp('f180', {'app.py': APP, 'gunicorn.conf.py': CONF})
def clr():
    for f in ('atexit.log', 'hook.log'): (d / f).unlink(missing_ok=True)
def rd(f): p = d / f; return p.read_text().strip().splitlines() if p.exists() else []
def inflight(s, path='/slow'):
    box = {}
    def run():
        t0 = time.perf_counter()
        try: r = s.get(path, timeout=15); box['r'] = f'{r[0]} ' + (r[2].decode()[:12] if r[0] == 200 else f'(错误页 {len(r[2])} 字节)')
        except Exception as e: box['r'] = f'{type(e).__name__}'
        box['t'] = time.perf_counter() - t0
    th = threading.Thread(target=run); th.start(); return th, box
def run_case(sig, extra=()):
    clr()
    s = Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', *extra, 'app:app'])
    th, box = inflight(s); time.sleep(0.6); t0 = time.perf_counter(); ex = {}
    threading.Thread(target=lambda: (s.p.wait(), ex.setdefault('t', time.perf_counter() - t0)), daemon=True).start(); os.kill(s.p.pid, sig)
    # 关闭过程中的新连接
    time.sleep(0.5); new = 'ok'
    try: r = s.get('/pid', timeout=2); new = f'{r[0]}'
    except Exception as e: new = type(e).__name__
    th.join(); time.sleep(1.5); texit = ex.get('t'); log = [l.strip()[:110] for l in s.logtext().splitlines() if any(k in l for k in ('Handling signal', 'Worker exiting', 'Shutting down', 'killed', 'SIGKILL', 'Error', 'Traceback', 'KeyboardInterrupt', 'Worker (pid', 'Booting'))]
    s.stop(); return dict(client=box['r'], client_s=round(box['t'], 2), new=new, master_exit_s=None if texit is None else round(texit, 2), log=log, atexit=rd('atexit.log'), hook=rd('hook.log'))
print('== 一:SIGTERM(优雅关闭):3 秒的请求正在处理时给 master 发 SIGTERM,默认 graceful_timeout=30 秒')
r = run_case(signal.SIGTERM); R['term'] = r
print(f'  那个进行中的请求 → {r["client"]},耗时 {r["client_s"]} s | 关闭开始 0.5 秒后的新连接 → {r["new"]} | master 退出用了 {r["master_exit_s"]} s')
print('  日志:'); [print('    ' + l) for l in r['log']]; print('  worker 里 atexit 是否运行:', r['atexit'], '| worker_exit 钩子:', r['hook'])
print()
print('== 二:同样的请求,不同的信号:SIGTERM / SIGINT / SIGQUIT / SIGKILL(master)')
print(f'{"信号":<10}{"进行中的请求":<26}{"master 退出(s)":>14}  {"atexit":<8}{"worker_exit 钩子"}')
R['sigs'] = {}
for name, sig in (('SIGTERM', signal.SIGTERM), ('SIGINT', signal.SIGINT), ('SIGQUIT', signal.SIGQUIT), ('SIGKILL', signal.SIGKILL)):
    r = run_case(sig); R['sigs'][name] = r
    print(f'{name:<10}{r["client"] + " (" + str(r["client_s"]) + " s)":<26}{str(r["master_exit_s"]):>14}  {len(r["atexit"]):<8}{len(r["hook"])}')
print()
print('== 三:graceful_timeout 比请求时间短:--graceful-timeout 1,3 秒的请求在 SIGTERM 之后')
r = run_case(signal.SIGTERM, ['--graceful-timeout', '1']); R['gt1'] = r
print(f'  进行中的请求 → {r["client"]},{r["client_s"]} s 后;master 退出 {r["master_exit_s"]} s')
print('  日志:'); [print('    ' + l) for l in r['log']]; print('  worker 里 atexit:', len(r['atexit']), '次 | worker_exit 钩子:', len(r['hook']), '次(日志里没有 Worker exiting)')
print()
print('== 四:SIGHUP 重载:一个 3 秒的请求在 HUP 时进行中,同时每 50 ms 发一次 /pid;统计失败数与 worker 更换')
clr()
with Server(d, ['gunicorn', '-w', '2', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    time.sleep(1.5); clr()
    pids0 = sorted(int(x) for x in subprocess.run(['pgrep', '-P', str(s.p.pid)], capture_output=True, text=True).stdout.split())
    th, box = inflight(s); time.sleep(0.4)
    res = []; stop = threading.Event()
    def spam():
        while not stop.is_set():
            try: r_ = s.get('/pid', timeout=3); res.append((time.perf_counter(), r_[0], r_[2].decode()))
            except Exception as e: res.append((time.perf_counter(), type(e).__name__, ''))
            time.sleep(0.05)
    sp = threading.Thread(target=spam); sp.start(); time.sleep(0.5); os.kill(s.p.pid, signal.SIGHUP); th.join(); time.sleep(1.0); stop.set(); sp.join()
    pids1 = sorted(int(x) for x in subprocess.run(['pgrep', '-P', str(s.p.pid)], capture_output=True, text=True).stdout.split())
    seen = sorted(set(x[2] for x in res if x[2])); bad = [x for x in res if x[1] != 200]
    print(f'  HUP 之前的 worker pid:{len(pids0)} 个;HUP 之后:{len(pids1)} 个,与之前重叠 {len(set(pids0) & set(pids1))} 个(全部更换)')
    print(f'  进行中的 3 秒请求 → {box["r"]},{box["t"]:.1f} s;期间 {len(res)} 次 /pid 请求,失败 {len(bad)} 次;请求中见过的不同 worker pid 数 {len(seen)}')
    print('  worker_exit 钩子:', len(rd('hook.log')), '次,atexit:', len(rd('atexit.log')), '次')
    R['hup'] = dict(old=len(pids0), new=len(pids1), overlap=len(set(pids0) & set(pids1)), client=box['r'], t=round(box['t'], 1), n=len(res), bad=len(bad), seen=len(seen), hook=len(rd('hook.log')), atexit=len(rd('atexit.log')))
save('f180', R)
