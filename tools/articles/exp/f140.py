import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f140'); R = {}
import websocket
APP = '''
from flask import Flask, jsonify
import json
app = Flask(__name__)
@app.get("/hello")
def hello(): return jsonify(msg="hello")
@app.get("/work")
def work():
    x = 0
    for i in range(20000): x += i * i
    return jsonify(x=x)
from asgiref.wsgi import WsgiToAsgi
from a2wsgi import WSGIMiddleware
asgiref_app = WsgiToAsgi(app); a2_app = WSGIMiddleware(app)
'''
d = mkapp('f140', {'app.py': APP})
def ab(port, path, n=4000, c=32):
    r = subprocess.run(['ab', '-n', str(n), '-c', str(c), f'http://127.0.0.1:{port}{path}'], capture_output=True, text=True, timeout=120); out = r.stdout
    rps = re.search(r'Requests per second:\s+([\d.]+)', out); mean = re.search(r'Time per request:\s+([\d.]+) \[ms\] \(mean\)', out); failed = re.search(r'Failed requests:\s+(\d+)', out); p99 = re.search(r'\s+99%\s+(\d+)', out)
    return float(rps.group(1)), float(mean.group(1)), int(failed.group(1)), int(p99.group(1)) if p99 else None
stacks = [
    ('gunicorn sync × 4 个 worker(WSGI)', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', 'app:app']),
    ('gunicorn gthread × 4 个 worker × 4 线程(WSGI)', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '4', '-k', 'gthread', '--threads', '4', 'app:app']),
    ('uvicorn × 4 个进程 + a2wsgi(ASGI)', ['uvicorn', 'app:a2_app', '--host', '127.0.0.1', '--port', '{port}', '--workers', '4', '--log-level', 'warning']),
    ('uvicorn × 4 个进程 + asgiref WsgiToAsgi(ASGI)', ['uvicorn', 'app:asgiref_app', '--host', '127.0.0.1', '--port', '{port}', '--workers', '4', '--log-level', 'warning']),
]
print(f'== 一:同一个 Flask 应用的不同部署方式,ApacheBench(4000 个请求、32 并发,不用 keep-alive;本机 {os.cpu_count()} 核,压测工具也占 CPU,只看相对关系)')
R['bench'] = {}
for path, label2 in (('/hello', '轻量接口 /hello'), ('/work', '有点计算的接口 /work(2 万次乘加)')):
    print(f'  [{label2}]'); R['bench'][path] = {}
    for label, cmd in stacks:
        with Server(d, cmd) as s:
            time.sleep(1.0); ab(s.port, path, n=500, c=8); rps, mean, failed, p99 = ab(s.port, path)
        print(f'     {label:<44} {rps:8.0f} 请求/秒 | 平均 {mean:6.1f} ms(32 并发)| p99 {p99} ms | 失败 {failed}'); R['bench'][path][label] = [rps, mean, p99, failed]
print()
print('== 二:Flask 经 WSGI 适配器放到 ASGI 服务器上,能不能处理 WebSocket?')
CODE = '''
from flask import Flask
app = Flask(__name__)
@app.get("/ws")
def ws(): return "plain http route"
from a2wsgi import WSGIMiddleware
a2_app = WSGIMiddleware(app)
'''
d2 = mkapp('f140ws', {'app.py': CODE})
with Server(d2, ['uvicorn', 'app:a2_app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning']) as s:
    try: w = websocket.create_connection(f'ws://127.0.0.1:{s.port}/ws', timeout=5); out = '连接成功'; w.close()
    except Exception as e: out = f'{type(e).__name__}: {str(e)[:100]}'
    print('  对 /ws 发 WebSocket 握手 →', out); R['ws'] = out
    st = s.get('/ws'); print('  同一路径的普通 HTTP GET →', st[0], st[2].decode())
save('f140', R)
