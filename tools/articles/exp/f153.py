import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f153'); R = {}
import http.client as hc, socket
APP = '''
from flask import Flask, request, jsonify
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1000
@app.get("/hello")
def hello(): return jsonify(msg="hi")
@app.get("/p/<path:name>")
def p(name): return jsonify(name=name, path=request.path, raw=request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI"), full_path=request.full_path)
@app.post("/upload")
def upload(): d = request.get_data(); return jsonify(n=len(d), te=request.headers.get("Transfer-Encoding"), cl=request.content_length)
@app.get("/boom")
def boom(): raise RuntimeError("view exploded")
@app.get("/dir/")
def d(): return "dir"
@app.get("/host")
def host(): return jsonify(host=request.host, url=request.url, ua=request.headers.get("User-Agent"))
'''
d = mkapp('f153', {'app.py': APP})
import importlib.util
spec = importlib.util.spec_from_file_location('f153app', str(d / 'app.py')); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); tcapp = m.app; tc = tcapp.test_client()
def real(port, method, path, body=None, headers=None):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=10); c.request(method, path, body=body, headers=headers or {}); r = c.getresponse(); b = r.read(); h = {k.lower(): v for k, v in r.getheaders()}; c.close(); return r.status, h, b
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    time.sleep(0.8)
    print('== 一:响应头:同一个 /hello,test client 与真实 gunicorn 返回的头')
    r = tc.get('/hello'); th = {k.lower(): v for k, v in r.headers}; st, rh, b = real(s.port, 'GET', '/hello')
    print('  test client:', sorted(th)); print('  gunicorn   :', sorted(rh)); print('  gunicorn 多出:', sorted(set(rh) - set(th)), '| test client 多出:', sorted(set(th) - set(rh))); R['hdrs'] = [sorted(th), sorted(rh)]
    print()
    print('== 二:路径里的 %2F(编码的斜杠)与双斜杠')
    R['path'] = {}
    for label, path in (('/p/a%2Fb', '/p/a%2Fb'), ('/p/a//b', '/p/a//b'), ('/p/%E4%B8%AD', '/p/%E4%B8%AD')):
        r = tc.get(path); tj = r.get_json() if r.is_json else r.status_code; st, rh, b = real(s.port, 'GET', path); rj = json.loads(b) if rh.get('content-type', '').startswith('application/json') else st
        print(f'  {label:<14} test client → {tj if not isinstance(tj, dict) else {k: tj[k] for k in ("name", "path")}}'); print(f'  {"":<14} gunicorn     → {rj if not isinstance(rj, dict) else {k: rj[k] for k in ("name", "path")}}'); R['path'][label] = [str(tj)[:100], str(rj)[:100]]
    print()
    print('== 三:上传:没有 Content-Length 的分块传输(chunked)与 MAX_CONTENT_LENGTH = 1000')
    sock = socket.create_connection(('127.0.0.1', s.port)); body = b'x' * 3000
    sock.sendall(b'POST /upload HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n' + hex(len(body))[2:].encode() + b'\r\n' + body + b'\r\n0\r\n\r\n')
    resp = b''
    while True:
        ch = sock.recv(4096)
        if not ch: break
        resp += ch
    sock.close(); line = resp.split(b'\r\n')[0].decode(); tail = resp.split(b'\r\n\r\n', 1)[-1].decode().strip().replace('\n', ' '); print('  真实 gunicorn,3000 字节分块上传(MAX_CONTENT_LENGTH=1000)→', line, '|', tail[:100]); R['chunked_real'] = [line, tail[:100]]
    r = tc.post('/upload', data=body, content_type='application/octet-stream'); print('  test client,3000 字节(有 Content-Length)→', r.status_code); R['tc_big'] = r.status_code
    print('  test client 里没有直接模拟分块传输的简单写法(data 传迭代器会报 AttributeError),所以分块上传的行为只能用真实服务器验证'); R['tc_chunked'] = '无简单写法'
    print()
    print('== 四:视图抛异常:test client 在 TESTING 下直接抛出,真实服务器返回 500')
    tcapp.config['TESTING'] = True
    try: tc.get('/boom'); out = '没有抛出'
    except RuntimeError as e: out = f'异常传播到测试代码:RuntimeError: {e}'
    print('  TESTING=True 的 test client →', out); R['tc_boom'] = out
    tcapp.config['TESTING'] = False; r = tc.get('/boom'); print('  TESTING=False 的 test client →', r.status_code)
    st, rh, b = real(s.port, 'GET', '/boom'); print('  真实 gunicorn →', st); R['real_boom'] = st
    print()
    print('== 五:test client 默认的请求头与主机')
    r = tc.get('/host').get_json(); st, rh, b = real(s.port, 'GET', '/host'); rj = json.loads(b); print('  test client:', r); print('  真实 http.client:', {k: rj[k] for k in ('host', 'ua')}); R['host'] = [r, rj]
    print()
    print('== 六:重定向 Location:相对还是绝对')
    r = tc.get('/dir'); st, rh, b = real(s.port, 'GET', '/dir'); print('  test client →', r.status_code, r.headers.get('Location')); print('  gunicorn   →', st, rh.get('location')); R['redir'] = [r.headers.get('Location'), rh.get('location')]
save('f153', R)
