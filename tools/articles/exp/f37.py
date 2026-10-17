import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f37'); R = {}
import io
from flask import Flask, request
app = Flask('lim'); app.logger.disabled = True
@app.post('/up')
def up():
    try:
        f = request.files['file']; return {'name': f.filename, 'size': len(f.read())}
    except Exception as e: return {'error': type(e).__name__, 'code': getattr(e, 'code', None)}, getattr(e, 'code', 500)
@app.post('/raw')
def raw(): return {'len': len(request.get_data())}
@app.post('/override')
def override():
    request.max_content_length = 100
    return {'len': len(request.get_data())}
@app.get('/cfg')
def cfg(): return {'MAX_CONTENT_LENGTH': app.config['MAX_CONTENT_LENGTH'], 'request.max_content_length': request.max_content_length}
@app.post('/noread')
def noread(): return {'ok': True}
c = app.test_client()
print('== 一:MAX_CONTENT_LENGTH 默认是 None(不限制);设置后超限返回 413 Request Entity Too Large')
print('  默认配置:', c.get('/cfg').get_json()); R['default'] = c.get('/cfg').get_json()
app.config['MAX_CONTENT_LENGTH'] = 1000
print('  设成 1000 后:', c.get('/cfg').get_json())
R['rows'] = {}
for size in (500, 1000, 1001, 100000):
    r = c.post('/raw', data=b'x' * size, content_type='application/octet-stream'); R['rows'][size] = [r.status_code, r.get_data(as_text=True).strip().replace('\n', ' ')[:70]]; print(f'  POST /raw 正文 {size:>6} 字节 → {r.status_code} {R["rows"][size][1]}')
print()
print('== 二:检查发生在什么时候:读取请求体(访问 request.files / form / data / json)时才检查;不读就不检查')
r = c.post('/noread', data=b'x' * 100000, content_type='application/octet-stream'); print('  视图完全不读请求体,发 100000 字节(超限)→', r.status_code); R['noread'] = r.status_code
r = c.post('/up', data={'file': (io.BytesIO(b'x' * 5000), 'big.bin')}, content_type='multipart/form-data'); print('  multipart 上传 5000 字节的文件 →', r.status_code, r.get_json()); R['upload'] = [r.status_code, r.get_json()]
print()
print('== 三:每个请求单独设置(Flask 3.1):在读取请求体之前设 request.max_content_length;全局设置仍然是 1000')
app.config['MAX_CONTENT_LENGTH'] = None
r = c.post('/override', data=b'x' * 500); print('  全局不限制,视图里设 request.max_content_length = 100,发 500 字节 →', r.status_code); R['override'] = r.status_code
r = c.post('/override', data=b'x' * 50); print('  发 50 字节 →', r.status_code, r.get_json()); R['override_ok'] = r.status_code
print()
print('== 四:真实 HTTP:gunicorn + curl 上传 30 MB,限制 1 MB:服务器读了多少?客户端多久收到 413?')
d = mkapp('f37', {'app.py': '''
import time
from flask import Flask, request
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
@app.post("/up")
def up():
    f = request.files["file"]; return str(len(f.read()))
@app.post("/noread")
def noread(): return "没有读取请求体"
@app.post("/raw")
def raw(): return str(len(request.get_data()))
'''})
big = d / 'big.bin'; big.write_bytes(os.urandom(30 * 1024 * 1024)); small = d / 'small.bin'; small.write_bytes(os.urandom(500 * 1024))
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    R['real'] = {}
    for label, path, f_ in (('500 KB(限制内)', '/up', 'small.bin'), ('30 MB(超限)', '/up', 'big.bin'), ('30 MB,视图不读请求体', '/noread', 'big.bin')):
        t0 = time.perf_counter(); r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} 上传 %{size_upload} 字节 %{time_total}s', '-F', f'file=@{f_}', f'http://127.0.0.1:{s.port}{path}'], cwd=d, capture_output=True, text=True); R['real'][label] = r.stdout.strip(); print(f'  {label:<24} → {r.stdout.strip()}')
    t0 = time.perf_counter(); r = subprocess.run(['curl', '-s', '-o', 'resp.txt', '-w', '%{http_code} 上传 %{size_upload} 字节 %{time_total}s', '-H', 'Transfer-Encoding: chunked', '-H', 'Content-Type: application/octet-stream', '--data-binary', '@big.bin', f'http://127.0.0.1:{s.port}/raw'], cwd=d, capture_output=True, text=True); body_ = (d / 'resp.txt').read_text(errors='replace')[:80]; R['real']['30 MB chunked(无 Content-Length)'] = r.stdout.strip() + ' | 响应正文:' + body_; print(f'  30 MB chunked(无 CL)    → {r.stdout.strip()} | 响应正文:{body_!r}')
big.unlink(); small.unlink()
print()
print('== 五:413 响应本身:默认错误页;可以用 errorhandler(413) 返回 JSON')
app2 = Flask('lim2'); app2.config['MAX_CONTENT_LENGTH'] = 10
@app2.post('/x')
def x(): return str(len(request.get_data()))
@app2.errorhandler(413)
def too_big2(e): return {'error': 'payload too large', 'limit': app2.config['MAX_CONTENT_LENGTH']}, 413
r = app2.test_client().post('/x', data=b'y' * 50); print('  自定义 413 处理器:', r.status_code, r.get_json()); R['h413'] = [r.status_code, r.get_json()]
r = Flask('lim3'); r.config['MAX_CONTENT_LENGTH'] = 10; r.post('/x')(lambda: str(len(request.get_data()))); rr = r.test_client().post('/x', data=b'y' * 50); print('  默认 413 页:', rr.status_code, rr.get_data(as_text=True).strip().replace('\n', ' ')[:110]); R['d413'] = [rr.status_code, rr.get_data(as_text=True)[:110]]
save('f37', R)
