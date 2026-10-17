import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f160'); R = {}
import timeit, random, statistics
from flask import Flask, g, request, jsonify, Response, stream_with_context
app = Flask('tm'); app.logger.disabled = True
HOOK = []; MW = []; TD = []; AFTER_CALLS = [0]; TEARDOWN_CALLS = [0]
@app.before_request
def start(): g.t0 = time.perf_counter()
@app.after_request
def stop(r):
    AFTER_CALLS[0] += 1; d = (time.perf_counter() - g.t0) * 1000; HOOK.append((request.path, d)); r.headers['Server-Timing'] = f'app;dur={d:.2f}'; return r
@app.teardown_request
def td(e): TEARDOWN_CALLS[0] += 1
class Timing:
    def __init__(self, wsgi): self.wsgi = wsgi
    def __call__(self, environ, start_response):
        t0 = time.perf_counter(); it = self.wsgi(environ, start_response)
        try:
            for chunk in it: yield chunk
        finally:
            if hasattr(it, 'close'): it.close()
            MW.append((environ['PATH_INFO'], (time.perf_counter() - t0) * 1000))
app.wsgi_app = Timing(app.wsgi_app)
@app.get('/fast')
def fast(): return 'ok'
@app.get('/work')
def work(): time.sleep(0.05); return 'ok'
@app.get('/stream')
def stream():
    def gen():
        for i in range(3): time.sleep(0.1); yield f'{i}\n'
    return Response(stream_with_context(gen()), mimetype='text/plain')
@app.get('/boom')
def boom(): raise RuntimeError('x')
@app.get('/rand')
def rand(): time.sleep(0.2 if random.random() < 0.05 else 0.005); return 'ok'
c = app.test_client(); app.config['PROPAGATE_EXCEPTIONS'] = False
print('== 一:钩子计时 vs WSGI 中间件计时:同样的请求,各自记到的耗时')
R['hook_vs_mw'] = {}
for path in ('/fast', '/work', '/stream'):
    HOOK.clear(); MW.clear(); r = c.get(path); r.get_data(); h = HOOK[-1][1]; m = MW[-1][1]; print(f'  {path:<8} after_request 记到 {h:7.2f} ms | WSGI 中间件(含响应体生成完)记到 {m:7.2f} ms | Server-Timing 头:{r.headers.get("Server-Timing")}'); R['hook_vs_mw'][path] = [h, m]
print()
print('== 二:视图抛出未处理的异常时,after_request 与 teardown_request 分别被调用几次')
AFTER_CALLS[0] = TEARDOWN_CALLS[0] = 0
for p in ('/fast', '/boom', '/fast', '/boom'): c.get(p)
print(f'  4 个请求(其中 2 个抛异常,返回 500):after_request 被调用 {AFTER_CALLS[0]} 次,teardown_request 被调用 {TEARDOWN_CALLS[0]} 次'); R['calls'] = [AFTER_CALLS[0], TEARDOWN_CALLS[0]]
print('  (默认的 500 响应是 Flask 在异常处理里生成的,也会走 after_request——这里看到的次数就是实际调用数)')
print()
print('== 三:计时钩子本身的开销(test client,各 3000 次取最小)')
app2 = Flask('tm2'); app2.logger.disabled = True
@app2.get('/fast')
def f2(): return 'ok'
c2 = app2.test_client(); base = min(timeit.repeat(lambda: c2.get('/fast'), number=3000, repeat=3)) / 3000 * 1e6; wh = min(timeit.repeat(lambda: c.get('/fast'), number=3000, repeat=3)) / 3000 * 1e6
print(f'  无计时 {base:.0f} µs/请求;带 before/after 钩子与 WSGI 中间件 {wh:.0f} µs/请求;多出约 {wh - base:.0f} µs'); R['overhead'] = [base, wh]
print()
print('== 四:平均值会骗人:5% 的请求很慢(200 ms)、其余 5 ms,统计 400 个请求')
random.seed(1); HOOK.clear(); [c.get('/rand') for _ in range(400)]
ds = sorted(d for p, d in HOOK if p == '/rand'); n = len(ds); pct = lambda q: ds[min(n - 1, int(n * q))]
print(f'  {n} 个样本:平均 {statistics.mean(ds):.1f} ms | p50 {pct(0.5):.1f} ms | p95 {pct(0.95):.1f} ms | p99 {pct(0.99):.1f} ms | 最大 {ds[-1]:.1f} ms'); R['pct'] = [n, statistics.mean(ds), pct(0.5), pct(0.95), pct(0.99), ds[-1]]
save('f160', R)
