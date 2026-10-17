import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f139'); R = {}
import threading, http.client as hc
RAW = '''
import asyncio, time
async def app(scope, receive, send):
    if scope["type"] != "http": return
    path = scope["path"]
    if path == "/block": time.sleep(2)
    elif path == "/await": await asyncio.sleep(2)
    elif path == "/thread": await asyncio.to_thread(time.sleep, 2)
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": path.encode()})
'''
FLASK = '''
import asyncio, time
from flask import Flask
app = Flask(__name__)
@app.get("/block")
async def block(): time.sleep(2); return "blocked"
@app.get("/await")
async def aw(): await asyncio.sleep(2); return "awaited"
@app.get("/syncblock")
def syncblock(): time.sleep(2); return "syncblock"
@app.get("/fast")
def fast(): return "fast"
'''
FL_ASGI = FLASK + '''
from asgiref.wsgi import WsgiToAsgi
asgi_app = WsgiToAsgi(app)
from a2wsgi import WSGIMiddleware
a2_app = WSGIMiddleware(app)
'''
dr = mkapp('f139raw', {'rawapp.py': RAW}); df = mkapp('f139flask', {'app.py': FL_ASGI})
def timed(port, path):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=30); t0 = time.perf_counter(); c.request('GET', path); r = c.getresponse(); r.read(); c.close(); return ms(t0)
def probe(port, slow, fast='/fast'):
    th = threading.Thread(target=lambda: timed(port, slow)); th.start(); time.sleep(0.4); tf = timed(port, fast); th.join(); return tf
print('== 一:纯 ASGI 应用(没有框架)跑在 uvicorn 上:一个慢请求进行中,另一个什么都不做的请求要等多久')
R['raw'] = {}
with Server(dr, ['uvicorn', 'rawapp:app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning']) as s:
    time.sleep(0.5)
    for label, slow in (('在协程里调用 time.sleep(2)(阻塞)', '/block'), ('await asyncio.sleep(2)(让出)', '/await'), ('await asyncio.to_thread(time.sleep, 2)(放到线程)', '/thread')):
        tf = probe(s.port, slow, '/quick'); print(f'  {label:<50} 另一个请求用了 {tf:7.0f} ms'); R['raw'][label] = tf
print()
print('== 二:Flask 的 async 视图里调用阻塞代码,在 gunicorn gthread(8 线程)下')
R['gt'] = {}
dg = mkapp('f139g', {'app.py': FLASK})
with Server(dg, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app']) as s:
    time.sleep(0.5)
    for label, slow in (('async 视图里 time.sleep(2)', '/block'), ('async 视图里 await asyncio.sleep(2)', '/await'), ('sync 视图里 time.sleep(2)', '/syncblock')):
        tf = probe(s.port, slow); print(f'  {label:<40} 另一个请求(/fast)用了 {tf:5.0f} ms'); R['gt'][label] = tf
print()
print('== 三:同一个 Flask 应用,用 asgiref 的 WsgiToAsgi 放到 uvicorn 上(单进程):阻塞会不会拖慢所有请求')
R['asgi'] = {}
with Server(df, ['uvicorn', 'app:asgi_app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning']) as s:
    time.sleep(0.5)
    for label, slow in (('async 视图里 time.sleep(2)', '/block'), ('async 视图里 await asyncio.sleep(2)', '/await'), ('sync 视图里 time.sleep(2)', '/syncblock')):
        tf = probe(s.port, slow); print(f'  {label:<40} 另一个请求(/fast)用了 {tf:5.0f} ms'); R['asgi'][label] = tf
print()
print('== 四:换成 a2wsgi 的 WSGIMiddleware(同样放在 uvicorn 单进程上)')
R['a2'] = {}
with Server(df, ['uvicorn', 'app:a2_app', '--host', '127.0.0.1', '--port', '{port}', '--log-level', 'warning']) as s:
    time.sleep(0.5)
    for label, slow in (('async 视图里 time.sleep(2)', '/block'), ('async 视图里 await asyncio.sleep(2)', '/await'), ('sync 视图里 time.sleep(2)', '/syncblock')):
        tf = probe(s.port, slow); print(f'  {label:<40} 另一个请求(/fast)用了 {tf:5.0f} ms'); R['a2'][label] = tf
print()
print('== 五:在事件循环里「看得见」阻塞:用 asyncio 的 debug 模式的慢回调警告')
CODE = """
import asyncio, time, logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
async def main():
    asyncio.get_running_loop().slow_callback_duration = 0.1
    async def bad(): time.sleep(0.5)
    await bad()
asyncio.run(main(), debug=True)
"""
dd = mkapp('f139d', {'x.py': 'pass'}); rc, out = py(dd, CODE); line = [l for l in out.splitlines() if 'took' in l or 'Executing' in l][:2]; print('  ', line); R['debug'] = line
save('f139', R)
