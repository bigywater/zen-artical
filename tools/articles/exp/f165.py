import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f165'); R = {}
APP = '''
import time
from flask import Flask, request
app = Flask(__name__)
@app.get("/cpu")
def cpu():
    x = 1
    for _ in range(int(request.args["n"])): x = (x * x + 7) % 7919
    return "ok"
@app.get("/mixed")
def mixed():
    time.sleep(0.02)
    x = 1
    for _ in range(int(request.args["n"])): x = (x * x + 7) % 7919
    return "ok"
'''
d = mkapp('f165', {'app.py': APP})
def work(n):
    x = 1
    for _ in range(n): x = (x * x + 7) % 7919
N = 100000; t0 = time.perf_counter(); work(N); one = time.perf_counter() - t0; N = int(N * 0.010 / one)   # 约 10 ms 的 CPU
t0 = time.perf_counter(); work(N); one = time.perf_counter() - t0
def ab(port, path, n, c):
    out = subprocess.run(['ab', '-n', str(n), '-c', str(c), f'http://127.0.0.1:{port}{path}'], capture_output=True, text=True, timeout=300).stdout
    return float(re.search(r'Requests per second:\s+([\d.]+)', out).group(1)), float(re.search(r'Time per request:\s+([\d.]+) \[ms\] \(mean\)', out).group(1)), int(re.search(r'\s+99%\s+(\d+)', out).group(1)), int(re.search(r'Failed requests:\s+(\d+)', out).group(1))
def rss(port):
    pids = subprocess.run(['pgrep', '-f', f'127.0.0.1:{port}'], capture_output=True, text=True).stdout.split(); return sum(int(subprocess.run(['ps', '-o', 'rss=', '-p', p], capture_output=True, text=True).stdout.strip() or 0) for p in pids) / 1024
print(f'== 本机 {os.cpu_count()} 核;/cpu 每个请求约 {one * 1000:.0f} ms 纯 CPU;/mixed 每个请求先等 20 ms 再算同样的 CPU;ab 64 并发(压测工具同机,只看相对关系)')
print(f'  {"worker 数":>9} {"/cpu 请求/秒":>13} {"p99 ms":>7} | {"/mixed 请求/秒":>14} {"p99 ms":>7} | {"空闲内存 MB":>10}')
R['rows'] = {}
for w in (1, 2, 4, 8, 10, 16, 32):
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', str(w), 'app:app']) as s:
        time.sleep(1.0 + w * 0.05); mem = rss(s.port); ab(s.port, f'/cpu?n={N}', 100, 16); a = ab(s.port, f'/cpu?n={N}', 2000, 64); b = ab(s.port, f'/mixed?n={N}', 2000, 64)
    print(f'  {w:>9} {a[0]:>13.0f} {a[2]:>7} | {b[0]:>14.0f} {b[2]:>7} | {mem:>10.0f}'); R['rows'][w] = dict(cpu=a[0], cpu_p99=a[2], mixed=b[0], mixed_p99=b[2], mem=mem, failed=a[3] + b[3])
save('f165', R)
