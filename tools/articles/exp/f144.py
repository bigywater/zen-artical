import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f144'); R = {}
import threading, socket, http.client as hc
APP = '''
import time, os
from flask import Flask, request
app = Flask(__name__)
@app.get("/hello")
def hello(): return "hi"
@app.get("/wait")
def wait(): time.sleep(float(request.args.get("s", "0.5"))); return "waited"
'''
d = mkapp('f144', {'app.py': APP})
W = [('sync × 4', ['-w', '4']), ('gthread × 2 个 worker × 8 线程', ['-w', '2', '-k', 'gthread', '--threads', '8']), ('gevent × 2 个 worker', ['-w', '2', '-k', 'gevent', '--worker-connections', '500'])]
def ab(port, path, n, c, keepalive=False):
    cmd = ['ab', '-n', str(n), '-c', str(c)] + (['-k'] if keepalive else []) + [f'http://127.0.0.1:{port}{path}']; out = subprocess.run(cmd, capture_output=True, text=True, timeout=180).stdout
    return float(re.search(r'Requests per second:\s+([\d.]+)', out).group(1)), int(re.search(r'Failed requests:\s+(\d+)', out).group(1)), (re.search(r'Keep-Alive requests:\s+(\d+)', out) or [None, '0'])[1]
def rss_total(port):
    out = subprocess.run(['pgrep', '-f', f'127.0.0.1:{port}'], capture_output=True, text=True).stdout.split(); tot = 0
    for p in out: tot += int(subprocess.run(['ps', '-o', 'rss=', '-p', p], capture_output=True, text=True).stdout.strip() or 0)
    return tot / 1024, len(out)
print('== 一:三种 worker 类型,总共 4 个「槽位」的大致对等配置,三种负载(ApacheBench)')
R['bench'] = {}
for label, args in W:
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}'] + args + ['app:app']) as s:
        time.sleep(1.0); mem, nproc = rss_total(s.port)
        ab(s.port, '/hello', 300, 8); r1 = ab(s.port, '/hello', 4000, 32); r2 = ab(s.port, '/wait?s=0.5', 128, 64); r3 = ab(s.port, '/hello', 4000, 32, keepalive=True)
    print(f'  {label:<32} 空闲内存 {mem:5.0f} MB({nproc} 个进程) | /hello 32 并发 {r1[0]:6.0f} 请求/秒 | /wait 0.5 秒 × 128 个、64 并发:{r2[0]:5.0f} 请求/秒(理想 {64 / 0.5:.0f})| keep-alive 请求数 {r3[2]}'); R['bench'][label] = dict(mem=mem, nproc=nproc, hello=r1[0], wait=r2[0], keepalive=int(r3[2]), failed=r1[1] + r2[1])
print()
print('== 二:慢客户端:一个连接发了一半的请求就不动了,另外的正常请求会不会被拖住(各种 worker 都只有 1 个进程来看最清楚)')
R['slow'] = {}
for label, args in (('sync × 1', ['-w', '1']), ('gthread × 1 个 worker × 8 线程', ['-w', '1', '-k', 'gthread', '--threads', '8']), ('gevent × 1 个 worker', ['-w', '1', '-k', 'gevent'])):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--timeout', '30'] + args + ['app:app']) as s:
        time.sleep(1.0); slow = socket.create_connection(('127.0.0.1', s.port)); slow.sendall(b'GET /hello HTTP/1.1\r\nHost: x\r\nX-Slow: ')   # 请求头没发完
        time.sleep(0.5); c = hc.HTTPConnection('127.0.0.1', s.port, timeout=10); t0 = time.perf_counter()
        try: c.request('GET', '/hello'); r = c.getresponse(); r.read(); out = f'{r.status},用时 {ms(t0):.0f} ms'
        except Exception as e: out = f'{type(e).__name__}(等了 {ms(t0):.0f} ms)'
        slow.close(); c.close(); print(f'  {label:<32} 一个连接卡着没发完请求头时,另一个正常请求 → {out}'); R['slow'][label] = out
save('f144', R)
