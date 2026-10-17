import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f137'); R = {}
import asyncio, threading, timeit, http.client as hc
from flask import Flask, request, jsonify
print('== 一:async def 视图在 test client 里的行为;事件循环与线程')
app = Flask('a'); app.logger.disabled = True
@app.get('/s')
def sync_view(): return 'sync'
@app.get('/a')
async def async_view(): await asyncio.sleep(0); return 'async'
@app.get('/loop')
async def loop_view(): return jsonify(loop=id(asyncio.get_running_loop()), thread=threading.get_ident(), req_path=request.path)
@app.get('/gather')
async def gather_view():
    t0 = time.perf_counter(); await asyncio.gather(asyncio.sleep(0.5), asyncio.sleep(0.5), asyncio.sleep(0.5)); return jsonify(took=round(time.perf_counter() - t0, 2))
@app.get('/seq')
async def seq_view():
    t0 = time.perf_counter()
    for _ in range(3): await asyncio.sleep(0.5)
    return jsonify(took=round(time.perf_counter() - t0, 2))
c = app.test_client()
print('  GET /s →', c.get('/s').get_data(as_text=True), '| GET /a →', c.get('/a').get_data(as_text=True))
l1, l2 = c.get('/loop').get_json(), c.get('/loop').get_json(); print('  两个请求里事件循环的 id 相同吗:', l1['loop'] == l2['loop'], '| 线程相同吗:', l1['thread'] == l2['thread'], '| 视图里能用 request.path:', l1['req_path']); R['loop'] = [l1['loop'] == l2['loop'], l1['thread'] == l2['thread']]
r1, r2 = c.get('/gather').get_json(), c.get('/seq').get_json(); print(f'  一个请求里:asyncio.gather 三个各 0.5 秒的等待 → {r1["took"]} 秒;依次 await 三次 → {r2["took"]} 秒'); R['gather'] = [r1['took'], r2['took']]
print()
print('== 二:每个请求的额外开销:async 视图 vs sync 视图(test client,各 3000 次取最小)')
t_s = min(timeit.repeat(lambda: c.get('/s'), number=3000, repeat=3)) / 3000 * 1e6; t_a = min(timeit.repeat(lambda: c.get('/a'), number=3000, repeat=3)) / 3000 * 1e6
print(f'  sync 视图 {t_s:.0f} µs/请求;async 视图(await 一个 sleep(0)){t_a:.0f} µs/请求;多出约 {t_a - t_s:.0f} µs'); R['overhead'] = [t_s, t_a]
print()
APP = '''
import asyncio, os, time, threading
from flask import Flask, jsonify
app = Flask(__name__)
@app.get("/wait")
async def wait(): await asyncio.sleep(1); return jsonify(pid=os.getpid(), thread=threading.get_ident())
@app.get("/syncwait")
def syncwait(): time.sleep(1); return jsonify(pid=os.getpid(), thread=threading.get_ident())
'''
d = mkapp('f137', {'app.py': APP})
def burst(port, path, n):
    res = []
    def one():
        c = hc.HTTPConnection('127.0.0.1', port, timeout=60); c.request('GET', path); r = c.getresponse(); res.append((r.status, json.loads(r.read()))); c.close()
    ths = [threading.Thread(target=one) for _ in range(n)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; return ms(t0), res
print('== 三:8 个并发请求,每个 await asyncio.sleep(1):async 视图在 WSGI 服务器下并不会突破 worker 的并发数')
R['live'] = {}
for label, cmd in (('gunicorn sync,1 个 worker', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app']), ('gunicorn gthread,1 个 worker × 8 线程', ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', '-k', 'gthread', '--threads', '8', 'app:app'])):
    with Server(d, cmd) as s:
        time.sleep(0.5); ta, ra = burst(s.port, '/wait', 8); ts, rs = burst(s.port, '/syncwait', 8)
        print(f'  {label:<38} async 视图 {ta / 1000:.2f} 秒 | sync 视图 {ts / 1000:.2f} 秒 | 全部 200:{all(x[0] == 200 for x in ra)}'); R['live'][label] = [ta, ts]
save('f137', R)
