import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f117'); R = {}
import json, gzip, tracemalloc, timeit, orjson
from flask import Flask, jsonify, Response
def rows(n): return [{'id': i, 'name': f'user{i}', 'email': f'user{i}@example.com', 'score': i * 1.5, 'tags': ['a', 'b'], 'active': i % 2 == 0} for i in range(n)]
print('== 一:jsonify 一个大列表:耗时、响应大小、峰值内存(每个规模各取 3 次最小耗时)')
app = Flask('b'); app.logger.disabled = True; DATA = {n: rows(n) for n in (1000, 10000, 100000)}
@app.get('/<int:n>')
def big(n): return jsonify(DATA[n])
c = app.test_client(); R['scale'] = {}
print(f'  {"行数":>7} {"耗时(ms)":>10} {"响应(MB)":>10} {"峰值内存(MB)":>14}')
for n in (1000, 10000, 100000):
    c.get(f'/{n}'); t = min(timeit.repeat(lambda: c.get(f'/{n}'), number=1, repeat=3)) * 1000
    tracemalloc.start(); r = c.get(f'/{n}'); size = len(r.data); cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    print(f'  {n:>7} {t:>10.1f} {size / 1e6:>10.2f} {peak / 1e6:>14.1f}'); R['scale'][n] = [t, size, peak]
print()
print('== 二:同样 10 万行:各种序列化方式')
data = DATA[100000]; res = {}
for label, fn in (('json.dumps(默认,带空格分隔)', lambda: json.dumps(data)), ('json.dumps(紧凑 separators)', lambda: json.dumps(data, separators=(',', ':'))), ('orjson.dumps', lambda: orjson.dumps(data))):
    t = min(timeit.repeat(fn, number=1, repeat=3)) * 1000; sz = len(fn() if isinstance(fn(), (bytes, str)) else b''); res[label] = [t, sz]; print(f'  {label:<30} {t:>8.1f} ms  {sz / 1e6:.2f} MB')
R['ser'] = res
print()
print('== 三:Flask 的 debug 模式会把 JSON 缩进(响应变大)')
for dbg in (False, True):
    a = Flask('d'); a.debug = dbg; a.logger.disabled = True
    @a.get('/x')
    def x(): return jsonify(rows(1000))
    r = a.test_client().get('/x'); print(f'  debug={dbg!s:<5} compact={a.json.compact} 响应 {len(r.data) / 1e3:.0f} KB'); R.setdefault('debug', {})[str(dbg)] = [len(r.data), a.json.compact]
print()
print('== 四:gzip 压缩:大小与耗时(10 万行)')
raw = json.dumps(data, separators=(',', ':')).encode(); R['gz'] = {}
for lvl in (1, 6, 9):
    t = min(timeit.repeat(lambda: gzip.compress(raw, lvl), number=1, repeat=3)) * 1000; z = gzip.compress(raw, lvl); print(f'  gzip level {lvl}: {len(raw) / 1e6:.2f} MB → {len(z) / 1e6:.2f} MB({len(z) / len(raw) * 100:.1f}%),压缩耗时 {t:.0f} ms'); R['gz'][lvl] = [len(raw), len(z), t]
print()
print('== 五:真实 gunicorn:大响应的首字节时间与总时间;视图耗时超过 worker timeout')
APP = '''
import time, json
from flask import Flask, jsonify
app = Flask(__name__)
DATA = [{"id": i, "name": f"user{i}", "email": f"user{i}@example.com", "score": i * 1.5} for i in range(100000)]
@app.get("/big")
def big(): return jsonify(DATA)
@app.get("/slow")
def slow(): time.sleep(4); return "done"
'''
d = mkapp('f117', {'app.py': APP}); import http.client as hc
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--timeout', '2', '--workers', '1', 'app:app']) as s:
    co = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); t0 = time.perf_counter(); co.request('GET', '/big'); resp = co.getresponse(); ttfb = ms(t0); body = resp.read(); total = ms(t0); co.close()
    print(f'  /big(10 万行,{len(body) / 1e6:.1f} MB):收到响应头用时 {ttfb:.0f} ms,读完全部用时 {total:.0f} ms,Content-Length 头 = {resp.getheader("Content-Length")}'); R['live'] = [ttfb, total, len(body)]
    t0 = time.perf_counter()
    try: co = hc.HTTPConnection('127.0.0.1', s.port, timeout=30); co.request('GET', '/slow'); r = co.getresponse(); out = f'HTTP {r.status}'; r.read()
    except Exception as e: out = type(e).__name__
    print(f'  /slow(睡 4 秒,gunicorn --timeout 2):客户端结果 {out},用时 {ms(t0):.0f} ms'); R['timeout'] = [out, ms(t0)]; time.sleep(0.5)
    print('  服务端日志:', [l[:90] for l in s.logtext().splitlines() if 'TIMEOUT' in l or 'killed' in l.lower() or 'Booting worker' in l][-3:])
save('f117', R)
