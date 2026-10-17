import sys, os, time, json, re, subprocess, signal, threading, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
import asrv
tee('d130'); R = {}
urls = '''
import os, time
from django.urls import path
from django.http import HttpResponse
def ping(r): return HttpResponse('ok')
def work(r):
    time.sleep(float(r.GET.get('s', '0.3'))); return HttpResponse(str(os.getpid()))
urlpatterns = [path('ping/', ping), path('work/', work)]
'''
d = proj('d130', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
GUN = str(asrv.BIN / 'gunicorn')
def start(port, *args, log='g.log'):
    p = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{port}', '--log-level', 'info', *args], cwd=d, env=env(d), stdout=open(d / log, 'w'), stderr=subprocess.STDOUT)
    for _ in range(150):
        try: c = http.client.HTTPConnection('127.0.0.1', port, timeout=1); c.request('GET', '/ping/'); c.getresponse().read(); break
        except Exception: time.sleep(0.1)
    time.sleep(0.3); return p
def kill(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(15)
    except Exception: p.kill()
    time.sleep(0.4)
print('== 一:gunicorn 的默认值(当前安装版本的 Config())')
o = subprocess.run([PY, '-c', "import gunicorn; from gunicorn.config import Config; c = Config(); print('  gunicorn', gunicorn.__version__); print('  workers =', c.workers, '| worker_class =', c.worker_class_str, '| threads =', c.threads, '| timeout =', c.timeout, 's | graceful_timeout =', c.graceful_timeout, 's | keepalive =', c.keepalive, 's | max_requests =', c.max_requests)"], capture_output=True, text=True).stdout.rstrip()
print(o); R['defaults'] = o
print()
print(f'== 二:20 个并发请求,每个请求的视图里 time.sleep(0.3):不同 worker 配置的总耗时(本机 {os.cpu_count()} 个 CPU 核)')
R['conc'] = {}
for label, args in (('sync × 1(默认)', ['-w', '1']), ('sync × 4', ['-w', '4']), ('gthread × 1 进程 × 8 线程', ['-w', '1', '-k', 'gthread', '--threads', '8']), ('gthread × 2 进程 × 8 线程', ['-w', '2', '-k', 'gthread', '--threads', '8'])):
    p = start(9550, *args)
    try:
        asrv.get(9550, '/work/?s=0'); tot, res = asrv.conc(9550, '/work/?s=0.3', 20); pids = {r[1] for r in res}
    finally: kill(p)
    R['conc'][label] = tot; print(f'  {label:<26} 总耗时 {tot:6.0f} ms   用到的 worker 进程数 {len(pids)}   全部 200: {all(r[0] == 200 for r in res)}')
print()
print('== 三:--timeout:视图跑得比 timeout 久,worker 被杀掉(--timeout 2,视图 sleep 5 s)')
p = start(9551, '-w', '1', '--timeout', '2')
try:
    t0 = time.perf_counter()
    try: st, b, ms = asrv.get(9551, '/work/?s=5', timeout=30); res = f'状态码 {st}'
    except Exception as e: res = type(e).__name__
    el = (time.perf_counter() - t0) * 1000
    print(f'  客户端:{res},用时 {el:.0f} ms'); R['timeout_client'] = dict(res=res, ms=el)
    st, b, ms = asrv.get(9551, '/work/?s=0'); print('  之后的下一个请求:状态码', st, '(新 worker 已经接手)')
finally: kill(p)
lg = [l.split('] ', 1)[-1] for l in open(d / 'g.log').read().splitlines() if 'TIMEOUT' in l or 'Booting worker' in l or 'signal' in l.lower() or 'exited' in l.lower()]
print('  gunicorn 日志里相关的行:'); [print('   ', l[:110]) for l in lg[:8]]; R['timeout_log'] = lg[:8]
print()
print('== 四:--max-requests 5:worker 处理 5 个请求后被回收(连续 13 个串行请求,看 worker pid 的变化)')
p = start(9552, '-w', '1', '--max-requests', '5', '--max-requests-jitter', '0')
try:
    pids = [asrv.get(9552, '/work/?s=0')[1] for _ in range(13)]
finally: kill(p)
seq = []; [seq.append(x) for x in pids if not seq or seq[-1] != x]
print('  13 个请求的 pid 序列(相邻去重):', seq, '→ 共', len(set(pids)), '个不同的 worker 进程'); R['maxreq'] = dict(pids=pids, distinct=len(set(pids)))
print()
print('== 五:优雅停止:视图还在处理一个 2 s 的请求时给 gunicorn 主进程发 SIGTERM')
p = start(9553, '-w', '1', '--graceful-timeout', '10')
out_ = {}
def req():
    try: out_['r'] = asrv.get(9553, '/work/?s=2', timeout=30)
    except Exception as e: out_['r'] = repr(e)
th = threading.Thread(target=req); th.start(); time.sleep(0.6)
t0 = time.perf_counter(); p.send_signal(signal.SIGTERM); th.join(); p.wait(15); el = (time.perf_counter() - t0) * 1000
r = out_['r']; print('  在途请求(2 s)的结果: 状态码', r[0] if isinstance(r, tuple) else r, f'| 从 SIGTERM 到主进程退出 {el:.0f} ms'); R['graceful'] = dict(status=r[0] if isinstance(r, tuple) else str(r), ms=el)
try:
    asrv.get(9553, '/ping/', timeout=2); print('  退出之后还能连上吗: 能')
except Exception as e: print('  退出之后还能连上吗:', type(e).__name__)
save('d130', R)
