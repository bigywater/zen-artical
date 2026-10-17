import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f141'); R = {}
import http.client as hc
APP = '''
import time, io
from flask import Flask, request, jsonify, Response, stream_with_context
app = Flask(__name__)
@app.get("/environ")
def environ():
    e = request.environ
    keep = {k: (v if isinstance(v, (str, int, bool, tuple, type(None))) else type(v).__name__) for k, v in e.items() if not k.startswith(("HTTP_", "wsgi.errors")) or k in ("HTTP_HOST", "HTTP_X_DEMO")}
    return jsonify(keep)
@app.post("/echo")
def echo(): d = request.get_data(); return jsonify(n=len(d), ctype=request.content_type)
@app.get("/stream")
def stream():
    def gen():
        for i in range(4): yield f"chunk{i}\\n"; time.sleep(0.3)
    return Response(stream_with_context(gen()), mimetype="text/plain")
@app.get("/hello")
def hello(): return "hi"

# 一个自己写的、最小的 WSGI -> ASGI 适配器(只支持 HTTP;请求体整体读完再交给 WSGI 应用;WSGI 应用在线程里同步运行)
import asyncio
def mini_adapter(wsgi_app):
    async def asgi(scope, receive, send):
        if scope["type"] != "http": return
        body = b""
        while True:
            m = await receive(); body += m.get("body", b"")
            if not m.get("more_body"): break
        environ = {"REQUEST_METHOD": scope["method"], "SCRIPT_NAME": scope.get("root_path", ""), "PATH_INFO": scope["path"], "QUERY_STRING": scope["query_string"].decode(), "SERVER_NAME": scope["server"][0], "SERVER_PORT": str(scope["server"][1]), "REMOTE_ADDR": scope["client"][0], "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.version": (1, 0), "wsgi.url_scheme": scope["scheme"], "wsgi.input": io.BytesIO(body), "wsgi.errors": io.StringIO(), "wsgi.multithread": True, "wsgi.multiprocess": False, "wsgi.run_once": False, "CONTENT_LENGTH": str(len(body))}
        for k, v in scope["headers"]:
            k = k.decode().upper().replace("-", "_"); v = v.decode()
            if k == "CONTENT_TYPE": environ["CONTENT_TYPE"] = v
            elif k != "CONTENT_LENGTH": environ["HTTP_" + k] = v
        status = {}
        def start_response(s, headers, exc_info=None): status["s"] = s; status["h"] = headers
        def run():
            it = wsgi_app(environ, start_response); chunks = []
            try:
                for c in it: chunks.append(c)
            finally:
                if hasattr(it, "close"): it.close()
            return chunks
        chunks = await asyncio.to_thread(run)
        await send({"type": "http.response.start", "status": int(status["s"].split()[0]), "headers": [(k.lower().encode(), v.encode()) for k, v in status["h"]]})
        await send({"type": "http.response.body", "body": b"".join(chunks)})
    return asgi
from asgiref.wsgi import WsgiToAsgi
from a2wsgi import WSGIMiddleware
asgiref_app = WsgiToAsgi(app); a2_app = WSGIMiddleware(app); mini_app = mini_adapter(app)
'''
d = mkapp('f141', {'app.py': APP})
stacks = [('gunicorn(原生 WSGI)', ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '4', 'app:app']), ('uvicorn + a2wsgi', ['uvicorn', 'app:a2_app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning']), ('uvicorn + asgiref WsgiToAsgi', ['uvicorn', 'app:asgiref_app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning']), ('uvicorn + 自己写的 mini 适配器', ['uvicorn', 'app:mini_app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning'])]
print('== 一:交给 Flask 的 WSGI environ 里有什么(去掉 HTTP_ 头):各种适配方式的差别')
envs = {}
for label, cmd in stacks:
    with Server(d, cmd) as s:
        time.sleep(0.5); r = s.get('/environ', headers={'X-Demo': 'v'}); envs[label] = json.loads(r[2])
base = set(envs['gunicorn(原生 WSGI)'])
for label, e in envs.items():
    print(f'  [{label}] 键 {len(e)} 个'); extra = sorted(set(e) - base); missing = sorted(base - set(e)); print(f'     比 gunicorn 多出:{extra}'); print(f'     比 gunicorn 少了:{missing}'); R.setdefault('env', {})[label] = dict(n=len(e), extra=extra, missing=missing)
print('  几个关键值:')
for label, e in envs.items(): print(f'     {label:<30} SERVER_NAME={e.get("SERVER_NAME")} REMOTE_ADDR={e.get("REMOTE_ADDR")} wsgi.url_scheme={e.get("wsgi.url_scheme")} wsgi.multithread={e.get("wsgi.multithread")} wsgi.input={e.get("wsgi.input")}'); R.setdefault('keyvals', {})[label] = {k: str(e.get(k)) for k in ('SERVER_NAME', 'REMOTE_ADDR', 'wsgi.url_scheme', 'wsgi.multithread', 'wsgi.input', 'SCRIPT_NAME', 'SERVER_PROTOCOL')}
print()
print('== 二:请求体(POST 2 MB)与响应流:能不能边生成边发出')
R['stream'] = {}
for label, cmd in stacks:
    with Server(d, cmd) as s:
        time.sleep(0.5)
        c = hc.HTTPConnection('127.0.0.1', s.port, timeout=20); c.request('POST', '/echo', body=b'x' * (2 * 1024 * 1024), headers={'Content-Type': 'application/octet-stream'}); r = c.getresponse(); echo_out = json.loads(r.read()); c.close()
        c = hc.HTTPConnection('127.0.0.1', s.port, timeout=20); t0 = time.perf_counter(); c.request('GET', '/stream'); r = c.getresponse(); ts = []
        while True:
            ch = r.read(6)
            if not ch: break
            ts.append(round(ms(t0)))
        c.close(); print(f'  {label:<30} 2 MB 请求体读到 {echo_out["n"]} 字节 | 流式响应各块到达(ms):{ts}'); R['stream'][label] = [echo_out['n'], ts]
print()
print('== 三:自己写的 mini 适配器能跑通 Flask 的路由与 404 吗(POST 大请求体见上一节)')
with Server(d, stacks[3][1]) as s:
    time.sleep(0.5); st = s.get('/hello'); print('  GET /hello →', st[0], st[2].decode()); st = s.get('/nope'); print('  GET /nope →', st[0]); R['mini'] = [s.get('/hello')[0], s.get('/nope')[0]]
save('f141', R)
