import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f118'); R = {}
import dj, threading, json, http.client as hc
pg = dj.PG(9473, name='f118pg').start()
URL = f'postgresql+psycopg://lab@127.0.0.1:{pg.port}/lab'
N = 500000
pg.psql(f"create table big as select g as id, 'user' || g as name, 'user' || g || '@example.com' as email, (g * 1.5)::float8 as score from generate_series(1,{N}) g")
APP = '''
import os, json
from flask import Flask, Response, stream_with_context, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
app = Flask(__name__); app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB"]; db = SQLAlchemy(app)
LOG = os.environ["LOGF"]
def log(s):
    with open(LOG, "a") as f: f.write(s + "\\n")
@app.get("/pid")
def pid(): return str(os.getpid())
Q = sa.text("select id, name, email, score from big order by id")
@app.get("/all")
def all_():
    rows = db.session.execute(Q).mappings().all(); return jsonify([dict(r) for r in rows])
@app.get("/ndjson")
def ndjson():
    @stream_with_context
    def gen():
        with db.engine.connect().execution_options(stream_results=True) as conn:
            for r in conn.execute(Q).mappings(): yield json.dumps(dict(r), separators=(",", ":")) + "\\n"
    return Response(gen(), mimetype="application/x-ndjson")
@app.get("/array")
def array():
    @stream_with_context
    def gen():
        yield "["
        with db.engine.connect().execution_options(stream_results=True) as conn:
            first = True
            for r in conn.execute(Q).mappings():
                yield ("" if first else ",") + json.dumps(dict(r), separators=(",", ":")); first = False
        yield "]"
    return Response(gen(), mimetype="application/json")
@app.get("/array-fail")
def array_fail():
    def gen():
        yield "["
        for i in range(100000):
            if i == 50000: raise RuntimeError("db error mid-stream")
            yield ("" if i == 0 else ",") + json.dumps({"id": i})
        yield "]"
    return Response(gen(), mimetype="application/json")
@app.get("/slowstream")
def slowstream():
    def gen():
        import time
        try:
            for i in range(1000):
                yield f"{i}\\n" * 2000; time.sleep(0.01)
        except GeneratorExit: log("generator closed (client went away)"); raise
        finally: log("generator finally")
    return Response(gen(), mimetype="text/plain")
'''
d = mkapp('f118', {'app.py': APP}); LOGF = d / 'events.log'
def rss(pid): 
    try: return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()) / 1024
    except Exception: return 0
try:
    print(f'== 一:{N} 行数据(约 {N * 80 / 1e6:.0f} MB JSON):一次性 jsonify vs 流式 NDJSON vs 流式 JSON 数组')
    SRV = lambda: Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '4', '--workers', '1', '--timeout', '120', 'app:app'], DB=URL, LOGF=LOGF)
    R['paths'] = {}; print('  (每种方式各用一个全新的 worker 进程,避免上一次请求留下的内存影响峰值)')
    for label, path in (('一次性 jsonify', '/all'), ('流式 NDJSON', '/ndjson'), ('流式 JSON 数组', '/array')):
        with SRV() as s:
            wpid = int(s.get('/pid')[2]); base = rss(wpid); R['base'] = base
            mx = [base]; stop = threading.Event()
            def mon():
                while not stop.is_set(): mx[0] = max(mx[0], rss(wpid)); time.sleep(0.05)
            th = threading.Thread(target=mon); th.start()
            co = hc.HTTPConnection('127.0.0.1', s.port, timeout=120); t0 = time.perf_counter(); co.request('GET', path); r = co.getresponse(); ttfb = ms(t0); n = 0; first_chunk = None
            while True:
                ch = r.read(65536)
                if not ch: break
                if first_chunk is None: first_chunk = ms(t0)
                n += len(ch)
            total = ms(t0); stop.set(); th.join(); co.close()
            print(f'  {label:<16} 状态 {r.status} 响应头到达 {ttfb:>6.0f} ms | 首块数据 {first_chunk:>6.0f} ms | 全部读完 {total:>6.0f} ms | {n / 1e6:.1f} MB | Content-Length: {r.getheader("Content-Length")} | Transfer-Encoding: {r.getheader("Transfer-Encoding")} | worker 空闲 {base:.0f} MB,峰值 RSS {mx[0]:.0f} MB(多 {mx[0] - base:.0f} MB)')
            R['paths'][label] = dict(ttfb=ttfb, first=first_chunk, total=total, mb=n / 1e6, cl=r.getheader('Content-Length'), te=r.getheader('Transfer-Encoding'), rss=mx[0], base=base)
    with SRV() as s:
        print()
        print('== 二:流式 JSON 数组读完后是合法 JSON 吗?')
        co = hc.HTTPConnection('127.0.0.1', s.port, timeout=120); co.request('GET', '/array'); body = co.getresponse().read(); co.close(); arr = json.loads(body); print(f'  json.loads 解析成功,{len(arr)} 个元素,第一个 {arr[0]},最后一个 {arr[-1]}'); R['valid'] = [len(arr), arr[0], arr[-1]]
        print()
        print('== 三:流到一半出错:响应头已经发出,状态码已经是 200')
        co = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); co.request('GET', '/array-fail'); r = co.getresponse(); print('  状态码:', r.status, '| Transfer-Encoding:', r.getheader('Transfer-Encoding'))
        try: b = r.read(); out = f'读到 {len(b)} 字节,正常结束'
        except Exception as e: out = f'读取时抛出 {type(e).__name__}'
        print('  客户端读取结果:', out); R['midfail'] = [r.status, out]
        try: json.loads(b); print('  内容能解析成 JSON')
        except Exception: print('  已读到的内容不是完整的 JSON(数组缺右括号)' if out.startswith('读到') else '')
        co.close()
        print()
        print('== 四:客户端中途断开:服务端的生成器收到什么?')
        LOGF.write_text(''); co = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); co.request('GET', '/slowstream'); r = co.getresponse(); r.read(10000); co.close(); time.sleep(1.5)
        print('  服务端日志:', LOGF.read_text().strip().splitlines()); R['disconnect'] = LOGF.read_text().strip().splitlines()
finally:
    pg.stop()
save('f118', R)
